#!/usr/bin/env python3
"""Evidence-backed, on-demand verification; the existing Hermes agent searches the web."""
import contextlib,fcntl,hashlib,importlib.util,json,re,secrets,sys
from pathlib import Path
from datetime import datetime
from runtime import BASE, assert_safe
import collector
layout=collector.processor.layout
START='<!-- verification:start -->';END='<!-- verification:end -->'

def require_record(url):
    rec=layout.lookup(url)
    if not rec or not rec.get('data'):raise ValueError('请先完成文章整理；核验不自动抓取或整理文章')
    return rec

def prepare(params):
    rec=require_record(params['url']);note=BASE/rec['path'];text=note.read_text()
    if layout.protected_digest(text)!=rec['protected_digest']:raise ValueError('正文有手动修改，请先核对；未覆盖')
    claims=params.get('claims')
    if not claims:
        return {'ok':True,'stage':'待选择关键说法','title':rec['title'],'url':rec['url'],'article':rec['raw'],
                'candidate_information':{k:rec['data'].get(k,'') for k in ('关键数据与案例','待核实')},
                'instruction':'从原文选3至6条可查证的关键说法，再以claims调用prepare。必须用现有web_search/web_extract或浏览器实际查询原始发布方和独立证据，逐条记录来源和结论。搜索无结果不等于原文错误。'}
    if not isinstance(claims,list) or not 1<=len(claims)<=6 or any(not isinstance(c,str) or not 5<=len(c.strip())<=400 for c in claims):raise ValueError('claims需要1至6条完整说法，每条5至400字符')
    token=secrets.token_hex(16)
    request={'url':rec['url'],'claims':[c.strip() for c in claims],'digest':layout.protected_digest(text),'prepared':datetime.now(layout.TZ).isoformat()}
    folder=BASE/'_AI/刘向/运行记录/核验请求';assert_safe(folder);folder.mkdir(parents=True,exist_ok=True)
    layout.atomic(folder/(token+'.json'),json.dumps(request,ensure_ascii=False,indent=2))
    return {'ok':True,'stage':'待联网查证','token':token,'claims':[{'id':str(i+1),'claim':c} for i,c in enumerate(request['claims'])],
            'instruction':'调用现有联网工具逐项查询，再以save提交全部id。每条包含verdict(支持/矛盾/未确认)、reason、queries、evidence。证据含url、title、excerpt短原文；支持/矛盾须有真实可读取的证据，不能只改状态。原页面打不开时该项写未确认，保留查询说明。'}

def normalize(text):return re.sub(r'\s+','',text).casefold()

def read_evidence(item,cache):
    url=item.get('url','');url=layout.canonical_url(url)
    if url not in cache:
        final,body,kind=collector.fetch(url)
        if 'text/plain' in kind:plain=body.decode('utf-8-sig')
        else:
            charset=re.search(br'charset=["\']?([a-zA-Z0-9_-]+)',body[:4096])
            tree=collector.html.fromstring(body,parser=collector.html.HTMLParser(encoding=charset[1].decode() if charset else 'utf-8'))
            for node in tree.xpath('//script|//style|//noscript'):node.drop_tree()
            plain=tree.text_content()
        cache[url]=(final,plain,hashlib.sha256(body).hexdigest())
    final,plain,digest=cache[url];quote=item.get('excerpt','').strip();title=item.get('title','').strip()
    if not title or len(title)>200 or not 16<=len(quote)<=160:raise ValueError('证据需要标题及16至160字符的短原文')
    if len(quote.split())>25:raise ValueError('单条证据原文请限制在25个词以内')
    if normalize(quote) not in normalize(plain):raise ValueError('提交的证据原文未在网页中找到；未提升核验状态')
    return {'url':final,'title':title,'excerpt':quote,'page_sha256':digest,'retrieved':datetime.now(layout.TZ).isoformat()}

def clean(text):return str(text).replace(START,'').replace(END,'').strip()

def save(params):
    token=params.get('token','')
    if not re.fullmatch(r'[a-f0-9]{32}',token):raise ValueError('需要prepare返回的真实token')
    request_path=BASE/'_AI/刘向/运行记录/核验请求'/f'{token}.json'
    request=json.loads(request_path.read_text())
    if request.get('completed'):raise ValueError('此核验请求已保存；如需重查请重新prepare')
    url=request['url'];rows=params.get('results',[])
    if not isinstance(rows,list) or len(rows)!=len(request['claims']):raise ValueError('请提交本次选定的全部说法，未确认项也不能省略')
    expected={str(i+1) for i in range(len(rows))}
    if {str(r.get('id')) for r in rows}!=expected:raise ValueError('核验id不完整或重复')
    checked=[];cache={}
    for row in sorted(rows,key=lambda r:int(r['id'])):
        verdict=row.get('verdict');reason=clean(row.get('reason',''));queries=row.get('queries',[]);evidence=row.get('evidence',[])
        if verdict not in ('支持','矛盾','未确认') or not reason or len(reason)>1500:raise ValueError('每项需明确结论和理由')
        if not isinstance(queries,list) or not queries or any(not isinstance(q,str) or not q.strip() for q in queries):raise ValueError('每项需记录实际使用的查询词')
        if not isinstance(evidence,list) or len(evidence)>3:raise ValueError('每项最多3条证据')
        if verdict!='未确认' and not evidence:raise ValueError('支持/矛盾不能缺少证据；未更新状态')
        verified=[read_evidence(e,cache) for e in evidence]
        checked.append({'id':str(row['id']),'claim':request['claims'][int(row['id'])-1],'verdict':verdict,'reason':reason,'queries':queries,'evidence':verified})
    answered=sum(r['verdict']!='未确认' for r in checked)
    status='未核验' if not answered else '已核验' if answered==len(checked) else '部分核验'
    stamp=datetime.now(layout.TZ).isoformat(timespec='seconds')
    lines=[START,'### 外部核验记录','',f'核验时间：{stamp}',f'核验范围：本次选定的 {len(checked)} 条关键说法；已取得结论 {answered} 条。此状态不表示整篇文章所有说法正确。','旧解读中的疑点保留；以下为此次查证结果。','']
    for row in checked:
        lines += [f'**{row["id"]}. {clean(row["claim"])}**',f'- 结论：{row["verdict"]}',f'- 依据与限制：{row["reason"]}',f'- 查询：'+ '；'.join(clean(q) for q in row['queries'])]
        for e in row['evidence']:
            label=clean(e['title']).replace('[','').replace(']','')
            lines += [f'- 证据：[{label}]({e["url"]})',f'  > {clean(e["excerpt"])}']
        lines += ['']
    lines += [END];section='\n'.join(lines)
    with (layout.state_dir()/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);rec=require_record(url);note=BASE/rec['path'];previous=note.read_text()
        if layout.protected_digest(previous)!=request['digest']:raise ValueError('查证期间正文已变化，未覆盖，请重新prepare')
        if layout.RAW_HEADING not in previous:raise ValueError('原文分区缺失，未覆盖')
        prefix,raw=previous.split(layout.RAW_HEADING,1)
        prefix=re.sub(re.escape(START)+r'.*?'+re.escape(END)+r'\n*','',prefix,flags=re.S)
        text=prefix+section+'\n\n'+layout.RAW_HEADING+raw
        header,body=text[4:].split('\n---\n',1)
        if re.search(r'^核验状态:',header,re.M):header=re.sub(r'^核验状态:[^\n]*',lambda _: '核验状态: '+json.dumps(status,ensure_ascii=False),header,flags=re.M)
        else:header+='\n核验状态: '+json.dumps(status,ensure_ascii=False)
        text='---\n'+header+'\n---\n'+body
        layout.backup_file(note);layout.atomic(note,text)
        rec.update(verification_status=status,verification_markdown=section,verification={'checked':checked,'time':stamp,'scope':'selected_claims'},protected_digest=layout.protected_digest(text))
        layout.atomic(layout.state_dir()/(layout.article_id(url)+'.json'),json.dumps(rec,ensure_ascii=False,indent=2))
        request['completed']=stamp;layout.atomic(request_path,json.dumps(request,ensure_ascii=False,indent=2))
    result=layout.result(rec,'核验结果已保存');result.update(verification_status=status,checked=len(checked),concluded=answered)
    return result

def run(params):
    action=params.get('action')
    if action=='prepare':return prepare(params)
    if action=='save':return save(params)
    raise ValueError('未知核验动作')

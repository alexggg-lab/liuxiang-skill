"""Single-document article storage for Liuxiang."""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from runtime import BASE, CONFIG, SETTINGS, assert_safe
assert_safe(BASE)
TZ = ZoneInfo(SETTINGS.get('timezone', 'Asia/Shanghai'))
TYPES = ('行业研究', '教程指南', '观点分析', '案例复盘', '工具资料')
RAW_HEADING = '## 完整图文原文\n\n'
PERSONAL_START = '<!-- personal:start -->'
PERSONAL_END = '<!-- personal:end -->'


def canonical_url(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise ValueError('需要完整的网页来源链接')
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))


def article_id(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:24]


def state_dir():
    path = BASE / '_AI/刘向/运行记录/文章'
    if path.is_symlink():
        raise ValueError('文章记录目录不能是软链接')
    assert_safe(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic(path, text):
    assert_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('不能覆盖软链接')
    fd, tmp = tempfile.mkstemp(prefix='.note-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def lookup(url):
    path = state_dir() / (article_id(url) + '.json')
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    target = BASE / record['path']
    assert_safe(target)
    if not target.resolve().is_relative_to(BASE):
        raise ValueError('记录路径超出知识库')
    if target.is_symlink() or not target.is_file():
        raise ValueError('已登记的文章笔记不存在，请先检查，不重复抓取')
    return record


def clean_title(title):
    title = re.sub(r'__([0-9a-f]{12,64})(?:\.md)?(?:__AI(?:整理|解读)_[0-9a-f]+)?$', '', title)
    title = re.sub(r'[\x00-\x1f/\\:*?"<>|\[\]#]', '_', title).strip('. ')
    while len(title.encode('utf-8')) > 180:
        title = title[:-1]
    return title or '未命名文章'


def personal(text):
    if PERSONAL_START in text and PERSONAL_END in text:
        return text.split(PERSONAL_START, 1)[1].split(PERSONAL_END, 1)[0].strip()
    return ''


def protected_digest(text):
    # Obsidian attributes are user-editable; protect the body, preserve the live header.
    text = re.sub(r'^---\n.*?\n---\n', '', text, count=1, flags=re.S)
    text = re.sub(r'<!-- personal:start -->.*?<!-- personal:end -->', '', text, count=1, flags=re.S)
    return hashlib.sha256(text.encode()).hexdigest()


def raw_body(source):
    if RAW_HEADING in source:
        return source.split(RAW_HEADING, 1)[1].rstrip()
    source = re.sub(r'^---\n.*?\n---\n', '', source, count=1, flags=re.S)
    source = re.sub(r'^# [^\n]*\n', '', source, count=1)
    source = re.sub(r'^.*(?:原始链接|抓取地址)[：:].*\n', '', source, flags=re.M)
    # Old imports used text paths rather than Obsidian embeds.
    source = re.sub(r'^本地图片[：:]\s*(05_原始素材/[^\n]+)$', r'![[\1]]', source, flags=re.M)
    return source.strip()


def render(record, data=None, thoughts=''):
    data = data or record.get('data') or {}
    topics = SETTINGS['topics']
    domains = [tag for tag in data.get('推荐标签', []) if tag in topics][:3]
    kind = data.get('内容类型', '观点分析')
    if kind not in TYPES:
        kind = '观点分析'
    stage = '已解读' if data else '待整理'
    meta = {'标题': record['title'], '领域': domains, '类型': kind, '整理状态': stage,
            '来源': record.get('source_metadata', {}).get('source_name', ''),
            '原始链接': record['url'], '收录日期': record['received'],
            '核验状态': record.get('verification_status', '未核验'),
            'tags': [f'领域/{t}' for t in domains] + [f'类型/{kind}', f'状态/{stage}']}
    author = record.get('source_metadata', {}).get('author', '')
    if author:
        meta['作者'] = author
    lines = ['---'] + [f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in meta.items()] + ['---', '', '# '+record['title'], '']
    lines += ['## 这篇文章讲什么', '', '> 以下为作者观点的转述；外部核验范围与结果见 AI 解读中的核验记录。', '',
              data.get('一句话结论', '原文已保存，尚未生成解读。'), '',
              '## 值得留下的信息', '', data.get('原文核心信息', '待整理。'), '',
              '### 数据与案例', '', data.get('关键数据与案例', '原文未提供具体数据。'), '',
              '## 我的想法', '', PERSONAL_START, thoughts, PERSONAL_END, '',
              '## AI 解读', '', '> 以下为 AI 分析和建议，不代表原文事实，也不代表本人观点。', '',
              data.get('AI分析', '尚未生成。'), '', '### 待核实', '', data.get('待核实', '尚未核验。'), '']
    if data.get('可二创方向'):
        lines += ['### 可借鉴方向', ''] + ['- '+v for v in data['可二创方向']] + ['']
    if record.get('interpretation'):
        for heading, content in record['interpretation'].items():
            lines += ['### '+heading, '', content, '']
    if record.get('verification_markdown'):
        lines += [record['verification_markdown'], '']
    lines += ['## 完整图文原文', '', record['raw'].rstrip(), '']
    if record.get('image_errors'):
        lines += ['### 图片保存情况', ''] + ['- '+v for v in record['image_errors']] + ['']
    return '\n'.join(lines)


def preserve_properties(rendered, previous, update_stage=False):
    """Keep editable properties verbatim during subsequent AI updates."""
    old_match = re.match(r'^---\n(.*?)\n---\n', previous, re.S)
    new_match = re.match(r'^---\n(.*?)\n---\n', rendered, re.S)
    if not old_match or not new_match:
        raise ValueError('笔记属性格式不完整，未覆盖')
    header = old_match[1]
    for line in new_match[1].splitlines():
        key = line.split(':', 1)[0]
        if not re.search(r'^'+re.escape(key)+r':', header, re.M):
            header += '\n'+line
        elif update_stage and key in ('整理状态', 'tags'):
            header = re.sub(r'^'+re.escape(key)+r':[^\n]*(?:\n(?:[ \t]+[^\n]*|-[ \t]+[^\n]*))*', lambda _: line, header, flags=re.M)
    return '---\n'+header+'\n---\n'+rendered[new_match.end():]


def backup_file(path):
    cfg = SETTINGS
    folder = Path(cfg['backup_directory']).expanduser().resolve() / '笔记历史' / article_stamp()
    dest = folder / path.relative_to(BASE)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def article_stamp():
    return datetime.now(TZ).strftime('%Y%m%d-%H%M%S-%f')


def publish(url, title=None, raw=None, data=None, image_errors=None, interpretation=None, raw_is_body=False, source_metadata=None):
    with (state_dir() / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = lookup(url)
        if old and (raw is not None or (data is not None and old.get('data'))):
            return result(old)
        record = dict(old or {'url': canonical_url(url), 'received': datetime.now(TZ).date().isoformat()})
        record.setdefault('processor', 'AI')
        record.setdefault('verification_status', '未核验')
        if source_metadata is not None:
            record['source_metadata'] = {k: str(source_metadata.get(k, '')).strip() for k in ('source_name', 'author')}
        if title is not None:
            record['title'] = clean_title(title)
        if raw is not None:
            record['raw'] = raw if raw_is_body else raw_body(raw)
        if data is not None:
            record['data'] = data
        if image_errors is not None:
            record['image_errors'] = image_errors
        if interpretation is not None:
            record['interpretation'] = interpretation
        if not record.get('title') or not record.get('raw'):
            raise ValueError('缺少文章标题或原文，不发布笔记')
        thoughts, old_path = '', None
        if old:
            old_path = BASE / old['path']
            previous = old_path.read_text(encoding='utf-8')
            if old['protected_digest'] != protected_digest(previous):
                raise ValueError('笔记正文被手动修改，请保留手动内容后再处理；未覆盖')
            thoughts = personal(previous)
        domains = [v for v in record.get('data', {}).get('推荐标签', [])
                   if v in SETTINGS['topics']]
        folder = BASE / ('01_外部知识/'+(domains[0] if domains else '待分类') if record.get('data') else '00_收件箱')
        assert_safe(folder)
        folder.mkdir(parents=True, exist_ok=True)
        if folder.is_symlink():
            raise ValueError('目标目录不能是软链接')
        path = folder / (record['title'] + '.md')
        if path.exists() and path != old_path:
            if path.is_symlink():
                raise ValueError('目标文件不能是软链接')
            n = 2
            while (folder / f'{record["title"]}（{n}）.md').exists():
                n += 1
            path = folder / f'{record["title"]}（{n}）.md'
        text = render(record, thoughts=thoughts)
        if old:
            text = preserve_properties(text, previous, update_stage=bool(record.get('data') and not old.get('data')))
        if old_path and old_path == path and old_path.read_text(encoding='utf-8') == text:
            return result(record, '已存在，未重复生成')
        if old_path:
            backup_file(old_path)
        atomic(path, text)
        record['path'] = str(path.relative_to(BASE))
        record['protected_digest'] = protected_digest(text)
        atomic(state_dir() / (article_id(url)+'.json'), json.dumps(record, ensure_ascii=False, indent=2))
        if old_path and old_path != path:
            old_path.unlink()  # Full file is preserved in the external history backup.
        return result(record, '已整理' if record.get('data') else '原文已归档，待整理')


def result(record, status=None):
    path = str(BASE / record['path'])
    return {'ok': True, 'title': record['title'], 'source': path, 'result': path,
            'status': status or ('已整理，跳过重复收录' if record.get('data') else '原文已归档，待整理'),
            'summary': record.get('data', {}).get('一句话结论', '')}

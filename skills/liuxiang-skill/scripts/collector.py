#!/usr/bin/env python3
"""Hermes 的受限知识库入口：仅抓取公开网页、追加原文与整理结果。"""
import argparse
import fcntl
import hashlib
import http.client
import importlib.util
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
import sys
import os
import subprocess
import tempfile
from lxml import html
from datetime import datetime
from urllib.parse import urlsplit, urljoin, urlunsplit
import trafilatura

from runtime import BASE, assert_safe
import processor

def public_target(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('只接受没有账户密码的 http/https 公网链接')
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    if port not in (80, 443):
        raise ValueError('只接受标准网页端口')
    records = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('不抓取本机、局域网或保留地址')
    return parts, port, addresses[0]

def fetch(url, *, image=False):
    # 将连接固定到已验证的公网 IP，HTTPS 仍按原主机名校验证书。
    for _ in range(6):
        parts, port, address = public_target(url)
        host = parts.hostname.encode('idna').decode('ascii')
        connection = http.client.HTTPConnection(host, port, timeout=40)
        sock = socket.create_connection((address, port), timeout=40)
        try:
            if parts.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            connection.sock = sock
            path = urlunsplit(('', '', parts.path or '/', parts.query, ''))
            connection.request('GET', path, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,text/plain', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader('Location')
                if not target:
                    raise ValueError('网页重定向缺少目标')
                url = urljoin(url, target)
                continue
            if response.status != 200:
                raise ValueError(f'网页返回 HTTP {response.status}；可能需要登录或不允许抓取，请直接发送正文')
            content_type = response.getheader('Content-Type', '').lower()
            if not (content_type.startswith('image/') if image else any(kind in content_type for kind in ('text/html', 'application/xhtml+xml', 'text/plain'))):
                raise ValueError('链接不是可直接提取的网页正文；请发送正文或文本文件')
            body = response.read(20_000_001)
            if len(body) > 20_000_000:
                raise ValueError('网页超过20MB，本次未收录')
            return url, body, content_type
        finally:
            connection.close()
            sock.close()
    raise ValueError('网页重定向次数过多')

def image_texts(body, final_url):
    """仅下载存档文章配图并登记路径（不做OCR，不做视觉分析）。"""
    charset = re.search(br'charset=[\"\']?([a-zA-Z0-9_-]+)', body[:4096]) if isinstance(body, bytes) else None
    encoding = charset[1].decode('ascii') if charset else 'utf-8'
    tree = html.fromstring(body, parser=html.HTMLParser(encoding=encoding))
    roots = tree.xpath('//*[@id="js_content"]') or tree.xpath('//article') or tree.xpath('//main')
    root = roots[0] if roots else tree
    urls = list(dict.fromkeys(urljoin(final_url, image.get('data-src') or image.get('src') or '')
                            for image in root.xpath('.//img')
                            if urlsplit(urljoin(final_url, image.get('data-src') or image.get('src') or '')).scheme in ('http', 'https') and (image.get('data-src') or image.get('src'))))
    notes, sections = [], []
    titles = tree.xpath('//meta[@property="og:title"]/@content') or tree.xpath('//title/text()')
    image_title = processor.layout.clean_title(titles[0] if titles else urlsplit(final_url).hostname)
    folder = BASE / '05_原始素材' / '网页图片' / (image_title + '（' + processor.layout.article_id(final_url)[:8] + '）')
    if urls:
        if (BASE / '05_原始素材').is_symlink() or (BASE / '05_原始素材/网页图片').is_symlink() or folder.is_symlink():
            raise ValueError('素材目录为软链接，已停止')
        assert_safe(folder)
        folder.mkdir(parents=True, exist_ok=True)
    if len(urls) > 40:
        notes.append(f'文章共{len(urls)}张图片，本次存档前40张，其余图片尚未归档。')
    for index, url in enumerate(urls[:40], 1):
        try:
            _, pixels, content_type = fetch(url, image=True)
            suffix = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/gif': '.gif'}.get(content_type.split(';')[0], '.img')
            path = folder / (hashlib.sha256(pixels).hexdigest()[:24] + suffix)
            if path.is_symlink():
                raise ValueError('图片文件是软链接')
            if not path.exists():
                fd, temp = tempfile.mkstemp(prefix='.download-', dir=folder)
                try:
                    with os.fdopen(fd, 'wb') as f:
                        f.write(pixels)
                        f.flush()
                        os.fsync(f.fileno())
                    os.link(temp, path)
                finally:
                    os.unlink(temp)
            sections.append(f'图片来源：{url}\n![[{path.relative_to(BASE)}]]\n')
        except Exception as error:
            notes.append(f'图片{index}未完成存档：{error}')
    if urls:
        notes.insert(0, '图片已按文章归档，未做OCR识别与视觉分析（按约定仅对应原文）。')
    return sections, notes, len(urls), 0


def extract_source_metadata(body, final_url):
    """Use only publisher/author declarations in the fetched page, never model guesses."""
    charset = re.search(br'charset=[\"\']?([a-zA-Z0-9_-]+)', body[:4096]) if isinstance(body, bytes) else None
    encoding = charset[1].decode('ascii') if charset else 'utf-8'
    tree = html.fromstring(body, parser=html.HTMLParser(encoding=encoding))
    def first(expressions):
        for expression in expressions:
            values = tree.xpath(expression)
            if isinstance(values, str):
                values = [values]
            for value in values:
                text = ' '.join(str(value).split())[:200]
                if text:
                    return text
        return ''
    is_weixin = urlsplit(final_url).hostname == 'mp.weixin.qq.com'
    source = first(['string(//*[@id="js_name"])']) if is_weixin else ''
    source = source or first(['//meta[@property="og:site_name"]/@content', '//meta[@name="application-name"]/@content'])
    author = first(['string(//*[@id="js_author_name_text"])', 'string(//*[@id="js_author_name"])']) if is_weixin else ''
    author = author or first(['//meta[@name="author"]/@content', '//meta[@property="article:author"]/@content', '//meta[@property="og:article:author"]/@content'])
    return {'source_name': source, 'author': author}


def extract_article(body, final_url):
    """Keep paragraph/image order from the article DOM, without OCR."""
    charset = re.search(br'charset=[\"\']?([a-zA-Z0-9_-]+)', body[:4096]) if isinstance(body, bytes) else None
    encoding = charset[1].decode('ascii') if charset else 'utf-8'
    tree = html.fromstring(body, parser=html.HTMLParser(encoding=encoding))
    roots = tree.xpath('//*[@id="js_content"]') or tree.xpath('//article') or tree.xpath('//main')
    if not roots:
        record = trafilatura.bare_extraction(body, url=final_url, include_comments=False,
                                             include_tables=True, with_metadata=True)
        text = record.text or '' if record else ''
        title = (record.title if record else None) or urlsplit(final_url).hostname
        return title, text, ['页面未识别到独立文章容器，原文完整性待复核；未声称已保存完整图文'], 0
    root = roots[0]
    names = tree.xpath('//meta[@property="og:title"]/@content') or tree.xpath('//title/text()')
    title = names[0].strip() if names else urlsplit(final_url).hostname
    sections, notes, count, _ = image_texts(body, final_url)
    images = {}
    for section in sections:
        match = re.search(r'图片来源：([^\n]+)\n!\[\[([^\]]+)\]\]', section)
        if match:
            images[match[1]] = match[2]

    def markdown(node):
        tag = str(node.tag).lower()
        if tag in ('script', 'style', 'noscript', 'iframe'):
            return ''
        if tag == 'img':
            src = urljoin(final_url, node.get('data-src') or node.get('src') or '')
            return '\n\n![[%s]]\n\n' % images[src] if src in images else '\n\n> 图片未保存：%s\n\n' % src
        if tag == 'br':
            return '\n'
        text = node.text or ''
        for child in node:
            text += markdown(child) + (child.tail or '')
        if tag == 'a' and node.get('href'):
            href = urljoin(final_url, node.get('href'))
            if urlsplit(href).scheme in ('http', 'https') and text.strip():
                return '['+text.strip()+']('+href+')'
        if tag in ('strong', 'b') and text.strip():
            return '**'+text.strip()+'**'
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return '\n\n'+('#'*int(tag[1]))+' '+text.strip()+'\n\n'
        if tag == 'li':
            return '\n- '+text.strip()+'\n'
        if tag in ('p', 'div', 'section', 'article', 'main', 'blockquote', 'ul', 'ol', 'tr'):
            return '\n\n'+text.strip()+'\n\n'
        if tag in ('td', 'th'):
            return text.strip()+' | '
        return text

    text = re.sub(r'\n[ \t]+\n', '\n\n', markdown(root))
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    errors = [note for note in notes if any(word in note for word in ('未完成', '尚未归档'))]
    return title, text, errors, count


def archive_article(url):
    cached = processor.layout.lookup(url)
    if cached:
        return processor.layout.result(cached)
    final_url, body, content_type = fetch(url)
    if 'text/plain' in content_type:
        text, title = body.decode('utf-8-sig'), urlsplit(final_url).hostname
        notes, count = [], 0
        source_metadata = {}
    else:
        title, text, notes, count = extract_article(body, final_url)
        source_metadata = extract_source_metadata(body, final_url)
    visible = re.sub(r'!\[\[[^\]]+\]\]', '', text)
    if len(visible.strip()) < 120:
        raise ValueError('正文不足，未生成完整文章；图片不能替代正文，请提供原文')
    signals = ('环境异常', '请完成安全验证', '访问过于频繁', 'verify you are human', 'enable javascript and cookies')
    if any(s in visible[:2000].lower() for s in signals):
        raise ValueError('网页返回验证或限制页面，未归档')
    result = processor.layout.publish(url, title=title, raw=text, image_errors=notes, raw_is_body=True, source_metadata=source_metadata)
    result['image_count'] = count
    result['image_notes'] = notes
    if notes:
        result['status'] = '原文已保存，图文完整性待复核'
    return result



#!/usr/bin/env python3
"""刘向：文章归档、同笔记整理及证据核验。Python 3.10+，macOS/Linux。"""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', default=os.environ.get('LIUXIANG_VAULT'))
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('init', help='初始化独立配置，不更改 Obsidian 或 Hermes 设置')
    p.add_argument('--backup-directory')
    p.add_argument('--topics', nargs='+', default=['AI前沿', 'AI应用', 'Agent', '技术架构', '产品运营', '内容创作', '商业观察', '个人成长'])
    p.add_argument('--timezone', default='Asia/Shanghai')
    sub.add_parser('doctor', help='检查依赖和知识库配置')
    p = sub.add_parser('archive', help='保存公开网页，不调用模型'); p.add_argument('url')
    p = sub.add_parser('import', help='导入用户提供的 UTF-8 Markdown 正文')
    p.add_argument('url'); p.add_argument('--file', required=True); p.add_argument('--title', required=True)
    p.add_argument('--source-name', default=''); p.add_argument('--author', default='')
    p = sub.add_parser('read', help='读取已归档原文及整理状态'); p.add_argument('url')
    p = sub.add_parser('apply', help='校验并保存 Hermes 生成的整理 JSON')
    p.add_argument('url'); p.add_argument('--file', required=True)
    p = sub.add_parser('verify-prepare', help='准备核验；可用 JSON 文件传入 claims')
    p.add_argument('url'); p.add_argument('--file')
    p = sub.add_parser('verify-save', help='校验真实网页短引文并保存核验结果'); p.add_argument('--file', required=True)
    args = parser.parse_args()
    if not args.vault:
        parser.error('请用 --vault 或 LIUXIANG_VAULT 指定知识库')
    os.environ['LIUXIANG_VAULT'] = args.vault
    from runtime import BASE, CONFIG, SETTINGS, assert_safe, topic_names
    from zoneinfo import ZoneInfo
    if args.action == 'init':
        ZoneInfo(args.timezone)
        topics = topic_names(args.topics)
        backup = Path(args.backup_directory).expanduser().absolute() if args.backup_directory else BASE.parent / (BASE.name + '-刘向备份')
        assert_safe(backup)
        if backup.resolve().is_relative_to(BASE):
            raise ValueError('备份目录必须在知识库之外')
        if CONFIG.exists():
            return {'ok': True, 'status': '已初始化，未覆盖现有配置', 'config': str(CONFIG)}
        # No pre-existing directories or properties are overwritten.
        for name in ('00_收件箱', '01_外部知识', '05_原始素材/网页图片', '_AI/刘向'):
            folder = BASE / name; assert_safe(folder); folder.mkdir(parents=True, exist_ok=True)
        conf = {'version': '0.1.0', 'timezone': args.timezone, 'topics': topics,
                'tag_aliases': {}, 'backup_directory': str(backup.resolve())}
        with CONFIG.open('x', encoding='utf-8') as stream:
            json.dump(conf, stream, ensure_ascii=False, indent=2)
        return {'ok': True, 'status': '已初始化', 'config': str(CONFIG), 'backup_directory': str(backup)}
    if not SETTINGS:
        raise ValueError('请先运行 init')
    if args.action == 'doctor':
        import lxml, trafilatura
        return {'ok': True, 'python': sys.version.split()[0], 'vault': str(BASE), 'config': str(CONFIG),
                'backup_directory': SETTINGS['backup_directory'], 'topics': SETTINGS['topics'],
                'model': '复用宿主 Agent，不设置独立模型', 'dependencies': {'lxml': lxml.__version__, 'trafilatura': trafilatura.__version__}}
    import note_layout as layout
    if args.action == 'archive':
        import collector
        return collector.archive_article(args.url)
    if args.action == 'import':
        old = layout.lookup(args.url)
        if old:
            return layout.result(old)
        body = Path(args.file).read_text(encoding='utf-8-sig')
        if not body.strip() or len(body) > 192000:
            raise ValueError('原文为空或超过192000字符，请分批导入')
        return layout.publish(args.url, title=args.title, raw=body, raw_is_body=True,
                              source_metadata={'source_name': args.source_name, 'author': args.author})
    if args.action == 'read':
        record = layout.lookup(args.url)
        if not record:
            raise ValueError('未找到文章，请先 archive 或 import')
        return {'ok': True, 'title': record['title'], 'raw': record['raw'], 'topics': SETTINGS['topics'],
                'organized': bool(record.get('data')), 'result': str(BASE / record['path'])}
    if args.action == 'apply':
        import processor
        record = layout.lookup(args.url)
        if not record:
            raise ValueError('请先归档原文')
        if record.get('data'):
            return layout.result(record)
        data = processor.validate(json.loads(Path(args.file).read_text(encoding='utf-8')))
        return layout.publish(args.url, data=data)
    import verification
    if args.action == 'verify-prepare':
        params = {'url': args.url}
        if args.file:
            params['claims'] = json.loads(Path(args.file).read_text(encoding='utf-8'))['claims']
        return verification.prepare(params)
    return verification.save(json.loads(Path(args.file).read_text(encoding='utf-8')))


if __name__ == '__main__':
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except Exception as error:
        print(json.dumps({'ok': False, 'status': '未完成', 'message': str(error)}, ensure_ascii=False))
        sys.exit(1)

"""Explicit vault selection and namespaced configuration; no host configuration edits."""
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo


def assert_safe(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError('目标或上级目录是软链接，请改用真实路径：' + str(item))


def topic_names(topics):
    if not isinstance(topics, list) or not topics:
        raise ValueError('topics 必须是非空领域列表')
    for name in topics:
        if not isinstance(name, str) or not name.strip() or len(name) > 50 or any(c in name for c in '/\\\n\r:*?"<>|') or name in ('.', '..'):
            raise ValueError('领域名不能包含路径符号或空值')
    return list(dict.fromkeys(topics))


value = os.environ.get('LIUXIANG_VAULT')
if not value:
    raise ValueError('需要 --vault 或 LIUXIANG_VAULT 指定知识库')
BASE = Path(value).expanduser().resolve()
assert_safe(BASE)
BASE = BASE.resolve()
CONFIG = BASE / '_AI/刘向/config.json'
assert_safe(CONFIG)
SETTINGS = json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.exists() else {}
if SETTINGS:
    topic_names(SETTINGS['topics'])
    ZoneInfo(SETTINGS.get('timezone', 'Asia/Shanghai'))
    backup = Path(SETTINGS['backup_directory']).expanduser().absolute()
    assert_safe(backup)
    if backup.resolve().is_relative_to(BASE):
        raise ValueError('备份目录必须位于知识库之外')

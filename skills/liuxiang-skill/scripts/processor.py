import re
import note_layout as layout
from runtime import SETTINGS as _SETTINGS
FIELDS = ['一句话结论', '原文核心信息', '关键数据与案例', '待核实', 'AI分析', '可二创方向', '推荐标签']
def validate(data):
    if not isinstance(data, dict) or not set(FIELDS + ['内容类型']).issubset(data) or set(data) - set(FIELDS) - {'内容类型'}:
        raise ValueError('模型结果字段不完整')
    for key in FIELDS[:-2]:
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError('模型结果存在空字段：' + key)
    for key in FIELDS[-2:]:
        if not isinstance(data[key], list) or len(data[key]) > 3:
            raise ValueError('模型结果列表格式错误：' + key)
        if any(not isinstance(item, str) or not item.strip() for item in data[key]):
            raise ValueError('模型结果列表包含空项：' + key)
    # 严格白名单保证标签没有 emoji 或 Markdown 装饰。
    data['推荐标签'] = list(dict.fromkeys(
        re.sub(r'[^\u3400-\u4dbf\u4e00-\u9fffA-Za-z0-9 _-]', '', tag).strip()
        for tag in data['推荐标签']))
    data['推荐标签'] = [tag for tag in data['推荐标签'] if tag][:3]
    if len(data['一句话结论']) > 100:
        raise ValueError('一句话结论不能超过100字')
    if _SETTINGS.get('topics'):
        aliases = _SETTINGS.get('tag_aliases', {})
        normalized = list(dict.fromkeys(aliases.get(t, t) for t in data['推荐标签']))
        candidates = [t for t in normalized if t not in _SETTINGS['topics']]
        data['推荐标签'] = [t for t in normalized if t in _SETTINGS['topics']][:3]
        if candidates:
            data['AI分析'] += '\n\n候选标签（尚未加入词表）：' + '、'.join(candidates)
    if data.get('内容类型', '观点分析') not in layout.TYPES:
        raise ValueError('内容类型不在固定词表中')
    data.setdefault('内容类型', '观点分析')
    return data


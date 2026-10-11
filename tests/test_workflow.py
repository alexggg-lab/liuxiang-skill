"""Offline behavioral tests. Uses isolated vaults and simulated HTTP fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/liuxiang-skill/scripts'
URL = 'https://example.org/articles/demo'
DATA = {'一句话结论': '作者认为保存原文有助于追溯知识来源。', '原文核心信息': '- 保存来源与原文。',
        '关键数据与案例': '原文未提供具体数据。', '待核实': '效果未经外部核验。',
        'AI分析': '保留证据便于复查，这是 AI 建议。', '可二创方向': ['记录自己的实践'],
        '推荐标签': ['AI应用'], '内容类型': '教程指南'}

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.vault = self.home / 'vault'
        self.call('init')
        self.raw = self.home / 'raw.md'
        self.raw.write_text('这是一篇虚构示例。\n\n原文与分析需要分开保存。\n\n![[05_原始素材/网页图片/demo.png]]\n', encoding='utf-8')
        self.datafile = self.home / 'data.json'; self.datafile.write_text(json.dumps(DATA, ensure_ascii=False))
    def call(self, *args, ok=True):
        proc = subprocess.run([sys.executable, str(SCRIPTS/'liuxiang.py'), '--vault', str(self.vault), *args], capture_output=True, text=True)
        result = json.loads(proc.stdout)
        self.assertEqual(proc.returncode == 0, ok, result)
        return result
    def ingest(self, url=URL):
        return self.call('import', url, '--file', str(self.raw), '--title', '虚构示例', '--source-name', '示例出版社')
    def apply(self, url=URL, ok=True):
        return self.call('apply', url, '--file', str(self.datafile), ok=ok)
    def modules(self):
        os.environ['LIUXIANG_VAULT'] = str(self.vault)
        sys.path.insert(0, str(SCRIPTS))
        for name in ('runtime', 'note_layout', 'processor', 'collector', 'verification'):
            sys.modules.pop(name, None)
        import collector, verification
        return collector, verification
    def test_archive_organize_deduplicate_and_raw(self):
        receipt = self.ingest(); old = Path(receipt['result'])
        note = Path(self.apply()['result'])
        self.assertFalse(old.exists())
        self.assertEqual(note.read_text().split('## 完整图文原文\n\n',1)[1].rstrip(), self.raw.read_text().rstrip())
        self.assertEqual(self.ingest()['result'], str(note))
        self.assertEqual(len(list(self.vault.rglob('*.md'))), 1)
        self.assertTrue(list((self.home/'vault-刘向备份').rglob('*.md')))
    def test_manual_properties_personal_and_multiline_tags(self):
        note = Path(self.ingest()['result'])
        text = note.read_text().replace('来源: "示例出版社"', '来源: "我修改的来源"')
        import re
        text = re.sub(r'^tags:.*$', 'tags:\n  - 旧标签', text, flags=re.M)
        text = text.replace('<!-- personal:start -->\n', '<!-- personal:start -->\n我的判断。\n')
        note.write_text(text)
        text = Path(self.apply()['result']).read_text()
        self.assertIn('我修改的来源', text); self.assertIn('我的判断。', text)
        self.assertNotIn('  - 旧标签', text)
    def test_manual_body_not_overwritten(self):
        note = Path(self.ingest()['result']); note.write_text(note.read_text()+'\n手动新增正文。')
        before = note.read_bytes(); self.apply(ok=False); self.assertEqual(note.read_bytes(), before)
    def test_same_title_different_url(self):
        self.ingest(); self.apply()
        self.ingest(URL+'2'); self.apply(URL+'2')
        self.assertEqual(len(list((self.vault/'01_外部知识').rglob('*.md'))), 2)
    def test_invalid_data_preserves_raw(self):
        note = Path(self.ingest()['result']); before = note.read_bytes()
        self.datafile.write_text('{}'); self.apply(ok=False); self.assertEqual(note.read_bytes(), before)
    def test_init_idempotent_and_namespaced(self):
        config = self.vault/'_AI/刘向/config.json'; before = config.read_bytes()
        self.call('init'); self.assertEqual(config.read_bytes(), before)
        self.assertFalse((self.vault/'_AI/pipeline.json').exists())
    def test_unsafe_topic_and_symlink_rejected(self):
        self.call('init', '--topics', '../outside', ok=False)
        outside = self.home/'outside'; outside.mkdir()
        (self.vault/'00_收件箱').rmdir(); (self.vault/'00_收件箱').symlink_to(outside)
        self.call('import', URL, '--file', str(self.raw), '--title', 'demo', ok=False)
        self.assertEqual(list(outside.iterdir()), [])
    def test_collector_metadata_image_order_and_cache(self):
        collector, _ = self.modules()
        body = '<html><title>示例</title><meta property="og:site_name" content="示例站"><article><p>第一段</p><img src="https://example.org/a.png"><p>第二段</p></article></html>'.encode()
        with patch.object(collector, 'fetch', return_value=('https://example.org/a.png', b'image-fixture', 'image/png')):
            title, raw, errors, count = collector.extract_article(body, URL)
        self.assertLess(raw.index('第一段'), raw.index('![[')); self.assertLess(raw.index('![['), raw.index('第二段'))
        self.assertEqual(count, 1); self.assertEqual(errors, [])
        self.assertEqual(collector.extract_source_metadata(body, URL)['source_name'], '示例站')
        self.ingest()
        with patch.object(collector, 'fetch', side_effect=AssertionError('must not fetch cached article')):
            self.assertTrue(collector.archive_article(URL)['ok'])
    def test_verification_partial_evidence_raw_and_replay(self):
        self.ingest(); note = Path(self.apply()['result'])
        collector, verification = self.modules()
        req = verification.prepare({'url': URL, 'claims': ['示例机构发布了一个新产品', '该产品效果尚未确认']})
        rows = [{'id': '1', 'verdict': '支持', 'reason': '模拟页面包含发布声明，仅测试保存行为。', 'queries': ['示例产品 发布'], 'evidence': [{'url': 'https://example.org/evidence', 'title': '模拟证据', 'excerpt': '示例机构今天正式发布了一个全新的演示产品。'}]},
                {'id': '2', 'verdict': '未确认', 'reason': '没有找到效果研究。', 'queries': ['示例产品 效果'], 'evidence': []}]
        original = note.read_text().split('## 完整图文原文\n\n',1)[1]
        with patch.object(collector, 'fetch', return_value=('https://example.org/evidence', '<article>示例机构今天正式发布了一个全新的演示产品。</article>'.encode(), 'text/html')):
            result = verification.save({'token': req['token'], 'results': rows})
        self.assertEqual(result['verification_status'], '部分核验')
        self.assertEqual(note.read_text().split('## 完整图文原文\n\n',1)[1], original)
        with self.assertRaises(ValueError): verification.save({'token': req['token'], 'results': rows})
    def test_fabricated_evidence_rejected(self):
        self.ingest(); note = Path(self.apply()['result']); before = note.read_bytes()
        collector, verification = self.modules()
        req = verification.prepare({'url': URL, 'claims': ['示例机构发布了一个新产品']})
        rows = [{'id': '1', 'verdict': '支持', 'reason': '声称存在', 'queries': ['产品发布'], 'evidence': [{'url': 'https://example.org/evidence', 'title': '示例', 'excerpt': '示例机构今天正式发布了一个全新的演示产品。'}]}]
        with patch.object(collector, 'fetch', return_value=('https://example.org/evidence', b'<article>unrelated content</article>', 'text/html')):
            with self.assertRaises(ValueError): verification.save({'token': req['token'], 'results': rows})
        self.assertEqual(note.read_bytes(), before)
    def test_private_url_denied(self):
        collector, _ = self.modules()
        with self.assertRaises(ValueError): collector.public_target('http://127.0.0.1/')

if __name__ == '__main__': unittest.main()

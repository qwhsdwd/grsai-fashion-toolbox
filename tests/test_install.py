import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.comfy = Path(self.temp.name) / 'ComfyUI 测试目录'
        self.comfy.mkdir()
        (self.comfy / 'main.py').write_text('# ComfyUI fixture', encoding='utf-8')
        (self.comfy / 'folder_paths.py').write_text('# fixture', encoding='utf-8')

    def install(self, path=None):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/install.py'), '--comfy-root', str(path or self.comfy), '--skip-config'],
                              capture_output=True, text=True, encoding='utf-8')

    def test_fresh_install_creates_nodes_workflows_and_blank_private_config(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        node = self.comfy / 'custom_nodes/ComfyUI-Cloud-Fashion'
        self.assertTrue((node / '__init__.py').exists())
        self.assertEqual(json.loads((node / 'config.local.json').read_text(encoding='utf-8'))['api_key'], '')
        workflows = self.comfy / 'user/default/workflows/我的工具箱/05 线上工作流'
        self.assertEqual(len(list(workflows.glob('*.json'))), 3)
        self.assertFalse((node / 'test_client.py').exists())

    def test_reinstall_preserves_recipients_credentials_and_edited_workflow(self):
        node = self.comfy / 'custom_nodes/ComfyUI-Cloud-Fashion'
        node.mkdir(parents=True)
        config = node / 'config.local.json'
        config.write_text('{"api_key":"recipient-secret","base_url":"https://grsaiapi.com"}', encoding='utf-8')
        flows = self.comfy / 'user/default/workflows/我的工具箱/05 线上工作流'
        flows.mkdir(parents=True)
        edited = flows / '02 人物换装＋姿势参考－GPT Image 2.5（线上）.json'
        edited.write_text('{"my_edit":true}', encoding='utf-8')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('recipient-secret', config.read_text(encoding='utf-8'))
        self.assertEqual(edited.read_text(encoding='utf-8'), '{"my_edit":true}')
        self.assertNotIn('recipient-secret', result.stdout + result.stderr)

    def test_windows_portable_parent_directory_is_recognized(self):
        result = self.install(self.comfy.parent)
        # The portable child is conventionally called ComfyUI.
        self.assertNotEqual(result.returncode, 0)
        self.comfy.rename(self.comfy.parent / 'ComfyUI')
        result = self.install(self.comfy.parent)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_directory_is_rejected_without_creating_node_files(self):
        invalid = self.comfy / 'unrelated'
        invalid.mkdir()
        result = self.install(invalid)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((invalid / 'custom_nodes').exists())


if __name__ == '__main__':
    unittest.main()

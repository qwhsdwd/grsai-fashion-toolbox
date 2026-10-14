"""Install the bundled nodes and workflows into an existing ComfyUI."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RUNTIME_FILES = ('__init__.py', 'client.py', 'prompts.py', 'configure.py',
                 'config.example.json', 'requirements.txt', 'README.md', '.gitignore')


def comfy_directory(value):
    root = Path(value.strip().strip('"').strip("'")).expanduser().resolve()
    if root.name == 'custom_nodes':
        root = root.parent
    if not (root / 'main.py').is_file() and (root / 'ComfyUI/main.py').is_file():
        root = root / 'ComfyUI'
    if not (root / 'main.py').is_file() or not (root / 'folder_paths.py').is_file():
        raise ValueError('请选择包含 main.py、folder_paths.py 的 ComfyUI 目录，或 Windows 便携包的上级目录。')
    return root


def install_into(root, payload=None):
    root = comfy_directory(str(root))
    if payload is None:
        choices = (ROOT / 'ComfyUI-Cloud-Fashion', ROOT.parent / 'assets/ComfyUI-Cloud-Fashion', ROOT)
        payload = next((p for p in choices if (p / '__init__.py').is_file()), None)
    if payload is None or not (payload / 'client.py').is_file():
        raise ValueError('安装资源不完整，请重新解压整个分享包。')
    target = root / 'custom_nodes/ComfyUI-Cloud-Fashion'
    if target.is_symlink():
        raise ValueError('该节点目录是符号链接。请由 Codex 核对现有源码位置后更新，避免覆盖其他项目。')
    target.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_FILES:
        source = payload / name
        if source.is_file() and source.resolve() != (target / name).resolve():
            shutil.copy2(source, target / name)
    config = target / 'config.local.json'
    if not config.exists():
        with config.open('x', encoding='utf-8') as handle:
            json.dump({'api_key': '', 'base_url': 'https://grsaiapi.com'}, handle, indent=2)
            handle.write('\n')
        config.chmod(0o600)
    flows = root / 'user/default/workflows/我的工具箱/05 线上工作流'
    flows.mkdir(parents=True, exist_ok=True)
    bundled_flows = target / 'workflows'
    bundled_flows.mkdir(exist_ok=True)
    installed, preserved = 0, 0
    for source in sorted((payload / 'workflows').glob('*.json')):
        if source.name.endswith('_api.json'):
            continue
        if source.resolve() != (bundled_flows / source.name).resolve():
            shutil.copy2(source, bundled_flows / source.name)
        destination = flows / source.name
        if destination.exists():
            preserved += 1
        else:
            shutil.copy2(source, destination)
            installed += 1
    return {'node_directory': str(target), 'workflows_directory': str(flows),
            'installed_workflows': installed, 'preserved_workflows': preserved,
            'config_file': str(config)}


def main():
    parser = argparse.ArgumentParser(description='安装 GrsAI 线上服装工具箱。需要已安装的 ComfyUI；不会提交生成任务。')
    parser.add_argument('--comfy-root')
    parser.add_argument('--skip-config', action='store_true', help='只安装；稍后在私有配置文件填写 Key')
    args = parser.parse_args()
    value = args.comfy_root or input('输入或拖入 ComfyUI 文件夹路径：')
    result = install_into(value)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.skip_config:
        subprocess.run([sys.executable, str(Path(result['node_directory']) / 'configure.py')], check=True)
    print('安装完成。重启 ComfyUI，刷新页面，在「我的工具箱 → 05 线上工作流」打开工作流。')
    print('先上传自己的素材，再运行。未安装 ComfyUI 时，请让 Codex 先协助安装。')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('安装未完成：' + str(error), file=sys.stderr)
        raise SystemExit(1)

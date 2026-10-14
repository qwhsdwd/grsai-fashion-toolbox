"""Configure a recipient's own GrsAI key without echoing it to the terminal."""
import argparse
import getpass
import json
import os
from pathlib import Path

from client import CloudError, read_credentials, save_json

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='配置 GrsAI Key；不会提交生成任务。')
    parser.add_argument('--check', action='store_true', help='只检查配置格式，不显示 Key，不联网')
    args = parser.parse_args()
    path = ROOT / 'config.local.json'
    if args.check:
        base, _ = read_credentials(path)
        print(f'配置格式正确；接口：{base}。此检查不代表远端 Key 已通过认证。')
        return
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    print('GrsAI 官网：https://grsai.com/ → 登录控制台 → API Key。')
    print('1. 全球节点 https://grsaiapi.com')
    print('2. 国内节点 https://grsai.dakka.com.cn')
    choice = input('选择节点 [1/2，默认1]：').strip() or '1'
    if choice not in ('1', '2'):
        raise CloudError('请选择1或2。')
    key = getpass.getpass('粘贴你自己的 GrsAI Key（输入不会显示；留空保留已配置的 Key）：').strip()
    key = key or previous.get('api_key', '')
    if not key:
        raise CloudError('尚未填写 Key。也可以用编辑器打开 config.local.json 私下填写。')
    base = 'https://grsaiapi.com' if choice == '1' else 'https://grsai.dakka.com.cn'
    save_json(path, {'api_key': key, 'base_url': base})
    print(f'已保存到：{path}。重启 ComfyUI 后即可使用。没有调用收费接口。')
    if os.environ.get('GRSAI_API_KEY') or os.environ.get('GRSAI_BASE_URL'):
        print('注意：当前环境中的 GRSAI_API_KEY / GRSAI_BASE_URL 会优先于文件配置。')


if __name__ == '__main__':
    try:
        main()
    except (CloudError, OSError, ValueError) as error:
        print('配置未完成：' + str(error))
        raise SystemExit(1)

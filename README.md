# GrsAI 线上服装工具箱 · Codex Skill

把这个仓库链接发给自己的 **Codex**，让它协助安装 ComfyUI 节点、导入工作流，并引导你配置**自己的 GrsAI Key**。

**仓库链接：https://github.com/qwhsdwd/grsai-fashion-toolbox**

## 直接把这段话发给 Codex

```text
请读取 https://github.com/qwhsdwd/grsai-fashion-toolbox 的 README.md 和 SKILL.md，
把本仓库安装为当前 Codex 的 grsai-fashion-toolbox Skill，
然后按 Skill 帮我找到正在使用的 ComfyUI，安装随附节点并导入三条工作流。
请引导我在本机私下填写自己的 GrsAI Key，不要让我把 Key 发到聊天里。
保留我已有的工作流和配置，先完成不收费的安装与检查。
如果我尚未安装 ComfyUI，请先协助安装适合当前系统的版本。
生成图片或视频等我提供素材和要求后再运行。
```

Codex 会先阅读仓库中的安装说明，再协助执行。需要能访问 GitHub、操作本机文件与终端的 Codex 环境；如果当前环境没有这些权限，可下载仓库后在本机 Codex 中继续。

## 包含什么

| 工作流 | 作用 | 线上模型 |
| --- | --- | --- |
| 01 文生图 | 输入描述，生成图片 | `gpt-image-2.5` |
| 02 人物换装＋姿势参考 | 人物图＋目标衣服，可加下装和姿势图 | `gpt-image-2.5` |
| 03 图片＋关键词＋姿势参考生视频 | 用确认后的图片与动作描述生成视频 | `minimax-h3` |

AI 生成调用 GrsAI，本机负责上传、预览和保存；无需下载本地图片或视频生成模型。仓库不包含完整 ComfyUI、API Key、账号余额、人物照片或收费样片。

任务编号自动管理：**换素材或参数会新建任务；相同内容同批次会复用结果或续查**。想用同样素材再生成一版，把节点中的「重新生成批次」加1。

## 安装后在哪里找

工作流浏览器：

**我的工具箱 → 05 线上工作流**

单独添加节点：双击画布搜索「线上人物换装」，或进入 **我的工具箱 → 线上模型**。

如果列表未显示，直接把安装目录 `custom_nodes/ComfyUI-Cloud-Fashion/workflows` 中的 JSON 拖入 ComfyUI。分享版没有图片素材，换装和视频流程需先上传自己的图片。

## 自己的 Key 怎么填

1. 在 [GrsAI 官网](https://grsai.com/) 登录自己的账号，在控制台获取自己的 API Key。
2. 安装后运行节点目录中的 `configure.py`，按不回显的提示输入；或者私下编辑同目录的 `config.local.json`。
3. 等当前队列完成，保存工作流，再重启 ComfyUI 并刷新页面。

配置格式：

```json
{
  "api_key": "填写你自己的GrsAI Key",
  "base_url": "https://grsaiapi.com"
}
```

支持全球节点 `https://grsaiapi.com` 和国内节点 `https://grsai.dakka.com.cn`。网站首页 `https://grsai.com/` 不能作为 API 根地址；不要在地址后追加 `/v1`。

环境变量 `GRSAI_API_KEY` / `GRSAI_BASE_URL` 优先于节点目录配置；缺少节点目录配置时可读取旧版 `~/.config/grsai/credentials.json`。Key 不写入工作流，也不需要提交到 GitHub 或发给 Codex。

本工具仅适配 **GrsAI 原生异步接口**，不能换成任意其他供应商的 Key 就使用。安装与格式检查不产生生成费用；点击运行后按自己的 GrsAI 账号规则计费。格式检查不代表远端 Key、余额或模型权限已经通过验证。

## 手动安装

若不使用 Codex 自动协助，可克隆本仓库，并在仓库根目录运行：

```bash
python scripts/install.py --comfy-root "/实际/ComfyUI目录" --skip-config
```

macOS / Linux 也可使用 `python3`。Windows 便携版可用包内 `python_embeded/python.exe`；`--comfy-root` 可传入包含 `main.py`、`folder_paths.py` 的目录，或 `ComfyUI_windows_portable` 上级目录。

安装器会保留已有 Key 与同名工作流。随后在节点目录执行 `configure.py`，或编辑私有配置文件；配置格式检查用 `configure.py --check`。没有安装 ComfyUI 时，请先让 Codex 协助安装。

若只安装 Skill，将整个仓库放入当前 `CODEX_HOME` 下的 `skills/grsai-fashion-toolbox`；未设置 `CODEX_HOME` 时通常为 `~/.codex/skills/grsai-fashion-toolbox`。确保该文件夹第一层有 `SKILL.md`，之后新开一个 Codex 聊天使用：

```text
请用 $grsai-fashion-toolbox 帮我安装和配置线上服装工具箱。
```

## 教程、源码和检查

- [完整中文教程](references/用户教程.md)：连线、姿势图、自动任务、视频和常见错误。
- [给 Codex 的 Skill 指令](SKILL.md)。
- [安装器](scripts/install.py) 与 [节点源码](assets/ComfyUI-Cloud-Fashion)。
- [离线下载与发布说明](https://github.com/qwhsdwd/grsai-fashion-toolbox/releases)。

运行不收费的本地检查：

```bash
python -X utf8 -m unittest discover -s tests -p "test_*.py"
```

33项检查覆盖自动任务、旧任务迁移、重复提交保护、锁、配置读取和安装器。三条完整工作流已在 macOS ComfyUI 的隔离 CPU 后台使用缓存样本验收；本次发布不额外提交收费生成。Windows 锁机制有模拟测试，Windows / Linux 的完整 ComfyUI 使用仍需实际环境验证。

遇到问题可提交 [Issue](https://github.com/qwhsdwd/grsai-fashion-toolbox/issues)，附系统、ComfyUI 版本和不含 Key 的错误日志。共享时转发本仓库或发布包，保留自己的私有配置与任务记录。

采用 [MIT License](LICENSE)。本项目是 ComfyUI 工作流与节点封装，模型服务由 GrsAI 提供。

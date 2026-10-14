---
name: grsai-fashion-toolbox
description: 协助用户安装、配置和使用 GrsAI ComfyUI 线上服装工具箱，包含文生图、人物换装与姿势参考、图片生视频，以及自动任务续查。适用于用户拿到本 Skill 或工作流后希望使用自己的 GrsAI Key 在 Windows、macOS 或 Linux 上运行。
---

# GrsAI 线上服装工具箱

帮助用户把随附的节点与三条工作流安装到正在使用的 ComfyUI，填写自己的 GrsAI Key，完成导入和检查。资源全部在本 Skill 中，不依赖原作者电脑或另一个 Skill。

仓库：https://github.com/qwhsdwd/grsai-fashion-toolbox 。用户只给出仓库链接并要求安装时，先读取 README 与本文件，再将整个仓库安装到当前 CODEX_HOME 下的 `skills/grsai-fashion-toolbox`（未设置时为 `~/.codex/skills/grsai-fashion-toolbox`）。已有同名 Skill 时先检查本地修改，再更新；不要覆盖私有配置。之后继续完成用户已授权的节点安装与配置引导，不必等下一轮重新调用 Skill。

先读 [用户教程](references/用户教程.md) 获取安装入口、工作流位置和操作方法。节点源码位于 `assets/ComfyUI-Cloud-Fashion`；安装器是 `scripts/install.py`。

## 安装与配置

1. 定位用户当前使用的 ComfyUI 根目录，确认包含 `main.py` 和 `folder_paths.py`。结合正在运行的进程、工作目录、启动参数与目录判断，保留已指定的实例。无法唯一确定时再询问目录。Windows 便携版可传入其上级目录。
2. 如果尚未安装 ComfyUI，先说明本 Skill 包含节点而非完整 ComfyUI。优先按用户已有安装方式协助；仅为这些线上节点运行时可以使用 CPU 模式，无需下载本地生成模型。安装 ComfyUI 另参照当时的官方文档，不在此包内猜测固定版本。
3. 用可用的 Python 执行 `scripts/install.py --comfy-root "实际目录" --skip-config`。安装器保留用户已有 Key 与同名工作流，不覆盖其他节点。若目标是符号链接，检查其真实源码位置后做针对性更新，不删除链接强装。
4. 引导用户访问 [GrsAI 官网](https://grsai.com/)，登录控制台后创建自己的 API Key。不要索要原作者的 Key。不要让用户把 Key 发到聊天、命令参数或工作流中。打开安装目录的 `config.local.json` 让用户私下填写，或让用户在自己的终端运行 `configure.py`，使用不回显的输入。不得读取或输出 Key 原文；验证仅报告是否配置。
5. `base_url` 只选 `https://grsaiapi.com` 或 `https://grsai.dakka.com.cn`，不填 `https://grsai.com/` 首页、不追加 `/v1`。环境变量优先于配置文件；若环境变量已设置，说明其优先级，不擅自删改。
6. 在运行队列空闲后重启对应的 ComfyUI 后台加载节点。优先使用该安装方式的正常重启入口，保留编辑中的工作流；运行中的任务先等待完成。刷新前保存未保存的编辑。

## 导入和验证

- 工作流目录：`user/default/workflows/我的工具箱/05 线上工作流`。也可拖入节点目录 `workflows` 内的 JSON；多用户或自定义 user-directory 安装优先使用拖入方式，或写入实际用户目录。
- 节点目录：「我的工具箱 → 线上模型」，名称为「01 线上文生图 · GPT Image 2.5」「02 线上人物换装 · GPT Image 2.5」「03 线上图生视频 · MiniMax H3」。
- 检查 `/object_info/CloudFashionTextToImage`、`CloudFashionOutfit`、`CloudFashionImageToVideo` 是否注册，并检查 `task_name` 默认「自动」、可选输入「重新生成批次」默认0。使用实际服务器地址，不假设8188一定是用户实例。
- 用安装节点目录中的 `configure.py --check` 做本地格式检查；它不联网、不输出 Key，也不证明远端认证或余额有效。
- 安装、导入、结构验证不需要收费生成。用户已要求生成或明确授权实测时才提交对应任务；不得把安装请求扩展为三条收费样片。已授权的任务不重复询问。

## 任务与输入规则

任务按实际图片内容和 API 参数生成指纹。换人物、服装、下装、姿势、提示词、尺寸、视频参数会自动建立新任务；同内容同批次复用或续查。`task_name` 是保留给旧工作流的兼容字段，无需用户手改。同内容想再出一版时增加「重新生成批次」。不要删除任务记录或自动增加批次来绕过提交状态不确定的保护。

人物图接 `person`，上衣或整套服装接 `garment`，独立下装接 `bottom`，姿势图接 `pose`。可选图只有连接后才会上传。分享版不含人物素材，先引导用户上传自己的图片。先确认换装图，再生成视频。H3 1080P最多10秒，480P/768P最多15秒；视频示例默认10秒1080P。

任务记录位于实际输出目录的 `线上工具箱/任务记录`。旧版相同内容的记录会迁移并保留原文件。超时或查询失败保持素材、参数、批次重跑；提交未取得ID时先核对控制台记录，不盲目重新收费提交。

## 交付

交付用户机器上的节点与工作流位置、已完成的检查、是否做过真实收费生成，以及简明下一步。共享时转发本仓库链接或发布 ZIP；不要把本地配置、Key、任务记录、私人图片和生成成品重新打进去。接口文档入口可能变化，按 [官网文档](https://grsai.com/dashboard/documents/chat) 和当前模型文档核对；本包仅适配 GrsAI 原生异步 `/v1/api/generate` 与 `/v1/api/result`，不声称兼容其他供应商。

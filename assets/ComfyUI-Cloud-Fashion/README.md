# GrsAI 线上服装工具箱

给 ComfyUI 增加文生图、人物换装与姿势参考、图片生视频三条线上工作流。图片使用 `gpt-image-2.5`，视频使用 `minimax-h3`。AI 生成由 GrsAI 完成，本机处理输入、预览和保存；需要能正常运行的 ComfyUI 和用户自己的 GrsAI Key。

官网：[grsai.com](https://grsai.com/)。登录后进入控制台创建自己的 API Key。本包适配 GrsAI 原生接口。

## 安装

使用分享包中的安装入口，或让 Codex 执行：

```bash
python install.py --comfy-root "/你的/ComfyUI目录" --skip-config
```

Windows 便携包也可以传入 `ComfyUI_windows_portable` 上级目录。安装程序只复制本节点和三条工作流，保留已有 Key 和同名工作流。

随后在 `ComfyUI/custom_nodes/ComfyUI-Cloud-Fashion` 目录执行 `python configure.py`，通过不回显的输入填写自己的 Key。也可以私下编辑该目录的 `config.local.json`：

```json
{
  "api_key": "填写你自己的GrsAI Key",
  "base_url": "https://grsaiapi.com"
}
```

支持全球节点 `https://grsaiapi.com` 和国内节点 `https://grsai.dakka.com.cn`。这里填接口根地址，不要填官网首页，也不要追加 `/v1`。

配置读取优先级：环境变量 `GRSAI_API_KEY` / `GRSAI_BASE_URL` → 节点目录 `config.local.json` → 旧版 `~/.config/grsai/credentials.json`。环境变量会优先于文件配置。

重启 ComfyUI，刷新页面，再打开：

**我的工具箱 → 05 线上工作流 → 02 人物换装＋姿势参考－GPT Image 2.5（线上）**

也可以把节点目录 `workflows` 下的 JSON 拖入 ComfyUI。节点搜索目录为「我的工具箱 → 线上模型」。

## 使用

| 工作流 | 必填内容 | 可选内容 |
| --- | --- | --- |
| 01 文生图 | 画面描述 `prompt` | 尺寸、完整构图 |
| 02 人物换装 | 人物图 → `person`；上衣或整套衣服 → `garment` | 独立裙子或裤子 → `bottom`；姿势图 → `pose` |
| 03 图片生视频 | 已确认的成品图 → `image`；动作描述 → `keywords` | 造型参考图 → `pose` |

分享版不含个人图片。换装和视频流程必须先上传自己的素材；可选图片只有接上线才会发送给 GrsAI。人物身份来自 `person`，衣服图只提供服装，姿势图只提供姿势。

视频默认10秒1080P；1080P最多10秒，480P/768P最多15秒。服务返回的实际尺寸、时长与效果以成品为准。先检查换装效果，再生成视频。

## 自动任务

`task_name` 保持「自动」即可，旧版编号也无需修改。任务根据实际图片内容、提示词、模型、尺寸与其他参数自动识别。

- 素材或参数变化：自动新建任务。
- 相同素材、参数和批次：复用已完成结果，或继续查询已有任务。
- 想用相同素材再出一版：把「重新生成批次」加1，再运行。
- 改回之前的内容且批次相同：复用对应旧结果。

旧版相同请求的记录会自动迁移并保留原文件。提交后没有拿到任务ID时会停止重复提交；先核对 GrsAI 控制台记录，再决定是否增加批次。连接建立前失败可以用相同内容重跑。切换接口节点后，已有任务须回到原节点查询。

结果和记录位于 ComfyUI 输出目录：`线上工具箱/01 文生图`、`02 人物换装`、`03 图片生视频`、`任务记录`。

## 分享与检查

只分享发布 ZIP 或 Skill ZIP。不要分享 `config.local.json`、旧版凭据、任务记录、已生成文件或私人素材。Key 保存在用户自己的电脑上，不写入工作流。

配置格式检查：`python configure.py --check`。该命令不显示 Key、不联网，不能证明远端 Key、余额或权限有效。点击运行会调用 GrsAI，费用以用户账号当时的规则为准。

接口采用 `POST /v1/api/generate` 提交、`GET /v1/api/result?id=...` 查询。不要把兼容 OpenAI 的图片接口地址填进来。若出现节点缺失，检查是否安装到了当前 ComfyUI 实例并重启；若工作流列表未出现，直接拖入 JSON。

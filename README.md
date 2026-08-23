# 南风 H3 V8.1 for ComfyUI / NanFeng H3 V8.1 for ComfyUI

> MiniMax H3 的非官方 ComfyUI 一体化节点。V8.1保留旧节点ID兼容，并加入连续Sigma一/二采、同一ModelPatcher与LoRA链、官方完整3D潜空间放大，以及智能分镜。
>
> An unofficial all-in-one ComfyUI node suite for MiniMax H3. V8.1 keeps legacy node IDs and adds a continuous first/second-pass Sigma trajectory, shared ModelPatcher/LoRA chain, official full 3D latent upscaling, and smart storyboards.

**非官方项目 / Unofficial project.** 不包含MiniMax、Seedance或第三方模型权重，也不代表任何官方合作。

## V8.1重点功能

- 搜索标题：`南风H3 V8.1 多参视频生成（6+4同LoRA）`
- 一采、二采共享同一主模型、完整LoRA链、强度和注意力链。
- 一条连续Sigma轨迹；支持手动完整Sigma和独立的一采手动Sigma开关。
- 保留官方完整3D潜空间放大和完整Temporal推理，不做非官方时间切块。
- 统一一采/二采MP尺寸，显示实际宽高和latent网格对齐。
- 参考图片最长边可选1280、1536、1920；智能分镜单张图片最大30 MiB。
- 智能分镜：独立视觉/语言模型、服务端`.env`、1–12段、精确时长、结果追加不覆盖。
- API仅对真实网络/上游临时故障重试；成功但本地解析失败不会重复付费生成。
- “你想拍什么”独立保存原始中文自然语言；生成的英文分镜不会覆盖它，只同步素材。
- 智能分镜内部支持换图、删除、拖动换位和`↔`点击换位，并同步固定`@图片N`槽位。
- 同画布从当前分镜开始依次提交当前及后续非空分镜。
- V8.1已移除FaceRefine执行链；旧序列化字段仅保留为惰性兼容占位。

## 安装或覆盖升级

进入`ComfyUI/custom_nodes/`：

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

已有旧版时，先确认ComfyUI没有运行任务并退出，然后将Release ZIP里的`nanfeng_prompt_nodes`覆盖到：

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes
```

V8.1安全升级ZIP不包含`.env`，所以不会删除已有API配置。首次安装时，把`.env.example`复制为`.env`并填写自己的配置。重启ComfyUI后用`Ctrl+F5`强制刷新。

## ComfyUI V15整合包（夸克网盘）

完整整合包较大，GitHub只托管节点源码和轻量升级ZIP。V15整合包下载：

- 夸克网盘：https://pan.quark.cn/s/e0a7dbfea025?pwd=kqtU
- 提取码：`kqtU`
- 分享目录：`comfyuiV15`

**覆盖规则：**整合包使用者下载后，请再使用本仓库最新Release中的`nanfeng_prompt_nodes`覆盖整合包内：

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes
```

这样可确保整合包中的节点升级为GitHub当前V8.1版本，同时不会覆盖用户自己的`.env`。

## 模型目录

```text
ComfyUI/models/diffusion_models/H3/       # H3 Ref2VA / FL2VA
ComfyUI/models/text_encoders/             # MiniMax H3 text encoder
ComfyUI/models/vae/                       # H3 video VAE + audio VAE
ComfyUI/models/latent_upscale_models/     # H3 3D latent upscaler
ComfyUI/models/loras/H3/                  # Optional matching H3 LoRAs
```

Ref2VA请匹配Ref2V LoRA；FL2VA请匹配FL2V LoRA。4步Turbo LoRA可先用强度1.0做固定Seed基线。

## 隐私与安全

仓库和Release不包含：模型、生成媒体、视觉分析缓存、测试缓存、作者`.env`或API Key。API Key只保存在节点目录服务端`.env`，不会写入工作流JSON。

---

# English

## Highlights

- Continuous first/second-pass Sigma trajectory with one shared final ModelPatcher, complete LoRA chain, strengths, and attention chain.
- Official full 3D latent upscaler and full temporal inference remain intact; no unofficial temporal chunking.
- Unified MP sizing with visible dimensions and latent-grid alignment.
- Smart storyboard with separate vision/text providers, server-side `.env`, exact duration, append-only results, and same-canvas sequential queueing.
- Genuine transient failures may retry; successful paid responses that fail local parsing are never generated again.
- The original natural-language idea is stored independently and is not overwritten by generated storyboard prompts; only media slots synchronize.
- Modal image replacement, deletion, drag reorder, click-to-swap, and stable `@Picture N` slot semantics.
- V8.1 has no FaceRefine execution path; legacy serialized fields are inert compatibility placeholders only.

## Installation

Clone directly into the required custom-node directory:

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

For an in-place upgrade, exit ComfyUI with no active jobs and overwrite the existing `ComfyUI/custom_nodes/nanfeng_prompt_nodes` with the Release ZIP folder. The upgrade archive excludes `.env`, preserving existing API credentials. First-time users should copy `.env.example` to `.env`.

## Full ComfyUI V15 bundle

The large full bundle is hosted on Quark Drive, while GitHub carries source and the lightweight upgrade archive:

- https://pan.quark.cn/s/e0a7dbfea025?pwd=kqtU
- Extraction code: `kqtU`
- Shared folder: `comfyuiV15`

After installing the full bundle, overwrite its `ComfyUI/custom_nodes/nanfeng_prompt_nodes` with the latest GitHub Release package.

## Privacy

No model weights, generated media, visual-analysis cache, live `.env`, or API keys are included. Credentials remain server-side in the recipient's own `.env` and are never serialized into workflow JSON.

## Historical versions

V6 remains available through tag and Release `v6.0.0`. V8.1 is the current main branch and latest Release.

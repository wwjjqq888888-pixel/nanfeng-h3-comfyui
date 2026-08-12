# 南风 H3 V4 for ComfyUI

[中文](#中文说明) · [English](README_EN.md)

> 面向 MiniMax H3 的中文优先 ComfyUI 自定义节点包：多模态参考、FL2VA、提示词列表、LoRA、可选注意力/缓存后端和可关闭的 Sigma 实验控制。

> **非官方项目 / Unofficial project.** 本仓库不隶属于 MiniMax 或 Comfy-Org，不包含任何模型权重。

## 中文说明

### 功能

- **南风 H3 多参视频生成 V4**：一个节点封装 MiniMax H3 的加载、条件构建、采样与音视频解码。
- **Ref2VA 多模态参考**：最多 9 张图片、3 个视频、3 段音频；槽位按顺序映射到 H3 原生参考标签。
- **FL2VA 模式**：文生视频、首帧图生视频、首尾帧三种模式互斥切换。
- **南风提示词列表**：多个非空提示词框各自生成独立顶层任务，并严格从上到下排队。
- **LoRA**：最多 3 组模型 LoRA；默认关闭。
- **可选加速**：支持已有环境中的 SageAttention、Sol-Attn 或 MiniMax H3 Block Cache（T8）；互斥规则由节点保护。
- **Sigma V4**：可关闭的 H3 Sigma Shift、低 Sigma 加密、手动 Sigma 和可选双阶段采样。
- **安全尺寸**：`原图比例`只读取首帧宽高比，像素预算仍由`百万像素`控制；参考图最长边限制为 1920，不放大较小原图。
- 保留 V1–V4 节点类 ID，尽量兼容旧工作流。

### 语言支持

- GitHub 首页、安装文档和发布说明：**中文 + English**。
- ComfyUI 节点界面：当前为**中文优先**，英文用户可配合 [English guide](README_EN.md) 使用。
- 提示词内容：可输入中文或英文；最终效果取决于 MiniMax H3 文本编码和模型能力。

### 环境要求

- 支持 MiniMax H3 原生节点的较新版本 ComfyUI。
- MiniMax H3 模型、文本编码器、视频 VAE、音频 VAE由用户自行下载并放入本机模型目录。
- 工作流保存视频使用 **ComfyUI-VideoHelperSuite** 的 `VHS_VideoCombine`。
- SageAttention、Sol-Attn、T8均为可选项；没有这些插件时请保持对应开关关闭，并将 SageAttention 设为 `disabled`。

### 安装方法 A：Git 克隆

在 `ComfyUI/custom_nodes/` 中执行：

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

重启 ComfyUI，再导入：

```text
workflows/南风H3V4.json
```

> 仓库发布后，`wwjjqq888888-pixel`会替换为真实账号。

### 安装方法 B：Release ZIP

1. 从 Releases 下载 `nanfeng-h3-comfyui-v1.0.0.zip`。
2. 解压后，将 `nanfeng_prompt_nodes` 文件夹放入 `ComfyUI/custom_nodes/`。
3. 重启 ComfyUI，并在浏览器中按 `Ctrl+F5`。
4. 导入附带的 `南风H3V4.json`。

详细步骤见：[中文安装说明](docs/INSTALL.zh-CN.md)。

### 模型目录

```text
ComfyUI/models/diffusion_models/   # H3 Ref2VA / FL2VA diffusion models
ComfyUI/models/text_encoders/      # MiniMax H3 text encoder
ComfyUI/models/vae/                # H3 video VAE + audio VAE
ComfyUI/models/loras/              # Optional LoRAs
```

节点下拉框读取接收方本机目录；仓库和工作流不会写死作者的模型路径。

### 工作流安全与隐私

附带工作流已经清除：作者本地模型选择、LoRA名称、素材文件、提示词、历史预览路径和随机种子。模型文件与用户素材不会上传到本仓库。

### 已知限制

- 本项目不附带模型权重，不提供MiniMax模型许可证之外的授权。
- `原图比例`仅适用于图生视频和首尾帧。
- LoRA启用时，V4 Sigma实验路径会自动关闭，避免叠加未经验证的采样语义。
- 加速后端可能改变速度、显存或输出；请固定Seed进行A/B测试，不应把图正确生成等同于画质无损。
- ComfyUI按位置序列化Widget；升级时不要随意删除或插入旧字段。

### 仓库结构

```text
nanfeng-h3-comfyui/
├─ __init__.py
├─ nodes.py
├─ h3_generator.py
├─ web/
├─ workflows/南风H3V4.json
├─ docs/
├─ README.md
└─ README_EN.md
```

### 反馈问题

提交Issue时请提供：ComfyUI版本、GPU、PyTorch/CUDA版本、使用的H3任务模型（Ref2VA或FL2VA）、分辨率、帧数、步数、完整报错。不要上传私有模型、API Key或含隐私的素材。

### 许可

节点代码以 [MIT License](LICENSE) 发布。MiniMax H3模型权重、ComfyUI及第三方插件各自遵循其原始许可证。

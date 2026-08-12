# 安装说明（中文）

## 1. 安装节点

### Git方式

进入`ComfyUI/custom_nodes/`后执行：

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

### ZIP方式

从GitHub Releases下载ZIP，将其中的`nanfeng_prompt_nodes`复制到：

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes
```

确认最终路径不是双层目录，例如不要出现：

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes/nanfeng_prompt_nodes/__init__.py
```

正确路径应为：

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes/__init__.py
```

## 2. 安装工作流依赖

通过ComfyUI Manager安装 **ComfyUI-VideoHelperSuite**，工作流使用它的`VHS_VideoCombine`节点。

SageAttention、Sol-Attn、T8为可选插件。未安装时：

```text
SageAttention = disabled
启用SolAttn = 关闭
启用T8缓存 = 关闭
```

## 3. 放置模型

```text
ComfyUI/models/diffusion_models/   MiniMax H3 Ref2VA/FL2VA模型
ComfyUI/models/text_encoders/      MiniMax H3文本编码器
ComfyUI/models/vae/                视频VAE和音频VAE
ComfyUI/models/loras/              可选LoRA
```

本仓库不提供模型文件。请确认所用权重许可证允许你的使用场景。

## 4. 重启并导入

1. 重启ComfyUI。
2. 浏览器按`Ctrl+F5`强制刷新。
3. 导入`workflows/南风H3V4.json`。
4. 在V4节点中重新选择本机模型、文本编码器和两个VAE。
5. 首次测试关闭LoRA、Sol、T8和Sigma实验，Sage设为`disabled`，先验证官方基线路径。

## 5. 模式与素材

- Ref2VA：不勾选三个FL2VA开关；至少添加一种参考素材。
- 文生视频：开启`文生视频`，不能上传图片/视频/音频参考。
- 图生视频：开启`图生视频`，图片1必须是首帧。
- 首尾帧：开启`首尾帧`，图片1为首帧、图片2为尾帧。
- 素材槽位必须从1开始连续填写，不能跳号。
- `原图比例`仅在图生视频和首尾帧模式有效。

## 6. 常见问题

**节点变红或找不到：** 检查目录层级，然后看ComfyUI启动终端的完整导入错误。

**工作流缺少VHS节点：** 安装或更新ComfyUI-VideoHelperSuite。

**模型下拉为空：** 检查模型目录并重启ComfyUI；浏览器刷新不能重新加载Python端模型列表。

**缺少Sage/Sol/T8节点：** 关闭相应功能。它们不是基线生成所必需。

**旧工作流控件错位：** 不要手工删除V4中用于兼容旧序列化位置的字段；优先重新导入仓库附带的脱敏工作流。

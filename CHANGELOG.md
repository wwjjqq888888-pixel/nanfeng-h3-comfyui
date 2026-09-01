# Changelog / 更新日志

## v10.0.0

### 中文

- 发布独立节点 `NanFengH3MultiReferenceGeneratorV10`。
- 新增智能音频驱动：音频与内部分镜一一对应，支持按段裁切、末段补静音和独立 API 配置。
- 新增 NativeAudioLock 精确源音频输出与生成前锁定校验。
- 新增恒定触发词独立输入，每段按单换行拼接且空值不产生顶头空行。
- 新增持久化 Sigma 预设：保护内置预设，允许新建、选择和删除自定义预设。
- 动态 LoRA 数量可减至 0；新增 LoRA 默认不启用；一采复用 LoRA 时隐藏二采重复配置。
- 保留连续一采/二采、完整 Sigma 轨迹、共享 ModelPatcher/LoRA 链与潜空间二采能力。
- 常规智能分镜 Skill、音频驱动 Skill 和 NS 分镜 Skill 均按节点目录相对解析。
- 新增 V10 实机截图、中英双语首页、明确的语言支持与隐私边界。
- 升级包排除 `.env`、`.audio-drive.env`、视觉缓存、字节码和测试缓存。

### English

- Published the standalone `NanFengH3MultiReferenceGeneratorV10` node.
- Added audio-driven storyboards with one audio interval per segment, per-segment slicing, final silence padding, and isolated provider configuration.
- Added exact source-audio output and pre-generation validation through NativeAudioLock.
- Added an independent constant-trigger line with exact single-newline composition and no empty-line artifact.
- Added persistent Sigma presets with protected built-ins and creatable/selectable/deletable custom entries.
- Dynamic LoRA count can reach zero; new entries default to disabled; reused first-pass LoRAs hide duplicate second-pass controls.
- Retained continuous first/second pass, full Sigma trajectory, shared ModelPatcher/LoRA chain, and latent second-pass generation.
- Regular storyboard, audio-drive, and NS storyboard Skills resolve relative to the installed node package.
- Added live V10 screenshots, a complete bilingual homepage, and explicit language/privacy boundaries.
- Upgrade package excludes live credentials, vision cache, bytecode, and test caches.

## v8.1.0

- Added independent V8.1 continuous Sigma first/second-pass generator.
- Shared ModelPatcher, LoRA, strengths, and attention chain across both passes.
- Added official full-temporal H3 3D latent upscaling path.
- Added secure smart storyboard backend/UI, image management, batching, cancellation, and paid-response-safe retry logic.
- Added independent persistent natural-language idea field; generated storyboard text no longer overwrites it.
- Removed FaceRefine execution from V8.1 while retaining inert positional compatibility placeholders.

## Historical / 历史版本

V6 and V4 remain available from their existing tags and Releases. / V6 与 V4 继续保留在原有标签和 Release 中。

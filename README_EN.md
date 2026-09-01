# NanFeng H3 V10 for ComfyUI

> One node for multi-reference media, AI storyboards, audio-driven segmentation, and continuous second-pass generation.

This is an **unofficial** all-in-one ComfyUI workstation for MiniMax H3. It consolidates models, LoRAs, image/video/audio references, segmented prompts, Sigma controls, audio locking, and second-pass generation into one dense node UI.

For the complete bilingual homepage, screenshots, installation instructions, language-support table, privacy notes, and model directories, see [README.md](README.md#english).

## V10 highlights

- Unified multi-reference image/video/audio slots with stable prompt references.
- Separate vision and text providers for AI storyboard generation.
- Dedicated audio-drive provider configuration and one audio interval per storyboard segment.
- Exact source-audio output through NativeAudioLock.
- Shared ModelPatcher and dynamic LoRA stack across continuous first/second-pass generation.
- Persistent protected/custom Sigma presets synchronized with sampling values and steps.
- Independent constant-trigger line prepended to each segment without blank-line artifacts.
- Portable relative paths for Skills, frontend assets, and local configuration.
- Separate regular and NS storyboard Skill directories with explicit scope boundaries.

## Install

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes_v10
```

Restart ComfyUI and press `Ctrl+F5`.

The runtime node UI is Chinese-first and does not yet provide a complete language switch. Chinese or English prompt text may be entered; comprehension depends on the selected upstream model.

No model weights, generated media, API keys, live `.env`, `.audio-drive.env`, or vision-analysis cache are included.

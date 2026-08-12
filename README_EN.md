# NanFeng H3 V4 for ComfyUI

[中文](README.md) · [English](#english)

> A Chinese-first ComfyUI custom-node package for MiniMax H3 with multimodal references, FL2VA modes, prompt-list batching, LoRA slots, optional acceleration backends, and opt-in Sigma experiments.

> **Unofficial project.** This repository is not affiliated with MiniMax or Comfy-Org and does not distribute model weights.

## English

### Features

- **NanFeng H3 Multi-Reference Video Generator V4** wraps model loading, conditioning, sampling, and audio/video decoding in one node.
- **Ref2VA references:** up to 9 images, 3 videos, and 3 audio files, mapped in slot order to native H3 reference labels.
- **FL2VA modes:** text-to-video, first-frame image-to-video, and first/last-frame generation.
- **Prompt List:** every non-empty prompt box becomes an independent top-level queue job, submitted in top-to-bottom order.
- **LoRA:** up to three model-only LoRAs; disabled by default.
- **Optional acceleration:** can use SageAttention, Sol-Attn, or MiniMax H3 Block Cache (T8) when those nodes are installed. Safety checks prevent unsupported combinations.
- **V4 Sigma controls:** optional H3 Sigma Shift, low-Sigma densification, manual Sigma sequences, and optional two-stage sampling.
- **Safe sizing:** Original Aspect Ratio reads only the first-frame aspect ratio; the Megapixels setting remains the output-area budget. Reference images are capped at a 1920-pixel longest edge and are never upscaled when already smaller.
- V1–V4 class IDs are retained for legacy-workflow compatibility.

### Language support

- GitHub overview, installation guide, and release notes: **Chinese and English**.
- ComfyUI node UI: currently **Chinese-first**. English users can follow this field reference and guide.
- Prompt text can be Chinese or English; actual understanding depends on the MiniMax H3 encoder and checkpoint.

### Requirements

- A recent ComfyUI build with native MiniMax H3 nodes.
- User-supplied MiniMax H3 diffusion checkpoint(s), text encoder, video VAE, and audio VAE.
- **ComfyUI-VideoHelperSuite** for the workflow's `VHS_VideoCombine` output node.
- SageAttention, Sol-Attn, and T8 are optional. Keep their controls off, and set SageAttention to `disabled`, when the corresponding extensions are absent.

### Install with Git

Run inside `ComfyUI/custom_nodes/`:

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

Restart ComfyUI and import:

```text
workflows/南风H3V4.json
```

The placeholder URL will be replaced with the real owner after publication.

### Install from a Release ZIP

1. Download `nanfeng-h3-comfyui-v1.0.0.zip` from Releases.
2. Extract `nanfeng_prompt_nodes` into `ComfyUI/custom_nodes/`.
3. Restart ComfyUI and hard-refresh the browser with `Ctrl+F5`.
4. Import the included `南风H3V4.json` workflow.

See [English installation guide](docs/INSTALL.en.md) for details.

### Model folders

```text
ComfyUI/models/diffusion_models/   # H3 Ref2VA / FL2VA diffusion models
ComfyUI/models/text_encoders/      # MiniMax H3 text encoder
ComfyUI/models/vae/                # H3 video VAE + audio VAE
ComfyUI/models/loras/              # Optional LoRAs
```

Dropdowns are populated from the recipient's local ComfyUI folders. No author-specific model path is embedded in the distributed workflow.

### Privacy

The included workflow has been sanitized: local checkpoint selections, LoRA names, media filenames, prompts, preview paths, and the author's seed were removed. Model files and user media are not included.

### Known limitations

- Model weights are not included and retain their original licenses.
- Original Aspect Ratio is available only in image-to-video and first/last-frame modes.
- Enabling a LoRA disables V4 Sigma experiments to avoid combining unverified sampling semantics.
- Acceleration backends can change speed, VRAM use, or output. Use fixed-seed A/B tests; graph execution alone is not proof of lossless quality.
- ComfyUI serializes widget values positionally. Do not remove or insert legacy fields when extending the node.

### Reporting issues

Include the ComfyUI version, GPU, PyTorch/CUDA version, H3 task checkpoint (Ref2VA or FL2VA), resolution, frame count, step count, and full error. Never upload private checkpoints, API keys, or sensitive media.

### License

Node source is released under the [MIT License](LICENSE). MiniMax H3 weights, ComfyUI, and third-party extensions remain subject to their own licenses.

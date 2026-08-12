# Installation Guide (English)

## 1. Install the custom node

### Git

Run inside `ComfyUI/custom_nodes/`:

```bash
git clone https://github.com/wwjjqq888888-pixel/nanfeng-h3-comfyui.git nanfeng_prompt_nodes
```

### ZIP

Download the Release ZIP and copy `nanfeng_prompt_nodes` to:

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes
```

The correct final path is:

```text
ComfyUI/custom_nodes/nanfeng_prompt_nodes/__init__.py
```

Avoid an accidental double-nested folder.

## 2. Install workflow dependencies

Install **ComfyUI-VideoHelperSuite** through ComfyUI Manager. The included workflow uses `VHS_VideoCombine`.

SageAttention, Sol-Attn, and T8 are optional. If absent, use:

```text
SageAttention = disabled
Enable SolAttn = off
Enable T8 cache = off
```

## 3. Place model files

```text
ComfyUI/models/diffusion_models/   MiniMax H3 Ref2VA/FL2VA checkpoints
ComfyUI/models/text_encoders/      MiniMax H3 text encoder
ComfyUI/models/vae/                Video VAE and audio VAE
ComfyUI/models/loras/              Optional LoRAs
```

No model weights are distributed by this repository.

## 4. Restart and import

1. Restart ComfyUI.
2. Hard-refresh the browser with `Ctrl+F5`.
3. Import `workflows/南风H3V4.json`.
4. Select your local checkpoint, text encoder, video VAE, and audio VAE.
5. For the first baseline test, disable LoRA, Sol, T8, and Sigma experiments, and set SageAttention to `disabled`.

## 5. Modes and media

- Ref2VA: leave all three FL2VA switches off and provide at least one reference asset.
- Text-to-video: enable the T2V switch and do not provide reference media.
- Image-to-video: enable I2V; Image 1 is the first frame.
- First/last-frame: enable the corresponding mode; Image 1 is first and Image 2 is last.
- Slots must be contiguous from slot 1; gaps are rejected.
- Original Aspect Ratio is valid only for I2V and first/last-frame modes.

## 6. Troubleshooting

**Node is missing or red:** verify the directory level and inspect the full ComfyUI startup import error.

**Missing VHS node:** install or update ComfyUI-VideoHelperSuite.

**Empty model dropdown:** verify model folders and restart ComfyUI. A browser refresh does not reload the Python-side model list.

**Missing Sage/Sol/T8 nodes:** turn off the corresponding option; these extensions are not required for baseline generation.

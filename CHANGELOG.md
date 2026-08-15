# Changelog

## V6 — 2026-08-14

- Added the `南风H3多参视频生成V6` compatibility-preserving node.
- V6 generation-mode switches no longer change the selected diffusion checkpoint in the frontend or expanded backend graph.
- Added persistent storyboard tabs with new, deep-copy, delete, independent prompts, and independent image/video/audio slots.
- Added mutually exclusive single-person and two-person small-face refinement modes.
- Added two independent identity-locked FaceRefine chains with sequential stitch-back.
- Added same-image left/right identity selection through `H3SelectIdentityFace`.
- Clarified main sampling, true HD second pass, fixed four-step FaceRefine, Sol-Attn RTX 5090 use, and T8 compatibility labels.
- Included the matching `ComfyUI-H3-FaceRefine` companion source under `integrations/`.

## v1.0.0

- Public bilingual release of NanFeng H3 V4 and NanFeng Prompt List.
- Includes sanitized MiniMax H3 V4 workflow.
- Supports Ref2VA and FL2VA T2V/I2V/first-last-frame routing.
- Includes three LoRA slots and optional Sage/Sol-Attn/T8 branches.
- Includes opt-in mode-aware Sigma controls.
- Preserves megapixel-budget sizing and caps reference-image longest edge at 1920.
- Fixes prompt-list queue order for normal and queue-front submission.

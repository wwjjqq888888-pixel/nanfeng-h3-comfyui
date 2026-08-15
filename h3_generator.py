"""南风 H3 多参视频生成：把官方 Ref2VA 工作流封装为单节点。"""
from __future__ import annotations

import os
import re
import math
from collections import OrderedDict

CATEGORY = "南风节点/视频生成"
FPS = 24
DEFAULT_MODEL_OPTIONS = [
    "H3/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "H3/minimax_h3_ref2va_int8_convrot.safetensors",
    "H3/minimax_h3_ref2va_bf16.safetensors",
]
FL2VA_MODEL_NAME = "minimax_h3_fl2va_int8_convrot.safetensors"
# 与 Downloads/video_minimax_h3_r2v.json 官方本地工作流保持一致。
DEFAULT_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
DEFAULT_VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
DEFAULT_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
SAGE_MODES = [
    "disabled", "auto", "sageattn_qk_int8_pv_fp16_cuda",
    "sageattn_qk_int8_pv_fp16_triton", "sageattn_qk_int8_pv_fp8_cuda",
    "sageattn_qk_int8_pv_fp8_cuda++", "sageattn3", "sageattn3_per_block_mean",
]


def _is_h3_video_model(filename: str) -> bool:
    """接受官方及第三方命名的H3 Ref2VA/FL2VA扩散模型。"""
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return "h3" in name and any(tag in name for tag in ("ref2va", "fl2va"))


def _select_fl2va_model(selected_model: str, installed: list[str]) -> str:
    """FL模式优先保留用户选择的FL2VA模型，否则回退官方标准权重。"""
    selected_name = str(selected_model or "").lower()
    if "fl2va" in selected_name and selected_model in installed:
        return selected_model
    return next(
        (x for x in installed if x.replace("\\", "/").lower().endswith(FL2VA_MODEL_NAME)),
        FL2VA_MODEL_NAME,
    )


SECOND_MODEL_SAME = "跟随一采模型（质量优先）"
SECOND_MODEL_AUTO = "自动轻量模型（Ref / FL匹配）"
FACE_REFINE_OFF = "关闭（原始输出）"
FACE_REFINE_ON = "远景小脸修复（H3 FaceRefine）"


def _select_face_refine_turbo_lora(installed: list[str]) -> str:
    """选择本机H3四步Turbo LoRA；FaceRefine固定四步链路不能在无蒸馏LoRA时静默运行。"""
    candidates = [x for x in installed if "h3" in x.lower() and "turbo" in x.lower() and "4step" in x.lower()]
    for marker in ("ema_ckpt850_pruned", "4step_pruned", "4_step"):
        match = next((x for x in candidates if marker in x.lower()), None)
        if match:
            return match
    if candidates:
        return candidates[0]
    raise ValueError(
        "远景小脸修复需要H3四步Turbo LoRA；请把 minimax_h3_*turbo*4step*.safetensors "
        "放入 ComfyUI/models/loras/H3 后刷新模型列表。"
    )


def _select_second_pass_model(requested: str, installed: list[str], fl_mode: bool, first_model: str) -> str:
    """二采自动选择同任务家族的轻量权重；没有轻量版时回退当前一采模型。"""
    family = "fl2va" if fl_mode else "ref2va"
    requested = str(requested or SECOND_MODEL_SAME)
    compatible = [x for x in installed if _is_h3_video_model(x) and family in x.lower()]
    if requested == SECOND_MODEL_SAME:
        return first_model
    if requested != SECOND_MODEL_AUTO:
        if requested not in installed:
            raise ValueError(f"二采模型不存在或尚未被ComfyUI扫描：{requested}")
        if family not in requested.lower():
            raise ValueError(f"当前模式需要{family.upper()}二采模型，不能使用：{requested}")
        return requested
    for marker in ("pruned_w4a8_mixed", "w4a8_mixed", "pruned_int8", "pruned_fp8"):
        match = next((x for x in compatible if marker in x.lower()), None)
        if match:
            return match
    if family in str(first_model).lower():
        return first_model
    return compatible[0] if compatible else first_model

RATIOS = {
    "1:1 (Square)": (1, 1), "2:3 (Portrait Photo)": (2, 3),
    "3:2 (Photo)": (3, 2), "3:4 (Portrait Standard)": (3, 4),
    "4:3 (Standard)": (4, 3), "9:16 (Portrait Widescreen)": (9, 16),
    "16:9 (Widescreen)": (16, 9), "21:9 (Ultrawide)": (21, 9),
}
MEGAPIXELS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.98, 1.0, 1.2, 1.5, 1.8, 2.0]


def resolution_from_megapixels(aspect_ratio: str, megapixels: float, multiple: int = 32) -> tuple[int, int]:
    w_ratio, h_ratio = RATIOS[aspect_ratio]
    scale = math.sqrt(float(megapixels) * 1024 * 1024 / (w_ratio * h_ratio))
    width = round(w_ratio * scale / multiple) * multiple
    height = round(h_ratio * scale / multiple) * multiple
    return max(multiple, width), max(multiple, height)


class NanFengH3ImageCanvasSize32:
    """沿用首帧宽高比，按所选百万像素计算画布；最长边不超过1920并对齐32。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "megapixels": ("FLOAT", {"default": 0.6, "min": 0.2, "max": 2.0, "step": 0.1}),
        }}

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "calculate"
    CATEGORY = CATEGORY

    def calculate(self, image, megapixels):
        source_height, source_width = int(image.shape[1]), int(image.shape[2])
        target_area = float(megapixels) * 1024 * 1024
        scale = math.sqrt(target_area / (source_width * source_height))
        width = source_width * scale
        height = source_height * scale
        if max(width, height) > 1920:
            cap_scale = 1920.0 / max(width, height)
            width *= cap_scale
            height *= cap_scale
        width = max(32, round(width / 32) * 32)
        height = max(32, round(height / 32) * 32)
        return min(1920, width), min(1920, height)


def duration_to_frames(seconds: float) -> int:
    """H3 要求帧数满足 17n+5；与原工作流公式完全一致。"""
    frames = max(5, round(float(seconds) * FPS))
    return frames + (5 - frames % 17) % 17


def _result(value):
    return value.result if hasattr(value, "result") else value


def _clean_filename(value: str) -> str:
    value = str(value or "").strip()
    return "" if value in {"未选择", "None", "null"} else value


def _parse_manual_sigmas(text: str) -> list[float]:
    """校验H3手动Sigma：从高到低、至少一个有效步骤，并且必须以0收尾。"""
    tokens = re.findall(r"[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?", str(text or ""))
    values = [float(token) for token in tokens]
    if len(values) < 2:
        raise ValueError("手动西格玛至少需要两个数值，例如：1, 0.8, 0。")
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("手动西格玛只能填写有限的非负数值。")
    if any(current <= following for current, following in zip(values, values[1:])):
        raise ValueError("手动西格玛必须严格从高到低排列，不能重复或回升。")
    if abs(values[-1]) > 1e-8:
        raise ValueError("手动西格玛最后一个数值必须是0。")
    return values


class NanFengH3UpscaleForSecondPass:
    """按目标百万像素逐帧放大一采视频，并保持原始宽高比与32倍数。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "megapixels": ("FLOAT", {"default": 1.0, "min": 0.2, "max": 2.0, "step": 0.1}),
            "method": (["lanczos", "bicubic", "bilinear", "nearest-exact"], {"default": "lanczos"}),
        }}

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "upscale"
    CATEGORY = CATEGORY

    def upscale(self, image, megapixels, method):
        import comfy.utils
        source_height, source_width = int(image.shape[1]), int(image.shape[2])
        source_area = source_width * source_height
        target_area = float(megapixels) * 1024 * 1024
        if target_area <= source_area:
            return image, source_width, source_height
        scale = math.sqrt(target_area / max(1, source_area))
        width = max(32, round(source_width * scale / 32) * 32)
        height = max(32, round(source_height * scale / 32) * 32)
        samples = image[..., :3].movedim(-1, 1)
        resized = comfy.utils.common_upscale(samples, width, height, str(method), "disabled").movedim(1, -1)
        return resized, width, height


class NanFengH3RebuildAVLatent:
    """用放大重编码后的视频Latent替换H3嵌套AV Latent中的视频流，保留原音频流。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video_latent": ("LATENT",), "source_av_latent": ("LATENT",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "rebuild"
    CATEGORY = CATEGORY

    def rebuild(self, video_latent, source_av_latent):
        from comfy.nested_tensor import NestedTensor
        video = video_latent["samples"]
        source = source_av_latent["samples"]
        if not getattr(source, "is_nested", False):
            raise ValueError("高清二采需要MiniMax H3音视频嵌套Latent。")
        streams = source.unbind()
        if len(streams) < 2:
            raise ValueError("MiniMax H3 Latent缺少音频流，无法重组高清二采输入。")
        result = source_av_latent.copy()
        result["samples"] = NestedTensor((video, streams[-1]))
        return (result,)


class NanFengH3AddFinalSigmaStep:
    """只在最后一个非零Sigma区间增加一个中点，供FL2VA做极轻微高频收尾。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"sigmas": ("SIGMAS",)}}

    RETURN_TYPES = ("SIGMAS",)
    FUNCTION = "add"
    CATEGORY = CATEGORY

    def add(self, sigmas):
        import torch
        if len(sigmas) < 2:
            return (sigmas,)
        midpoint = (sigmas[-2] + sigmas[-1]) * 0.5
        return (torch.cat((sigmas[:-1], midpoint.reshape(1), sigmas[-1:])),)


class NanFengH3TrimSigmasAtStart:
    """为高清二采从用户指定的精确Sigma开始，保留其后的原生下降轨迹。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "sigmas": ("SIGMAS",),
            "start_sigma": ("FLOAT", {"default": 0.2, "min": 0.01, "max": 1.0, "step": 0.01}),
        }}

    RETURN_TYPES = ("SIGMAS",)
    FUNCTION = "trim"
    CATEGORY = "南风节点/内部"

    def trim(self, sigmas, start_sigma):
        import torch
        start = float(start_sigma)
        if not math.isfinite(start) or start <= 0.0:
            raise ValueError("二采起始Sigma必须是大于0的有限数值。")
        flat = sigmas.flatten()
        if flat.numel() < 2:
            raise ValueError("二采Sigma轨迹至少需要两个值。")
        if start >= float(flat[0]):
            return (flat,)
        tail = flat[flat < start]
        if tail.numel() == 0 or float(tail[-1]) != 0.0:
            tail = torch.cat((tail, flat.new_zeros(1)))
        return (torch.cat((flat.new_tensor([start]), tail)),)


def _aggressive_h3_vram_release(mm, collect_garbage):
    """卸载模型并清掉ComfyUI动态加载/异步权重转换缓冲区。"""
    mm.unload_all_models()
    # 当前ComfyUI的动态VRAM路径会保留STREAM_CAST_BUFFERS与AIMDO缓冲区；
    # 单独empty_cache不能释放仍被这些全局字典引用的GPU Tensor。
    reset_cast_buffers = getattr(mm, "reset_cast_buffers", None)
    if reset_cast_buffers is not None:
        reset_cast_buffers()
    collect_garbage()
    mm.cleanup_models()
    mm.cleanup_models_gc()
    mm.soft_empty_cache(force=True)


def _vram_snapshot(mm):
    """返回ComfyUI可用显存、PyTorch保留池空闲和当前loaded-model数量。"""
    total_free, torch_pool_free = mm.get_free_memory(torch_free_too=True)
    loaded = len(getattr(mm, "current_loaded_models", ()))
    return total_free, torch_pool_free, loaded


def build_native_prompt(prompt: str, image_count: int, videos_with_audio: list[bool], audio_count: int) -> str:
    """将固定槽位别名转换为 H3 按实际呈现顺序生成的原生标签。"""
    mapping = {}
    for index in range(1, image_count + 1):
        mapping[f"@图片{index}"] = f"<Picture {index}>"
    audio_ordinal = 1
    for index, has_soundtrack in enumerate(videos_with_audio, 1):
        if has_soundtrack:
            mapping[f"@视频音频{index}"] = f"<Audio {audio_ordinal}>"
            audio_ordinal += 1
        mapping[f"@视频{index}"] = f"<Video {index}>"
    for index in range(1, audio_count + 1):
        mapping[f"@音频{index}"] = f"<Audio {audio_ordinal}>"
        audio_ordinal += 1

    text = str(prompt or "").strip()
    aliases = set(re.findall(r"@(图片|视频音频|视频|音频)(\d+)", text))
    unknown = sorted(f"@{kind}{number}" for kind, number in aliases if f"@{kind}{number}" not in mapping)
    if unknown:
        raise ValueError("以下@引用没有对应素材：" + "、".join(unknown))
    for source in sorted(mapping, key=len, reverse=True):
        text = text.replace(source, mapping[source])
    return text


def _load_media(image_names, video_names, audio_names):
    import folder_paths
    import nodes
    from comfy_api.latest import InputImpl
    from comfy_extras.nodes_audio import LoadAudio

    images = []
    for name in image_names:
        if name:
            images.append(nodes.LoadImage().load_image(name)[0])

    videos, video_audios, soundtrack_flags = [], [], []
    for name in video_names:
        if not name:
            continue
        path = folder_paths.get_annotated_filepath(name)
        components = InputImpl.VideoFromFile(path).get_components()
        videos.append(components.images)
        soundtrack = components.audio
        has_audio = soundtrack is not None
        soundtrack_flags.append(has_audio)
        video_audios.append(soundtrack if has_audio else None)

    audios = []
    for name in audio_names:
        if name:
            audios.append(_result(LoadAudio.execute(name))[0])
    return images, videos, video_audios, soundtrack_flags, audios


def _sample_progress_only(noise, guider, sampler, sigmas, latent):
    """等价执行 SamplerCustomAdvanced，但不生成/保留 Latent 预览图和 denoised 副本。"""
    import comfy.sample
    import comfy.model_management
    import comfy.utils

    source = latent
    latent_image = source["samples"]
    out = source.copy()
    latent_image = comfy.sample.fix_empty_latent_channels(
        guider.model_patcher,
        latent_image,
        source.get("downscale_ratio_spacial"),
        source.get("downscale_ratio_temporal"),
    )
    out["samples"] = latent_image
    noise_mask = source.get("noise_mask")
    total = max(0, int(sigmas.shape[-1]) - 1)
    pbar = comfy.utils.ProgressBar(total)

    # 保留 ComfyUI 原生进度/取消链路，只省略 latent_preview.prepare_callback 的图像解码。
    def callback(step, _x0, _x, total_steps):
        pbar.update_absolute(step + 1, total_steps, None)

    samples = guider.sample(
        noise.generate_noise(out), latent_image, sampler, sigmas,
        denoise_mask=noise_mask,
        callback=callback,
        disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
        seed=noise.seed,
    )
    samples = samples.to(comfy.model_management.intermediate_device())
    result = source.copy()
    result.pop("downscale_ratio_spacial", None)
    result.pop("downscale_ratio_temporal", None)
    result["samples"] = samples
    return result


class NanFengH3PrepareReferences:
    """子图内部节点：只负责素材读取和H3条件编码，可独立缓存。"""
    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "clip": ("CLIP",), "video_vae": ("VAE",), "audio_vae": ("VAE",),
            "prompt": ("STRING", {"multiline": True}),
            "width": ("INT",), "height": ("INT",), "length": ("INT",),
            "reference_size": (["match", "max"],),
        }
        for kind, count in (("image", 9), ("video", 3), ("audio", 3)):
            for i in range(1, count + 1):
                required[f"{kind}_{i}"] = ("STRING", {"default": ""})
        return {"required": required}

    RETURN_TYPES = ("CONDITIONING", "LATENT")
    FUNCTION = "prepare"
    CATEGORY = "南风节点/内部"

    def prepare(self, clip, video_vae, audio_vae, prompt, width, height, length, reference_size, **kwargs):
        from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo
        image_names = [_clean_filename(kwargs.get(f"image_{i}")) for i in range(1, 10)]
        video_names = [_clean_filename(kwargs.get(f"video_{i}")) for i in range(1, 4)]
        audio_names = [_clean_filename(kwargs.get(f"audio_{i}")) for i in range(1, 4)]
        images, videos, video_audios, soundtrack_flags, audios = _load_media(
            [x for x in image_names if x], [x for x in video_names if x], [x for x in audio_names if x]
        )
        native_prompt = build_native_prompt(prompt, len(images), soundtrack_flags, len(audios))
        result = _result(MiniMaxH3ReferenceToVideo.execute(
            clip, video_vae, audio_vae, native_prompt, int(width), int(height), int(length), reference_size,
            {f"ref_image_{i}": v for i, v in enumerate(images)},
            {f"ref_video_{i}": v for i, v in enumerate(videos)},
            {f"ref_video_audio_{i}": v for i, v in enumerate(video_audios) if v is not None},
            {f"ref_audio_{i}": v for i, v in enumerate(audios)},
        ))
        return tuple(result)


class NanFengH3LimitImageLongEdge:
    """内部无损通路：小图原样返回；大图按比例缩小到最长边不超过1920。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "max_long_edge": ("INT", {"default": 1920, "min": 32, "max": 8192, "step": 32}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "limit"
    CATEGORY = "南风节点/内部"

    def limit(self, image, max_long_edge=1920):
        from comfy.utils import common_upscale

        height, width = int(image.shape[1]), int(image.shape[2])
        longest = max(width, height)
        maximum = int(max_long_edge)
        if longest <= maximum:
            return (image,)
        scale = maximum / longest
        target_width = max(1, round(width * scale))
        target_height = max(1, round(height * scale))
        samples = image.movedim(-1, 1)
        resized = common_upscale(samples, target_width, target_height, "lanczos", "disabled")
        return (resized.movedim(1, -1),)


class NanFengH3ProgressSampler:
    """子图内部采样节点：保留进度，不制作Latent预览图。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "noise": ("NOISE",), "guider": ("GUIDER",), "sampler": ("SAMPLER",),
            "sigmas": ("SIGMAS",), "latent_image": ("LATENT",),
        }}
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "南风节点/内部"

    def sample(self, noise, guider, sampler, sigmas, latent_image):
        return (_sample_progress_only(noise, guider, sampler, sigmas, latent_image),)


class NanFengH3ReleaseAtStart:
    """每次新任务最先执行：清掉上一次H3任务残留的GPU驻留和CUDA缓存。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "unet_name": ("STRING", {"default": ""}),
            "clip_name": ("STRING", {"default": ""}),
            "video_vae_name": ("STRING", {"default": ""}),
            "audio_vae_name": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("unet_name", "clip_name", "video_vae_name", "audio_vae_name")
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # NOT_IDEMPOTENT在当前ComfyUI中只会把稳定node_id加入缓存键，第二次队列仍可能命中缓存。
        # NaN永不等于自身，强制每次Queue都真正执行“加载前释放”，并使下游Loader不复用旧任务对象。
        return float("NaN")

    def release(self, unet_name, clip_name, video_vae_name, audio_vae_name):
        import gc
        import comfy.model_management as mm
        before, before_pool, before_loaded = _vram_snapshot(mm)
        # 放在Loader之前而不是采样前：避免第二次任务先构造新patcher，再与旧任务驻留交叠。
        _aggressive_h3_vram_release(mm, gc.collect)
        after, after_pool, after_loaded = _vram_snapshot(mm)
        print(f"[南风H3] 新任务加载前释放显存：{before / 1024**2:.0f}→{after / 1024**2:.0f} MiB；"
              f"PyTorch池空闲 {before_pool / 1024**2:.0f}→{after_pool / 1024**2:.0f} MiB；"
              f"loaded_models {before_loaded}→{after_loaded}")
        return (unet_name, clip_name, video_vae_name, audio_vae_name)


class NanFengH3ReleaseBeforeDecode:
    """采样完成后、双VAE解码前，明确卸载扩散/文本模型的GPU驻留。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"samples": ("LATENT",)}}

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def release(self, samples):
        import gc
        import comfy.model_management as mm
        before, before_pool, before_loaded = _vram_snapshot(mm)
        _aggressive_h3_vram_release(mm, gc.collect)
        after, after_pool, after_loaded = _vram_snapshot(mm)
        print(f"[南风H3] VAE解码前释放显存：{before / 1024**2:.0f}→{after / 1024**2:.0f} MiB；"
              f"PyTorch池空闲 {before_pool / 1024**2:.0f}→{after_pool / 1024**2:.0f} MiB；"
              f"loaded_models {before_loaded}→{after_loaded}")
        return (samples,)


class NanFengH3ReleaseBeforeConditioning:
    """FL2VA条件编码前释放旧GPU驻留，再按需加载CLIP与视频VAE。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"clip": ("CLIP",), "vae": ("VAE",)}}

    RETURN_TYPES = ("CLIP", "VAE")
    RETURN_NAMES = ("clip", "vae")
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def release(self, clip, vae):
        import gc
        import comfy.model_management as mm
        before, before_pool, before_loaded = _vram_snapshot(mm)
        _aggressive_h3_vram_release(mm, gc.collect)
        after, after_pool, after_loaded = _vram_snapshot(mm)
        print(f"[南风H3] FL2VA条件编码前释放显存：{before / 1024**2:.0f}→{after / 1024**2:.0f} MiB；"
              f"PyTorch池空闲 {before_pool / 1024**2:.0f}→{after_pool / 1024**2:.0f} MiB；"
              f"loaded_models {before_loaded}→{after_loaded}")
        return (clip, vae)


class NanFengH3ReleaseBeforeConditionLoaders:
    """V3条件模型加载前屏障：先清空GPU驻留，再放行CLIP与双VAE文件名。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip_name": ("STRING", {"default": ""}),
            "video_vae_name": ("STRING", {"default": ""}),
            "audio_vae_name": ("STRING", {"default": ""}),
        }}

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("clip_name", "video_vae_name", "audio_vae_name")
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def release(self, clip_name, video_vae_name, audio_vae_name):
        import gc
        import comfy.model_management as mm
        before, before_pool, before_loaded = _vram_snapshot(mm)
        _aggressive_h3_vram_release(mm, gc.collect)
        after, after_pool, after_loaded = _vram_snapshot(mm)
        print(f"[南风H3 V3] 文本/参考条件模型加载前释放显存：{before / 1024**2:.0f}→{after / 1024**2:.0f} MiB；"
              f"PyTorch池空闲 {before_pool / 1024**2:.0f}→{after_pool / 1024**2:.0f} MiB；"
              f"loaded_models {before_loaded}→{after_loaded}")
        return (clip_name, video_vae_name, audio_vae_name)


class NanFengH3ReleaseBeforeSampling:
    """条件编码完成后、扩散采样前释放CLIP/VAE驻留，保留已生成的条件与latent。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "conditioning": ("CONDITIONING",),
            "latent": ("LATENT",),
        }}

    RETURN_TYPES = ("MODEL", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("model", "conditioning", "latent")
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def release(self, model, conditioning, latent):
        import gc
        import comfy.model_management as mm
        before, before_pool, before_loaded = _vram_snapshot(mm)
        _aggressive_h3_vram_release(mm, gc.collect)
        after, after_pool, after_loaded = _vram_snapshot(mm)
        print(f"[南风H3] 条件编码后、采样前释放显存：{before / 1024**2:.0f}→{after / 1024**2:.0f} MiB；"
              f"PyTorch池空闲 {before_pool / 1024**2:.0f}→{after_pool / 1024**2:.0f} MiB；"
              f"loaded_models {before_loaded}→{after_loaded}")
        return (model, conditioning, latent)


class NanFengH3ReleaseBeforeSecondModel:
    """放大Latent就绪后卸载一采/CLIP/VAE，再按文件名加载独立二采模型。"""
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "unet_name": ("STRING", {"default": ""}),
            "conditioning": ("CONDITIONING",),
            "latent": ("LATENT",),
        }}

    RETURN_TYPES = ("STRING", "CONDITIONING", "LATENT")
    RETURN_NAMES = ("unet_name", "conditioning", "latent")
    FUNCTION = "release"
    CATEGORY = "南风节点/内部"
    NOT_IDEMPOTENT = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def release(self, unet_name, conditioning, latent):
        import gc
        import comfy.model_management as mm
        _aggressive_h3_vram_release(mm, gc.collect)
        return (unet_name, conditioning, latent)


class NanFengH3MultiReferenceGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        try:
            import folder_paths
            model_options = folder_paths.get_filename_list("diffusion_models")
            text_encoders = folder_paths.get_filename_list("text_encoders")
            vaes = folder_paths.get_filename_list("vae")
        except Exception:
            model_options = list(DEFAULT_MODEL_OPTIONS)
            text_encoders = [DEFAULT_TEXT_ENCODER]
            vaes = [DEFAULT_VIDEO_VAE, DEFAULT_AUDIO_VAE]

        h3_models = [x for x in model_options if _is_h3_video_model(x)] or list(DEFAULT_MODEL_OPTIONS)
        # 优先使用完整INT8版，不默认选择pruned版。
        source_model = next((x for x in h3_models if x.replace("\\", "/").lower().endswith("minimax_h3_ref2va_int8_convrot.safetensors") and "pruned" not in x.lower()), h3_models[0])
        h3_text_encoders = [x for x in text_encoders if "minimax_h3" in x.lower()] or [DEFAULT_TEXT_ENCODER]
        h3_video_vaes = [x for x in vaes if "minimax_h3_video_vae" in x.lower()] or [DEFAULT_VIDEO_VAE]
        h3_audio_vaes = [x for x in vaes if "minimax_h3_audio_vae" in x.lower()] or [DEFAULT_AUDIO_VAE]

        required = OrderedDict([
            ("模型", (h3_models, {"default": source_model})),
            ("文本编码器", (h3_text_encoders, {"default": DEFAULT_TEXT_ENCODER if DEFAULT_TEXT_ENCODER in h3_text_encoders else h3_text_encoders[0]})),
            ("文本编码器类型", (["minimax"], {"default": "minimax"})),
            ("文本编码器设备", (["default", "cpu"], {"default": "default"})),
            ("视频VAE", (h3_video_vaes, {"default": h3_video_vaes[0]})),
            ("音频VAE", (h3_audio_vaes, {"default": h3_audio_vaes[0]})),
            ("模型权重精度", (["default", "fp8_e4m3fn", "fp8_e5m2"], {"default": "default"})),
            # 默认沿用KJ SageAttention=auto。
            ("SageAttention", (SAGE_MODES, {"default": "auto"})),
            ("允许编译", ("BOOLEAN", {"default": False})),
            ("画面比例", (list(RATIOS), {"default": "16:9 (Widescreen)"})),
            ("百万像素", (MEGAPIXELS, {"default": 0.4})),
            ("尺寸倍数", ([32], {"default": 32})),
            ("时长秒", ("FLOAT", {"default": 5.0, "min": 1.0, "max": 15.0, "step": 0.5})),
            ("提示词", ("STRING", {"multiline": True, "dynamicPrompts": True, "default": ""})),
            ("随机种子", ("INT", {"default": 470115107471061, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": True})),
            ("采样器", (["res_multistep"], {"default": "res_multistep"})),
            ("调度器", (["simple"], {"default": "simple"})),
            ("采样步数", ("INT", {"default": 20, "min": 1, "max": 100})),
            ("降噪强度", ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01})),
            ("参考图尺寸", (["match", "max"], {"default": "match"})),
        ])
        # 文件由前端素材卡上传到 ComfyUI/input；普通下拉作为无 JS 时的兼容回退。
        try:
            files = sorted(os.listdir(folder_paths.get_input_directory()))
        except Exception:
            files = []
        choices = ["未选择"] + files
        for kind, count in (("图片", 9), ("视频", 3), ("音频", 3)):
            for index in range(1, count + 1):
                required[f"{kind}{index}"] = (choices, {"default": "未选择"})
        # 序列化层必须追加在全部旧字段之后，避免升级时把旧工作流的降噪、参考图和素材按位置错写。
        # 自定义DOM仍把它们显示在采样步数正下方。
        required["文生视频"] = ("BOOLEAN", {"default": False})
        required["图生视频"] = ("BOOLEAN", {"default": False})
        required["首尾帧"] = ("BOOLEAN", {"default": False})
        return {"required": required}

    RETURN_TYPES = ("IMAGE", "AUDIO")
    RETURN_NAMES = ("图像", "音频")
    FUNCTION = "generate"
    CATEGORY = CATEGORY
    DESCRIPTION = "本地 MiniMax H3 Ref2VA 一体化生成：9图、3视频、3音频，输出最终图像帧与音频。"

    def generate(self, 模型, 文本编码器, 文本编码器类型, 文本编码器设备, 视频VAE, 音频VAE,
                 模型权重精度, SageAttention, 允许编译, 画面比例, 百万像素, 尺寸倍数, 时长秒, 提示词, 随机种子,
                 采样器, 调度器, 采样步数, 降噪强度, 参考图尺寸="match", 文生视频=False, 图生视频=False, 首尾帧=False, **kwargs):
        from comfy_execution.graph_utils import GraphBuilder
        image_names = [_clean_filename(kwargs.get(f"图片{i}")) for i in range(1, 10)]
        video_names = [_clean_filename(kwargs.get(f"视频{i}")) for i in range(1, 4)]
        audio_names = [_clean_filename(kwargs.get(f"音频{i}")) for i in range(1, 4)]
        selected_modes = [name for name, enabled in (("文生视频", 文生视频), ("图生视频", 图生视频), ("首尾帧", 首尾帧)) if enabled]
        if len(selected_modes) > 1:
            raise ValueError("文生视频、图生视频、首尾帧只能开启一个。")
        fl_mode = selected_modes[0] if selected_modes else ""
        # 槽位编号必须连续，确保可见 @编号 与 H3 原生编号完全一致。
        for label, values in (("图片", image_names), ("视频", video_names), ("音频", audio_names)):
            seen_gap = False
            for value in values:
                if not value:
                    seen_gap = True
                elif seen_gap:
                    raise ValueError(f"{label}槽位必须从1开始连续添加，不能跳号。")

        if fl_mode and any(video_names + audio_names):
            raise ValueError(f"{fl_mode}模式不接受视频或音频参考，请清空对应素材。")
        image_count = sum(bool(x) for x in image_names)
        if fl_mode == "文生视频" and image_count:
            raise ValueError("文生视频模式不能上传图片。")
        if fl_mode == "图生视频" and image_count != 1:
            raise ValueError("图生视频模式必须上传1张图片作为首帧。")
        if fl_mode == "首尾帧" and image_count != 2:
            raise ValueError("首尾帧模式必须上传2张图片：图片1为首帧、图片2为尾帧。")
        if not fl_mode and not any(image_names + video_names + audio_names):
            raise ValueError("请至少拖入一张图片、一个视频或一段音频。")
        original_ratio = isinstance(self, NanFengH3MultiReferenceGeneratorV4) and 画面比例 == "原图比例"
        if original_ratio and fl_mode not in {"图生视频", "首尾帧"}:
            raise ValueError("原图比例只适用于图生视频或首尾帧。")
        width, height = ((32, 32) if original_ratio else resolution_from_megapixels(画面比例, 百万像素, int(尺寸倍数)))
        length = duration_to_frames(时长秒)

        # 关键修复：展开成真实ComfyUI子图。Loader/条件/采样/解码重新成为独立缓存节点，
        # 不再在一个Python函数中手工持有整套模型对象。
        g = GraphBuilder()
        selected_model = 模型
        # V6起，模式切换只改变条件节点，不得替用户改动“模型”下拉选择。
        # V1-V5保留既有自动Ref/FL家族切换，避免破坏旧工作流行为。
        if fl_mode and not isinstance(self, NanFengH3MultiReferenceGeneratorV6):
            try:
                import folder_paths
                installed = folder_paths.get_filename_list("diffusion_models")
            except Exception:
                installed = []
            selected_model = _select_fl2va_model(模型, installed)
        # 起始释放节点同时作为四个Loader名称的依赖屏障，保证它必定先于任何大模型加载执行。
        start = g.node(
            "NanFengH3ReleaseAtStart", unet_name=selected_model, clip_name=文本编码器,
            video_vae_name=视频VAE, audio_vae_name=音频VAE,
        )
        model = g.node("UNETLoader", unet_name=start.out(0), weight_dtype=模型权重精度)
        # V2-only chain. LoRA belongs immediately after the base diffusion model so every
        # later model patch (Sage/Sol-Attn) sees the LoRA-patched weights. V1 does not
        # expose these kwargs and therefore remains byte-for-byte equivalent at runtime.
        if bool(kwargs.get("启用LoRA", False)):
            for index in range(1, 4):
                lora_name = _clean_filename(kwargs.get(f"LoRA{index}"))
                strength = float(kwargs.get(f"LoRA{index}强度", 1.0))
                if lora_name and strength != 0.0:
                    model = g.node(
                        "LoraLoaderModelOnly", model=model.out(0),
                        lora_name=lora_name, strength_model=strength,
                    )
        sol_enabled = bool(kwargs.get("启用SolAttn", False))
        t8_enabled = bool(kwargs.get("启用T8缓存", False))
        # Sage and Sol both replace the attention backend. T8 uses exception-based
        # block short-circuiting and has not been proven safe when combined with the
        # generic Sage override on long H3 sequences. V3 therefore selects exactly
        # one acceleration branch: Sol, T8, or Sage/base.
        skip_sage_for_specialized = (
            isinstance(self, NanFengH3MultiReferenceGeneratorV3)
            and (sol_enabled or t8_enabled)
        )
        if SageAttention != "disabled" and not skip_sage_for_specialized:
            model = g.node("PathchSageAttentionKJ", model=model.out(0), sage_attention=SageAttention, allow_compile=bool(允许编译))
        if sol_enabled and t8_enabled:
            raise ValueError("Sol-Attn 与 T8 Block Cache 不能同时开启；请只勾选其中一个，或将两者都关闭。")
        # 条件阶段结束前只建立基础模型/LoRA/Sage/T8的普通patch链。
        # Sol的flex wrapper会在首次采样时编译；必须放到强制清理屏障之后创建，
        # 否则reset_cast_buffers/force empty cache可能破坏其刚建立的编译状态，卡在0% Model Initializing。
        sol_config = None
        defer_sol_until_after_release = isinstance(self, NanFengH3MultiReferenceGeneratorV3)
        if sol_enabled:
            sol_config = {
                "tau": float(kwargs.get("SolAttn_tau", 1.2)),
                "thresh_type": str(kwargs.get("SolAttn阈值类型", "diag")),
                "exact_mode": str(kwargs.get("SolAttn精确模式", "exact_kv")),
                "dense_steps": int(kwargs.get("SolAttn完整末步", 1)),
                "step_off": float(kwargs.get("SolAttn末段比例", 0.0)),
                "sink_tokens": int(kwargs.get("SolAttn前缀Token", 0)),
            }
            if not defer_sol_until_after_release:
                model = g.node(
                    "SolAttnMiniMaxH3Patcher", model=model.out(0), enabled=True, **sol_config,
                )
                sol_config = None
        # V3 T8 branch: T8 alone after LoRA/base model. The generic Sage override is
        # intentionally skipped for this branch until a real cache-hit compatibility run passes.
        if bool(kwargs.get("启用T8缓存", False)):
            model = g.node(
                "MiniMaxH3BlockCacheT8", model=model.out(0),
                residual_diff_threshold=float(kwargs.get("T8残差阈值", 0.12)),
                start_percent=float(kwargs.get("T8开始比例", 0.08)),
                end_percent=float(kwargs.get("T8结束比例", 0.95)),
                max_consecutive_hits=int(kwargs.get("T8连续命中", 2)),
                cache_device=str(kwargs.get("T8缓存设备", "cpu")),
                metric_stride=int(kwargs.get("T8指标步幅", 8)),
                verbose=bool(kwargs.get("T8详细日志", False)),
            )
        # V3专用条件相位屏障只依赖起始释放节点，不依赖DiT/LoRA/加速patch链。
        # 这样条件编码阶段沿用官方工作流的“CLIP+双VAE先执行”节奏，不会提前prepare MiniMaxH3。
        if isinstance(self, NanFengH3MultiReferenceGeneratorV3):
            conditioning_phase = g.node(
                "NanFengH3ReleaseBeforeConditionLoaders",
                clip_name=start.out(1), video_vae_name=start.out(2), audio_vae_name=start.out(3),
            )
            clip_name, video_vae_name, audio_vae_name = conditioning_phase.out(0), conditioning_phase.out(1), conditioning_phase.out(2)
        else:
            clip_name, video_vae_name, audio_vae_name = start.out(1), start.out(2), start.out(3)
        clip = g.node("CLIPLoader", clip_name=clip_name, type=文本编码器类型, device=文本编码器设备)
        video_vae = g.node("VAELoader", vae_name=video_vae_name)
        audio_vae = g.node("VAELoader", vae_name=audio_vae_name)
        if fl_mode:
            # FL2VA模式使用官方原生条件节点。
            conditioning_release = g.node("NanFengH3ReleaseBeforeConditioning", clip=clip.out(0), vae=video_vae.out(0))
            condition_inputs = {
                "clip": conditioning_release.out(0), "vae": conditioning_release.out(1), "prompt": 提示词,
                "width": width, "height": height, "length": length,
            }
            if image_count:
                first = g.node("LoadImage", image=image_names[0])
                first_limited = g.node("NanFengH3LimitImageLongEdge", image=first.out(0), max_long_edge=1920)
                condition_inputs["first_frame"] = first_limited.out(0)
                if original_ratio:
                    image_size = g.node("NanFengH3ImageCanvasSize32", image=first_limited.out(0), megapixels=float(百万像素))
                    condition_inputs["width"] = image_size.out(0)
                    condition_inputs["height"] = image_size.out(1)
            if fl_mode == "首尾帧":
                last = g.node("LoadImage", image=image_names[1])
                last_limited = g.node("NanFengH3LimitImageLongEdge", image=last.out(0), max_long_edge=1920)
                condition_inputs["last_frame"] = last_limited.out(0)
            prepared = g.node("MiniMaxH3ImageToVideo", **condition_inputs)
        else:
            # 1:1复刻Ref2VA：素材保持独立原生子节点缓存边界。
            condition_inputs = {
                "clip": clip.out(0), "vae": video_vae.out(0), "audio_vae": audio_vae.out(0),
                "prompt": build_native_prompt(提示词, image_count, [True for x in video_names if x], sum(bool(x) for x in audio_names)), "width": width, "height": height, "length": length,
                # One sizing authority: upstream longest-edge 1920. Native "max" never upscales
                # and therefore leaves this capped input unchanged apart from required 32px alignment.
                # The legacy serialized widget remains for old-workflow index compatibility only.
                "ref_image_size": "max",
            }
            for i, filename in enumerate((x for x in image_names if x)):
                loaded = g.node("LoadImage", image=filename)
                limited = g.node("NanFengH3LimitImageLongEdge", image=loaded.out(0), max_long_edge=1920)
                condition_inputs[f"ref_images.ref_image_{i}"] = limited.out(0)
            for i, filename in enumerate((x for x in video_names if x)):
                loaded = g.node("LoadVideo", file=filename)
                components = g.node("GetVideoComponents", video=loaded.out(0))
                condition_inputs[f"ref_videos.ref_video_{i}"] = components.out(0)
                condition_inputs[f"ref_video_audios.ref_video_audio_{i}"] = components.out(1)
            for i, filename in enumerate((x for x in audio_names if x)):
                loaded = g.node("LoadAudio", audio=filename)
                condition_inputs[f"ref_audios.ref_audio_{i}"] = loaded.out(0)
            prepared = g.node("MiniMaxH3ReferenceToVideo", **condition_inputs)
        # 明确依赖屏障：只有条件编码完成后才释放CLIP/VAE，再开始加载/执行采样模型。
        sampling_ready = g.node(
            "NanFengH3ReleaseBeforeSampling",
            model=model.out(0), conditioning=prepared.out(0), latent=prepared.out(1),
        )
        sampling_model = sampling_ready.out(0)
        if sol_config is not None:
            # 在最后一次激进清理完成后才创建Sol wrapper；其编译/缓存状态不会再被清除。
            sampling_model = g.node(
                "SolAttnMiniMaxH3Patcher", model=sampling_model, enabled=True, **sol_config,
            ).out(0)
        noise = g.node("RandomNoise", noise_seed=int(随机种子))
        sigma_requested = isinstance(self, NanFengH3MultiReferenceGeneratorV4) and bool(kwargs.get("启用西格玛调节", False))
        hd_second_pass = isinstance(self, NanFengH3MultiReferenceGeneratorV5) and bool(kwargs.get("启用高清二采", False))
        if hd_second_pass and sigma_requested:
            raise ValueError("V5高清二采与西格玛调节不能同时开启；请关闭其中一个。")
        # V4按真实执行状态自动分流：LoRA完全关闭Sigma；裸Ref2VA沿用完整设置；
        # 裸FL2VA（文生/图生/首尾）只在最终高频区间增加一个中点。
        lora_active = bool(kwargs.get("启用LoRA", False)) and any(
            _clean_filename(kwargs.get(f"LoRA{index}")) and float(kwargs.get(f"LoRA{index}强度", 1.0)) != 0.0
            for index in range(1, 4)
        )
        sigma_enabled = sigma_requested and not lora_active
        if sigma_enabled:
            # Sigma Shift belongs after every model/attention/cache patch and immediately before
            # both sampling consumers. This keeps BasicGuider and BasicScheduler on one coherent
            # MiniMax H3 video/audio shift model instead of patching only the scheduler branch.
            sampling_model = g.node(
                "MiniMaxH3SigmaShift", model=sampling_model,
                shift_video=float(kwargs.get("视频西格玛偏移", 12.0)),
                shift_audio=float(kwargs.get("音频西格玛偏移", 3.0)),
            ).out(0)
        guider = g.node("BasicGuider", model=sampling_model, conditioning=sampling_ready.out(1))
        sampler = g.node("KSamplerSelect", sampler_name=采样器)
        first_steps = int(kwargs.get("一采步数", 20)) if hd_second_pass else int(采样步数)
        base_sigmas = g.node("BasicScheduler", model=sampling_model, scheduler=调度器, steps=first_steps, denoise=float(降噪强度))
        sigmas = base_sigmas.out(0)
        if sigma_enabled and fl_mode:
            # FL2VA不复用Ref2VA的整段低Sigma参数；仅在最后的非零→0区间增加1步。
            sigmas = g.node("NanFengH3AddFinalSigmaStep", sigmas=sigmas).out(0)
        elif sigma_enabled:
            sigma_mode = str(kwargs.get("西格玛模式", "低西格玛加密"))
            if sigma_mode == "手动序列":
                manual = str(kwargs.get("手动西格玛", "")).strip()
                values = _parse_manual_sigmas(manual)
                sigmas = g.node("ManualSigmas", sigmas=", ".join(f"{value:g}" for value in values)).out(0)
            else:
                start_sigma = float(kwargs.get("低西格玛开始", 0.8))
                end_sigma = float(kwargs.get("低西格玛结束", 0.0))
                if end_sigma > start_sigma:
                    raise ValueError("低西格玛结束值不能大于开始值。")
                sigmas = g.node(
                    "ExtendIntermediateSigmas", sigmas=sigmas,
                    steps=int(kwargs.get("每区间细分", 2)),
                    start_at_sigma=start_sigma, end_at_sigma=end_sigma,
                    spacing=str(kwargs.get("加密曲线", "cosine")),
                ).out(0)
        # 关闭Sigma时仍是V3原来的单次原生采样路径。双采开启后，第二段从第一段latent
        # 无新增噪声接续；这是真正的两次SamplerCustomAdvanced，不是重复从头生成。
        if type(self) is NanFengH3MultiReferenceGeneratorV4 and sigma_enabled and bool(kwargs.get("启用双采样", False)):
            split = g.node("SplitSigmasDenoise", sigmas=sigmas, denoise=float(kwargs.get("双采后段比例", 0.5)))
            first = g.node(
                "SamplerCustomAdvanced", noise=noise.out(0), guider=guider.out(0), sampler=sampler.out(0),
                sigmas=split.out(0), latent_image=sampling_ready.out(2),
            )
            second_sampler = g.node("KSamplerSelect", sampler_name=str(kwargs.get("双采后段采样器", "res_multistep")))
            no_noise = g.node("DisableNoise")
            sampled = g.node(
                "SamplerCustomAdvanced", noise=no_noise.out(0), guider=guider.out(0), sampler=second_sampler.out(0),
                sigmas=split.out(1), latent_image=first.out(0),
            )
        else:
            # 使用和用户原始工作流完全相同的原生采样节点，排除自定义采样语义/显存差异。
            sampled = g.node("SamplerCustomAdvanced", noise=noise.out(0), guider=guider.out(0), sampler=sampler.out(0), sigmas=sigmas, latent_image=sampling_ready.out(2))
        if hd_second_pass:
            # 真正的高清二采：一采AV latent先解码视频、按目标MP放大、重新编码视频，
            # 再把一采音频latent原样重组回NestedTensor，以独立低强度Sigma轨迹重绘。
            first_released = g.node("NanFengH3ReleaseBeforeDecode", samples=sampled.out(0))
            first_images = g.node("VAEDecode", samples=first_released.out(0), vae=video_vae.out(0))
            upscaled = g.node(
                "NanFengH3UpscaleForSecondPass", image=first_images.out(0),
                megapixels=float(kwargs.get("二采百万像素", 1.0)),
                method=str(kwargs.get("二采放大方法", "lanczos")),
            )
            encoded_video = g.node("VAEEncode", pixels=upscaled.out(0), vae=video_vae.out(0))
            rebuilt = g.node(
                "NanFengH3RebuildAVLatent", video_latent=encoded_video.out(0),
                source_av_latent=first_released.out(0),
            )
            try:
                import folder_paths
                installed_models = folder_paths.get_filename_list("diffusion_models")
            except Exception:
                installed_models = []
            second_model_name = _select_second_pass_model(
                kwargs.get("二采模型", SECOND_MODEL_SAME), installed_models, bool(fl_mode), selected_model,
            )
            # 条件张量直接复用一采结果，所以文本编码器不会重复加载/编码。独立屏障只在
            # 放大重编码完成后才卸载一采和VAE，然后加载用户选择的二采DiT，避免双模型并驻。
            second_ready = g.node(
                "NanFengH3ReleaseBeforeSecondModel", unet_name=second_model_name,
                conditioning=sampling_ready.out(1), latent=rebuilt.out(0),
            )
            second_model = g.node(
                "UNETLoader", unet_name=second_ready.out(0), weight_dtype=模型权重精度,
            ).out(0)
            if SageAttention != "disabled" and not (sol_enabled or t8_enabled):
                second_model = g.node(
                    "PathchSageAttentionKJ", model=second_model,
                    sage_attention=SageAttention, allow_compile=bool(允许编译),
                ).out(0)
            if sigma_enabled:
                second_model = g.node(
                    "MiniMaxH3SigmaShift", model=second_model,
                    shift_video=float(kwargs.get("视频西格玛偏移", 12.0)),
                    shift_audio=float(kwargs.get("音频西格玛偏移", 3.0)),
                ).out(0)
            second_guider = g.node("BasicGuider", model=second_model, conditioning=second_ready.out(1))
            second_sampler = g.node(
                "KSamplerSelect", sampler_name=str(kwargs.get("二采采样器", "res_multistep")),
            )
            second_sigmas = g.node(
                "BasicScheduler", model=second_model,
                scheduler=str(kwargs.get("二采调度器", "simple")),
                steps=int(kwargs.get("二采步数", 6)),
                denoise=1.0,
            )
            second_sigmas = g.node(
                "NanFengH3TrimSigmasAtStart", sigmas=second_sigmas.out(0),
                start_sigma=float(kwargs.get("二采起始Sigma", kwargs.get("二采降噪", 0.2))),
            )
            sampled = g.node(
                "SamplerCustomAdvanced", noise=noise.out(0), guider=second_guider.out(0),
                sampler=second_sampler.out(0), sigmas=second_sigmas.out(0),
                latent_image=second_ready.out(2),
            )
        released = g.node("NanFengH3ReleaseBeforeDecode", samples=sampled.out(0))
        image_decode = g.node("VAEDecode", samples=released.out(0), vae=video_vae.out(0))
        audio_decode = g.node("VAEDecodeAudio", samples=released.out(0), vae=audio_vae.out(0))

        legacy_face_refine = str(kwargs.get("启动准备", FACE_REFINE_OFF)) == FACE_REFINE_ON
        single_face_refine = bool(kwargs.get("单人小脸修复", False))
        multi_face_refine = bool(kwargs.get("多人小脸修复", False))
        if single_face_refine and multi_face_refine:
            raise ValueError("单人小脸修复与多人小脸修复只能开启一个，也可以全部关闭。")
        face_refine_enabled = isinstance(self, NanFengH3MultiReferenceGeneratorV6) and (
            legacy_face_refine or single_face_refine or multi_face_refine
        )
        final_images = image_decode.out(0)
        if face_refine_enabled:
            # 官方FaceRefine正确链路：成片逐帧追踪/裁剪 → 以追踪器动态画布重新建立
            # Ref2VA条件容器 → 把真实crop编码进AV latent → 按脸尺寸设置逐帧noise mask →
            # H3四步低强度重绘 → 解码 → 依照同一transform贴回原成片。
            # 二次修复统一使用Ref2VA容器：它允许0张参考图；I2VA/FL2VA则复用首/尾图片
            # 作为身份参考，但不把它们再次设成关键帧，避免局部crop被整帧构图强行拉扯。
            try:
                import folder_paths
                refine_lora = _select_face_refine_turbo_lora(folder_paths.get_filename_list("loras"))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f"无法读取H3修脸Turbo LoRA列表：{exc}") from exc
            identity_images = []
            if multi_face_refine:
                slots = [str(kwargs.get("人物1身份参考", "图片1")), str(kwargs.get("人物2身份参考", "图片2"))]
                indices = [int(slot.replace("图片", "")) - 1 if slot.startswith("图片") else -1 for slot in slots]
                positions = [str(kwargs.get("人物1图中位置", "自动（最大脸）")), str(kwargs.get("人物2图中位置", "自动（最大脸）"))]
                if any(index < 0 or index >= len(image_names) or not image_names[index] for index in indices):
                    raise ValueError("多人小脸修复需要从已上传素材中选择有效身份参考图。")
                if indices[0] == indices[1] and positions[0] == positions[1]:
                    raise ValueError("两人使用同一身份图时，必须选择同一张图中的不同人物位置。")
                for index, position in zip(indices, positions):
                    identity_load = g.node("LoadImage", image=image_names[index])
                    identity_limited = g.node(
                        "NanFengH3LimitImageLongEdge", image=identity_load.out(0), max_long_edge=1920,
                    )
                    identity_images.append(g.node(
                        "H3SelectIdentityFace", image=identity_limited.out(0),
                        detector="bbox\\face_yolov8m.pt", selection=position,
                        confidence=0.35, padding=0.55,
                    ).out(0))
            elif fl_mode in {"图生视频", "首尾帧"} and image_count:
                identity_images = [first_limited.out(0)]
            else:
                identity_images = [None]

            # 多人模式逐人建立完整独立链，并把上一人的贴回结果交给下一人；单人仍只运行一次原逻辑。
            for identity_image in identity_images:
                tracker_inputs = {
                    "images": final_images, "detector": "bbox\\face_yolov8m.pt",
                    "confidence": 0.35, "crop_factor": 2.5, "canvas_width": 512, "canvas_height": 512,
                    "canvas_mode": "auto_capped_768", "smooth_window": 11, "size_smooth_window": 81,
                    "smooth_method": "gaussian", "size_mode": "per_frame", "identity_track": True,
                    "identity_threshold": 0.28, "select": "largest", "fallback_detector": "none",
                    "fallback_head_frac": 0.5,
                }
                if identity_image is not None:
                    tracker_inputs["identity_reference"] = identity_image
                tracker = g.node("H3FaceTrackCrop", **tracker_inputs)
                refine_condition_inputs = {
                    "clip": clip.out(0), "vae": video_vae.out(0), "audio_vae": audio_vae.out(0),
                    "prompt": 提示词, "width": tracker.out(4), "height": tracker.out(5),
                    "length": length, "ref_image_size": "max",
                }
                if multi_face_refine:
                    # 每条链只接入本人的身份图，避免两个人在局部二采中互相串脸。
                    refine_condition_inputs["ref_images.ref_image_0"] = identity_image
                elif fl_mode in {"图生视频", "首尾帧"}:
                    refine_condition_inputs["ref_images.ref_image_0"] = first_limited.out(0)
                    if fl_mode == "首尾帧":
                        refine_condition_inputs["ref_images.ref_image_1"] = last_limited.out(0)
                elif not fl_mode:
                    for key, value in condition_inputs.items():
                        if key.startswith(("ref_images.", "ref_videos.", "ref_video_audios.", "ref_audios.")):
                            refine_condition_inputs[key] = value
                refine_prepared = g.node("MiniMaxH3ReferenceToVideo", **refine_condition_inputs)
                injected = g.node(
                    "H3InjectVideoLatent", av_latent=refine_prepared.out(1),
                    images=tracker.out(0), vae=video_vae.out(0),
                )
                refine_model = g.node(
                    "LoraLoaderModelOnly", model=sampling_model,
                    lora_name=refine_lora, strength_model=0.75,
                )
                audio_locked = g.node(
                    "MiniMaxH3NativeAudioLock", model=refine_model.out(0),
                    av_latent=injected.out(0), audio_vae=audio_vae.out(0), audio=audio_decode.out(0),
                )
                per_frame = g.node(
                    "H3PerFrameDenoise", av_latent=audio_locked.out(1), transform=tracker.out(1),
                    strength_small_face=0.80, strength_large_face=0.30,
                    scale_mode="absolute_px", face_px_small=30.0, face_px_large=120.0,
                    gamma=1.0, smooth_frames=25,
                )
                refine_ready = g.node(
                    "NanFengH3ReleaseBeforeSampling", model=audio_locked.out(0),
                    conditioning=refine_prepared.out(0), latent=per_frame.out(0),
                )
                refine_guider = g.node("BasicGuider", model=refine_ready.out(0), conditioning=refine_ready.out(1))
                refine_sigmas = g.node(
                    "BasicScheduler", model=refine_ready.out(0), scheduler="simple", steps=4, denoise=0.32,
                )
                refine_sampled = g.node(
                    "SamplerCustomAdvanced", noise=noise.out(0), guider=refine_guider.out(0),
                    sampler=sampler.out(0), sigmas=refine_sigmas.out(0), latent_image=refine_ready.out(2),
                )
                refine_released = g.node("NanFengH3ReleaseBeforeDecode", samples=refine_sampled.out(0))
                refined_crops = g.node("VAEDecode", samples=refine_released.out(0), vae=video_vae.out(0))
                stitched = g.node(
                    "H3FaceStitch", base_images=final_images, refined_crops=refined_crops.out(0),
                    transform=tracker.out(1), paste_region="face_only", mask_dilation=24,
                    feather=28, colour_match=1.0, blend=0.80,
                    undetected_frames="fade_out", feather_scales_with_crop=False,
                )
                final_images = stitched.out(0)
        return {"result": (final_images, audio_decode.out(0)), "expand": g.finalize()}


class NanFengH3MultiReferenceGeneratorV2(NanFengH3MultiReferenceGenerator):
    """V2：在V1完整行为之上追加LoRA与Blackwell Sol-Attn控制。"""

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = schema["required"]
        try:
            import folder_paths
            loras = folder_paths.get_filename_list("loras")
        except Exception:
            loras = []
        lora_choices = ["未选择"] + list(loras)
        # 只能追加，不能插入旧字段中间：保护ComfyUI按位置保存的旧工作流。
        required["启用LoRA"] = ("BOOLEAN", {"default": False})
        for index in range(1, 4):
            required[f"LoRA{index}"] = (lora_choices, {"default": "未选择"})
            required[f"LoRA{index}强度"] = ("FLOAT", {"default": 1.0, "min": -4.0, "max": 4.0, "step": 0.05})
        required["启用SolAttn"] = ("BOOLEAN", {"default": False})
        required["SolAttn_tau"] = ("FLOAT", {"default": 1.2, "min": 0.1, "max": 5.0, "step": 0.1})
        required["SolAttn阈值类型"] = (["diag", "exact"], {"default": "diag"})
        required["SolAttn精确模式"] = (["off", "exact_kv", "exact_kv_and_rows"], {"default": "exact_kv"})
        required["SolAttn完整末步"] = ("INT", {"default": 1, "min": 0, "max": 100, "step": 1})
        required["SolAttn末段比例"] = ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05})
        required["SolAttn前缀Token"] = ("INT", {"default": 0, "min": 0, "max": 1000000, "step": 128})
        return schema

    DESCRIPTION = "南风H3 V2：V1完整功能 + 3组模型LoRA + Blackwell Sol-Attn稀疏注意力加速。"


class NanFengH3MultiReferenceGeneratorV3(NanFengH3MultiReferenceGeneratorV2):
    """V3：V2全部功能 + MiniMax H3 Block Cache (T8)，提示词支持STRING连线输入。"""

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = schema["required"]
        # 只更新已有提示词字段的展示元数据，不插入或移动任何序列化字段：
        # 保留DOM文本框，同时在节点左侧暴露STRING连接口，可接南风提示词列表等上游输出。
        prompt_type, prompt_options = required["提示词"]
        required["提示词"] = (prompt_type, {**prompt_options, "defaultInput": True})
        required["启用T8缓存"] = ("BOOLEAN", {"default": False})
        required["T8残差阈值"] = ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01})
        required["T8开始比例"] = ("FLOAT", {"default": 0.08, "min": 0.0, "max": 1.0, "step": 0.01})
        required["T8结束比例"] = ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0, "step": 0.01})
        required["T8连续命中"] = ("INT", {"default": 2, "min": 1, "max": 10, "step": 1})
        required["T8缓存设备"] = (["cpu", "gpu"], {"default": "cpu"})
        required["T8指标步幅"] = ("INT", {"default": 8, "min": 1, "max": 32, "step": 1})
        required["T8详细日志"] = ("BOOLEAN", {"default": False})
        # 只能追加到V3既有字段末尾，避免旧工作流widgets_values位置整体错位。
        # 该字段只控制前端种子控件的control_after_generate；后端仍接收同一个随机种子整数。
        required["固定随机种子"] = ("BOOLEAN", {"default": False})
        return schema

    DESCRIPTION = "南风H3 V3：LoRA + Sage/Sol-Attn + MiniMax H3 Block Cache (T8)。"


class NanFengH3MultiReferenceGeneratorV4(NanFengH3MultiReferenceGeneratorV3):
    """V4：V3全部功能 + H3原生Sigma Shift、自定义Sigma及可选双阶段采样。"""

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = schema["required"]
        # 不移动既有字段；仅扩充现有画面比例选项。前端只在图生/首尾模式显示原图比例。
        ratio_options, ratio_config = required["画面比例"]
        required["画面比例"] = (["原图比例"] + list(ratio_options), ratio_config)
        # V4字段只能追加在V3完整序列末尾。DOM可把折叠视觉放到T8下方，不能移动序列化位置。
        required["启用西格玛调节"] = ("BOOLEAN", {"default": False})
        required["视频西格玛偏移"] = ("FLOAT", {"default": 12.0, "min": 0.01, "max": 100.0, "step": 0.01})
        required["音频西格玛偏移"] = ("FLOAT", {"default": 3.0, "min": 0.01, "max": 100.0, "step": 0.01})
        required["西格玛模式"] = (["低西格玛加密", "手动序列"], {"default": "低西格玛加密"})
        required["低西格玛开始"] = ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.01})
        required["低西格玛结束"] = ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01})
        required["每区间细分"] = ("INT", {"default": 2, "min": 1, "max": 8, "step": 1})
        required["加密曲线"] = (["cosine", "linear", "sine"], {"default": "cosine"})
        required["手动西格玛"] = ("STRING", {"default": "1, 0.988235, 0.972973, 0.952381, 0.923077, 0.878049, 0.8, 0.631579, 0", "multiline": True})
        required["启用双采样"] = ("BOOLEAN", {"default": False})
        required["双采后段比例"] = ("FLOAT", {"default": 0.5, "min": 0.05, "max": 0.95, "step": 0.05})
        required["双采后段采样器"] = (["res_multistep", "euler"], {"default": "res_multistep"})
        return schema

    DESCRIPTION = "南风H3 V4：V3完整功能 + 可关闭的Sigma Shift、低Sigma加密、手动Sigma与双阶段采样。"


class NanFengH3MultiReferenceGeneratorV5(NanFengH3MultiReferenceGeneratorV4):
    """V5：以真正的解码→放大→重编码→独立低强度H3二采取代V4 Sigma双阶段采样。"""

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        required = schema["required"]
        # V5继续严格追加，V1-V4的序列化Widget位置完全不动；V4旧双阶段字段仅隐藏/忽略。
        required["启用高清二采"] = ("BOOLEAN", {"default": False})
        required["一采步数"] = ("INT", {"default": 20, "min": 1, "max": 100, "step": 1})
        required["二采百万像素"] = (MEGAPIXELS, {"default": 1.0})
        required["二采放大方法"] = (["lanczos", "bicubic", "bilinear", "nearest-exact"], {"default": "lanczos"})
        required["二采步数"] = ("INT", {"default": 6, "min": 1, "max": 30, "step": 1})
        required["二采降噪"] = ("FLOAT", {"default": 0.2, "min": 0.05, "max": 0.6, "step": 0.01})
        required["二采采样器"] = (["res_multistep", "euler"], {"default": "res_multistep"})
        required["二采调度器"] = (["simple", "beta"], {"default": "simple"})
        try:
            import folder_paths
            installed = [x for x in folder_paths.get_filename_list("diffusion_models") if _is_h3_video_model(x)]
        except Exception:
            installed = []
        required["二采模型"] = ([SECOND_MODEL_SAME, SECOND_MODEL_AUTO] + installed, {"default": SECOND_MODEL_SAME})
        required["二采起始Sigma"] = ("FLOAT", {"default": 0.2, "min": 0.01, "max": 1.0, "step": 0.01})
        return schema

    DESCRIPTION = "南风H3 V5：V4完整功能 + 可选高清放大二采重绘；开启后主控步数失效，改用独立一采/二采步数。"


class NanFengH3MultiReferenceGeneratorV6(NanFengH3MultiReferenceGeneratorV5):
    """V6：V5完整功能 + 可选H3远景小脸追踪、局部重绘和时序贴回。"""

    @classmethod
    def INPUT_TYPES(cls):
        schema = super().INPUT_TYPES()
        # 旧下拉保留在原序列化位置，仅用于兼容已经保存的V6工作流；新界面使用两个互斥开关。
        schema["required"]["启动准备"] = ([FACE_REFINE_OFF, FACE_REFINE_ON], {"default": FACE_REFINE_OFF})
        schema["required"]["单人小脸修复"] = ("BOOLEAN", {"default": False})
        schema["required"]["多人小脸修复"] = ("BOOLEAN", {"default": False})
        identity_slots = [f"图片{i}" for i in range(1, 10)]
        schema["required"]["人物1身份参考"] = (identity_slots, {"default": "图片1"})
        schema["required"]["人物2身份参考"] = (identity_slots, {"default": "图片2"})
        identity_positions = ["自动（最大脸）", "最左人物", "左起第2人", "左起第3人", "最右人物"]
        schema["required"]["人物1图中位置"] = (identity_positions, {"default": "自动（最大脸）"})
        schema["required"]["人物2图中位置"] = (identity_positions, {"default": "自动（最大脸）"})
        return schema

    DESCRIPTION = "南风H3 V6：V5完整功能 + 可关闭、单人或双人H3 FaceRefine小脸修复。"


NODE_CLASS_MAPPINGS = {
    "NanFengH3MultiReferenceGenerator": NanFengH3MultiReferenceGenerator,
    "NanFengH3MultiReferenceGeneratorV2": NanFengH3MultiReferenceGeneratorV2,
    "NanFengH3MultiReferenceGeneratorV3": NanFengH3MultiReferenceGeneratorV3,
    "NanFengH3MultiReferenceGeneratorV4": NanFengH3MultiReferenceGeneratorV4,
    "NanFengH3MultiReferenceGeneratorV5": NanFengH3MultiReferenceGeneratorV5,
    "NanFengH3MultiReferenceGeneratorV6": NanFengH3MultiReferenceGeneratorV6,
    "NanFengH3ImageCanvasSize32": NanFengH3ImageCanvasSize32,
    "NanFengH3UpscaleForSecondPass": NanFengH3UpscaleForSecondPass,
    "NanFengH3RebuildAVLatent": NanFengH3RebuildAVLatent,
    "NanFengH3AddFinalSigmaStep": NanFengH3AddFinalSigmaStep,
    "NanFengH3TrimSigmasAtStart": NanFengH3TrimSigmasAtStart,
    "NanFengH3LimitImageLongEdge": NanFengH3LimitImageLongEdge,
    "NanFengH3ReleaseAtStart": NanFengH3ReleaseAtStart,
    "NanFengH3ReleaseBeforeConditionLoaders": NanFengH3ReleaseBeforeConditionLoaders,
    "NanFengH3ReleaseBeforeSecondModel": NanFengH3ReleaseBeforeSecondModel,
    "NanFengH3ReleaseBeforeConditioning": NanFengH3ReleaseBeforeConditioning,
    "NanFengH3ReleaseBeforeSampling": NanFengH3ReleaseBeforeSampling,
    "NanFengH3ReleaseBeforeDecode": NanFengH3ReleaseBeforeDecode,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "NanFengH3MultiReferenceGenerator": "南风H3多参视频生成",
    "NanFengH3MultiReferenceGeneratorV2": "南风H3多参视频生成V2",
    "NanFengH3MultiReferenceGeneratorV3": "南风H3多参视频生成V3",
    "NanFengH3MultiReferenceGeneratorV4": "南风H3多参视频生成V4",
    "NanFengH3MultiReferenceGeneratorV5": "南风H3多参视频生成V5",
    "NanFengH3MultiReferenceGeneratorV6": "南风H3多参视频生成V6",
    "NanFengH3ImageCanvasSize32": "南风H3 原图比例画布尺寸",
    "NanFengH3AddFinalSigmaStep": "南风H3 FL2VA末段微量Sigma修复",
    "NanFengH3ReleaseAtStart": "南风H3 开始前释放显存",
    "NanFengH3ReleaseBeforeConditionLoaders": "南风H3 V3条件模型加载前释放显存",
    "NanFengH3ReleaseBeforeConditioning": "南风H3 FL2VA条件前释放显存",
    "NanFengH3ReleaseBeforeSampling": "南风H3 条件后采样前释放显存",
    "NanFengH3ReleaseBeforeDecode": "南风H3 VAE前释放显存",
}

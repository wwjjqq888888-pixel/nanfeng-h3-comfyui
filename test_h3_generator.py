import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nanfeng_prompt_nodes.h3_generator", ROOT / "h3_generator.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_node_contract_is_image_and_audio_only():
    cls = MODULE.NanFengH3MultiReferenceGenerator
    assert cls.RETURN_TYPES == ("IMAGE", "AUDIO")
    assert cls.RETURN_NAMES == ("图像", "音频")
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGenerator"] == "南风H3多参视频生成"


def test_v2_schema_and_display_name_append_lora_and_sol_attn_controls():
    required = MODULE.NanFengH3MultiReferenceGeneratorV2.INPUT_TYPES()["required"]
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGeneratorV2"] == "南风H3多参视频生成V2"
    assert required["启用LoRA"][1]["default"] is False
    assert all(f"LoRA{i}" in required and f"LoRA{i}强度" in required for i in range(1, 4))
    assert required["启用SolAttn"][1]["default"] is False
    assert required["SolAttn_tau"][1]["default"] == 1.2
    assert required["SolAttn精确模式"][1]["default"] == "exact_kv"
    assert required["SolAttn完整末步"][1]["default"] == 1
    keys = list(required)
    assert keys.index("首尾帧") < keys.index("启用LoRA") < keys.index("启用SolAttn")


def test_v2_chain_is_base_then_lora_then_sage_then_sol_then_sampler():
    result = MODULE.NanFengH3MultiReferenceGeneratorV2().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "auto", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
        启用LoRA=True, LoRA1="h3_style.safetensors", LoRA1强度=0.8,
        LoRA2="未选择", LoRA2强度=1.0, LoRA3="未选择", LoRA3强度=1.0,
        启用SolAttn=True, SolAttn_tau=1.2, SolAttn阈值类型="diag", SolAttn精确模式="exact_kv",
        SolAttn完整末步=1, SolAttn末段比例=0.0, SolAttn前缀Token=0,
    )
    graph = result["expand"]
    ids = {node["class_type"]: node_id for node_id, node in graph.items() if node["class_type"] in {
        "UNETLoader", "LoraLoaderModelOnly", "PathchSageAttentionKJ", "SolAttnMiniMaxH3Patcher"
    }}
    lora = graph[ids["LoraLoaderModelOnly"]]
    sage = graph[ids["PathchSageAttentionKJ"]]
    sol = graph[ids["SolAttnMiniMaxH3Patcher"]]
    assert lora["inputs"]["model"] == [ids["UNETLoader"], 0]
    assert lora["inputs"]["strength_model"] == 0.8
    assert sage["inputs"]["model"] == [ids["LoraLoaderModelOnly"], 0]
    assert sol["inputs"]["model"] == [ids["PathchSageAttentionKJ"], 0]
    assert sol["inputs"]["tau"] == 1.2 and sol["inputs"]["exact_mode"] == "exact_kv"
    sampling_id, sampling_ready = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeSampling")
    assert sampling_ready["inputs"]["model"] == [ids["SolAttnMiniMaxH3Patcher"], 0]
    guider = next(node for node in graph.values() if node["class_type"] == "BasicGuider")
    scheduler = next(node for node in graph.values() if node["class_type"] == "BasicScheduler")
    assert guider["inputs"]["model"] == [sampling_id, 0]
    assert scheduler["inputs"]["model"] == [sampling_id, 0]


def test_v3_appends_fixed_seed_toggle_without_shifting_legacy_widgets():
    v2_keys = list(MODULE.NanFengH3MultiReferenceGeneratorV2.INPUT_TYPES()["required"])
    required = MODULE.NanFengH3MultiReferenceGeneratorV3.INPUT_TYPES()["required"]
    keys = list(required)
    assert required["固定随机种子"][1]["default"] is False
    assert keys[:len(v2_keys)] == v2_keys
    assert keys.index("T8详细日志") < keys.index("固定随机种子")


def test_v3_prompt_widget_exposes_a_string_socket_without_shifting_legacy_widgets():
    v2_required = MODULE.NanFengH3MultiReferenceGeneratorV2.INPUT_TYPES()["required"]
    v3_required = MODULE.NanFengH3MultiReferenceGeneratorV3.INPUT_TYPES()["required"]
    assert list(v3_required)[:len(v2_required)] == list(v2_required)
    prompt_type, prompt_options = v3_required["提示词"]
    assert prompt_type == "STRING"
    assert prompt_options["multiline"] is True
    assert prompt_options["defaultInput"] is True


def _generate_v4(**overrides):
    kwargs = {
        "图片1": "one.png",
        **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    }
    kwargs.update(overrides)
    return MODULE.NanFengH3MultiReferenceGeneratorV4().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 8, 1.0, **kwargs,
    )


def test_v4_schema_is_append_only_and_sigma_is_off_by_default():
    v3_keys = list(MODULE.NanFengH3MultiReferenceGeneratorV3.INPUT_TYPES()["required"])
    required = MODULE.NanFengH3MultiReferenceGeneratorV4.INPUT_TYPES()["required"]
    keys = list(required)
    assert keys[:len(v3_keys)] == v3_keys
    assert required["启用西格玛调节"][1]["default"] is False
    assert required["西格玛模式"][1]["default"] == "低西格玛加密"
    assert required["启用双采样"][1]["default"] is False
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGeneratorV4"] == "南风H3多参视频生成V4"
    assert "原图比例" in required["画面比例"][0]


def test_original_image_ratio_uses_selected_megapixels_instead_of_source_resolution():
    import torch
    node = MODULE.NanFengH3ImageCanvasSize32()
    assert node.calculate(torch.zeros((1, 1000, 1500, 3)), 0.6) == (960, 640)
    assert node.calculate(torch.zeros((1, 2000, 4000, 3)), 0.6) == (1120, 576)


def test_original_image_ratio_caps_long_edge_at_1920_after_megapixel_sizing():
    import torch
    node = MODULE.NanFengH3ImageCanvasSize32()
    assert node.calculate(torch.zeros((1, 2000, 4000, 3)), 2.0) == (1920, 960)


def test_v4_sigma_disabled_preserves_the_current_single_basic_scheduler_path():
    graph = _generate_v4(启用西格玛调节=False)["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert types.count("BasicScheduler") == 1
    assert types.count("SamplerCustomAdvanced") == 1
    assert "ManualSigmas" not in types
    assert "ExtendIntermediateSigmas" not in types
    assert "SplitSigmasDenoise" not in types
    assert "DisableNoise" not in types


def test_v4_manual_sigmas_can_split_into_two_real_sampler_passes():
    graph = _generate_v4(
        启用西格玛调节=True,
        西格玛模式="手动序列",
        手动西格玛="1, 0.95, 0.8, 0.6, 0.4, 0.2, 0",
        启用双采样=True,
        双采后段比例=0.5,
    )["expand"]
    manual_id, manual = next((i, n) for i, n in graph.items() if n["class_type"] == "ManualSigmas")
    split_id, split = next((i, n) for i, n in graph.items() if n["class_type"] == "SplitSigmasDenoise")
    samplers = [(i, n) for i, n in graph.items() if n["class_type"] == "SamplerCustomAdvanced"]
    disable_id = next(i for i, n in graph.items() if n["class_type"] == "DisableNoise")
    assert manual["inputs"]["sigmas"] == "1, 0.95, 0.8, 0.6, 0.4, 0.2, 0"
    assert split["inputs"] == {"sigmas": [manual_id, 0], "denoise": 0.5}
    assert len(samplers) == 2
    first_id, first = next((i, n) for i, n in samplers if n["inputs"]["sigmas"] == [split_id, 0])
    _, second = next((i, n) for i, n in samplers if n["inputs"]["sigmas"] == [split_id, 1])
    assert second["inputs"]["noise"] == [disable_id, 0]
    assert second["inputs"]["latent_image"] == [first_id, 0]


def test_v4_sigma_shift_is_after_sampling_barrier_and_feeds_both_guider_and_scheduler():
    graph = _generate_v4(启用西格玛调节=True, 视频西格玛偏移=12.0, 音频西格玛偏移=3.0)["expand"]
    barrier_id = next(i for i, n in graph.items() if n["class_type"] == "NanFengH3ReleaseBeforeSampling")
    shift_id, shift = next((i, n) for i, n in graph.items() if n["class_type"] == "MiniMaxH3SigmaShift")
    guider = next(n for n in graph.values() if n["class_type"] == "BasicGuider")
    scheduler = next(n for n in graph.values() if n["class_type"] == "BasicScheduler")
    assert shift["inputs"] == {"model": [barrier_id, 0], "shift_video": 12.0, "shift_audio": 3.0}
    assert guider["inputs"]["model"] == [shift_id, 0]
    assert scheduler["inputs"]["model"] == [shift_id, 0]


def test_v4_ref2va_without_lora_uses_the_user_ref_sigma_profile():
    graph = _generate_v4(
        启用西格玛调节=True,
        西格玛模式="低西格玛加密",
        低西格玛开始=0.8,
        低西格玛结束=0.0,
        每区间细分=3,
        加密曲线="cosine",
        启用双采样=False,
    )["expand"]
    scheduler_id = next(i for i, n in graph.items() if n["class_type"] == "BasicScheduler")
    extend_id, extend = next((i, n) for i, n in graph.items() if n["class_type"] == "ExtendIntermediateSigmas")
    sampler = next(n for n in graph.values() if n["class_type"] == "SamplerCustomAdvanced")
    assert extend["inputs"] == {
        "sigmas": [scheduler_id, 0], "steps": 3, "start_at_sigma": 0.8,
        "end_at_sigma": 0.0, "spacing": "cosine",
    }
    assert sampler["inputs"]["sigmas"] == [extend_id, 0]


def test_v4_fl2va_uses_exactly_one_final_high_frequency_sigma_step():
    graph = _generate_v4(
        启用西格玛调节=True,
        图生视频=True,
        图片1="one.png",
        西格玛模式="低西格玛加密",
        低西格玛开始=0.8,
        每区间细分=8,
    )["expand"]
    scheduler_id = next(i for i, n in graph.items() if n["class_type"] == "BasicScheduler")
    final_id, final_step = next((i, n) for i, n in graph.items() if n["class_type"] == "NanFengH3AddFinalSigmaStep")
    sampler = next(n for n in graph.values() if n["class_type"] == "SamplerCustomAdvanced")
    assert "ExtendIntermediateSigmas" not in [n["class_type"] for n in graph.values()]
    assert final_step["inputs"] == {"sigmas": [scheduler_id, 0]}
    assert sampler["inputs"]["sigmas"] == [final_id, 0]


def test_v4_lora_forces_native_sigma_path_even_when_sigma_switch_is_on():
    graph = _generate_v4(
        启用西格玛调节=True,
        启用LoRA=True,
        LoRA1="h3_style.safetensors",
        LoRA1强度=0.8,
    )["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert "LoraLoaderModelOnly" in types
    assert "MiniMaxH3SigmaShift" not in types
    assert "ExtendIntermediateSigmas" not in types
    assert "NanFengH3AddFinalSigmaStep" not in types
    assert types.count("BasicScheduler") == 1
    assert types.count("SamplerCustomAdvanced") == 1


def test_final_sigma_step_inserts_one_midpoint_only_in_the_last_interval():
    import torch
    node = MODULE.NanFengH3AddFinalSigmaStep()
    original = torch.tensor([1.0, 0.8, 0.4, 0.0])
    result, = node.add(original)
    assert torch.allclose(result, torch.tensor([1.0, 0.8, 0.4, 0.2, 0.0]))
    assert len(result) == len(original) + 1


@pytest.mark.parametrize("sigmas", ["", "1", "1, 0.8", "1, 0.8, 0.9, 0", "1, 0.8, 0.8, 0", "1, -0.1, 0"])
def test_v4_rejects_invalid_manual_sigma_sequences(sigmas):
    with pytest.raises(ValueError, match="手动西格玛"):
        _generate_v4(启用西格玛调节=True, 西格玛模式="手动序列", 手动西格玛=sigmas)


def test_v4_frontend_places_sigma_fold_after_t8_and_exposes_tuning_controls():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '"NanFengH3MultiReferenceGeneratorV4"' in source
    assert '"启用西格玛调节","启用西格玛调节","boolean"' in source
    assert '<summary>西格玛调节</summary>' in source
    assert "root.append(solDetails,t8Details,sigmaDetails,secondPassDetails)" in source
    assert "多参 Ref2VA" in source
    assert "I2V / T2V / 首尾帧" in source
    assert "LoRA（Sigma关闭）" in source
    assert "nfh3-sigma-profile-option" in source
    assert "nanfeng.h3.multi.reference.v50" in source


def _generate_v5(**overrides):
    main_steps = overrides.pop("采样步数", 20)
    kwargs = {
        "图片1": "one.png",
        **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    }
    kwargs.update(overrides)
    return MODULE.NanFengH3MultiReferenceGeneratorV5().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", main_steps, 1.0, **kwargs,
    )


def test_v5_schema_is_append_only_and_replaces_sigma_split_with_hd_second_pass():
    v4_required = MODULE.NanFengH3MultiReferenceGeneratorV4.INPUT_TYPES()["required"]
    required = MODULE.NanFengH3MultiReferenceGeneratorV5.INPUT_TYPES()["required"]
    keys = list(required)
    assert keys[:len(v4_required)] == list(v4_required)
    assert required["启用高清二采"][1]["default"] is False
    assert required["一采步数"][1]["default"] == 20
    assert required["二采步数"][1]["default"] == 6
    assert required["二采降噪"][1]["default"] == 0.2
    assert required["二采百万像素"][1]["default"] == 1.0
    assert "二采模型" in required
    assert required["二采模型"][1]["default"] == "跟随一采模型（质量优先）"
    assert required["二采起始Sigma"][1]["default"] == 0.2
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGeneratorV5"] == "南风H3多参视频生成V5"


def test_v5_second_pass_upscaler_never_silently_downscales():
    import torch
    node = MODULE.NanFengH3UpscaleForSecondPass()
    image = torch.zeros((4, 768, 1344, 3))
    result, width, height = node.upscale(image, 0.4, "lanczos")
    assert result is image
    assert (width, height) == (1344, 768)


def test_v5_hd_second_pass_decodes_upscales_reencodes_and_resamples_independently():
    graph = _generate_v5(
        启用高清二采=True,
        一采步数=14,
        二采步数=6,
        二采降噪=0.2,
        二采百万像素=1.0,
        二采放大方法="lanczos",
        二采起始Sigma=0.18,
    )["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert types.count("SamplerCustomAdvanced") == 2
    assert types.count("BasicScheduler") == 2
    assert "SplitSigmasDenoise" not in types
    assert "DisableNoise" not in types
    assert types.count("VAEDecode") == 2
    assert "NanFengH3UpscaleForSecondPass" in types
    assert "VAEEncode" in types
    assert "NanFengH3RebuildAVLatent" in types
    assert "NanFengH3TrimSigmasAtStart" in types
    assert types.count("UNETLoader") == 2
    assert types.count("CLIPLoader") == 1

    schedulers = [node for node in graph.values() if node["class_type"] == "BasicScheduler"]
    assert sorted(node["inputs"]["steps"] for node in schedulers) == [6, 14]
    assert all(node["inputs"]["denoise"] == 1.0 for node in schedulers)
    trim = next(node for node in graph.values() if node["class_type"] == "NanFengH3TrimSigmasAtStart")
    assert trim["inputs"]["start_sigma"] == 0.18

    first_decode_id, first_decode = next(
        (i, n) for i, n in graph.items()
        if n["class_type"] == "VAEDecode" and any(
            m["class_type"] == "NanFengH3UpscaleForSecondPass" and m["inputs"]["image"] == [i, 0]
            for m in graph.values()
        )
    )
    upscale_id, upscale = next((i, n) for i, n in graph.items() if n["class_type"] == "NanFengH3UpscaleForSecondPass")
    encode_id, encode = next((i, n) for i, n in graph.items() if n["class_type"] == "VAEEncode")
    rebuild_id, rebuild = next((i, n) for i, n in graph.items() if n["class_type"] == "NanFengH3RebuildAVLatent")
    assert upscale["inputs"]["image"] == [first_decode_id, 0]
    assert upscale["inputs"]["megapixels"] == 1.0
    assert encode["inputs"]["pixels"] == [upscale_id, 0]
    assert rebuild["inputs"]["video_latent"] == [encode_id, 0]


def test_v5_second_pass_model_auto_matches_ref2va_and_fl2va(monkeypatch):
    installed = [
        "H3/minimax_h3_ref2va_int8_convrot.safetensors",
        "H3/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
        "H3/minimax_h3_fl2va_int8_convrot.safetensors",
        "H3/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors",
    ]
    fake_folder_paths = SimpleNamespace(get_filename_list=lambda kind: installed if kind == "diffusion_models" else [])
    monkeypatch.setitem(sys.modules, "folder_paths", fake_folder_paths)
    ref_graph = _generate_v5(启用高清二采=True, 二采模型="自动轻量模型（Ref / FL匹配）")["expand"]
    ref_barrier = next(n for n in ref_graph.values() if n["class_type"] == "NanFengH3ReleaseBeforeSecondModel")
    assert ref_barrier["inputs"]["unet_name"] == "H3/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors"

    fl_graph = _generate_v5(
        启用高清二采=True, 二采模型="自动轻量模型（Ref / FL匹配）", 文生视频=True,
        图片1="未选择",
    )["expand"]
    fl_barrier = next(n for n in fl_graph.values() if n["class_type"] == "NanFengH3ReleaseBeforeSecondModel")
    assert fl_barrier["inputs"]["unet_name"] == "H3/minimax_h3_fl2va_pruned_w4a8_mixed.safetensors"


def test_v5_second_pass_model_defaults_to_same_first_model_for_quality(monkeypatch):
    installed = [
        "H3/minimax_h3_ref2va_int8_convrot.safetensors",
        "H3/minimax_h3_ref2va_pruned_w4a8_mixed.safetensors",
    ]
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: installed if kind == "diffusion_models" else []
    ))
    graph = _generate_v5(启用高清二采=True)["expand"]
    barrier = next(n for n in graph.values() if n["class_type"] == "NanFengH3ReleaseBeforeSecondModel")
    assert barrier["inputs"]["unet_name"] == "H3/minimax_h3_ref2va_int8_convrot.safetensors"


def test_v5_hd_second_pass_off_preserves_one_sampler_and_main_step_control():
    graph = _generate_v5(启用高清二采=False, 采样步数=17, 一采步数=14, 二采步数=6)["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert types.count("SamplerCustomAdvanced") == 1
    assert "NanFengH3UpscaleForSecondPass" not in types
    scheduler = next(node for node in graph.values() if node["class_type"] == "BasicScheduler")
    assert scheduler["inputs"]["steps"] == 17


def test_v5_hd_second_pass_and_global_sigma_are_mutually_exclusive_but_v4_is_unchanged():
    with pytest.raises(ValueError, match="高清二采.*西格玛调节.*不能同时开启"):
        _generate_v5(启用高清二采=True, 启用西格玛调节=True)

    graph = MODULE.NanFengH3MultiReferenceGeneratorV4().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
        启用西格玛调节=True, 启用双采样=True,
    )["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert "SplitSigmasDenoise" in types
    assert types.count("SamplerCustomAdvanced") == 2


def test_v5_frontend_has_independent_hd_second_pass_fold_and_disables_main_steps_when_enabled():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '"NanFengH3MultiReferenceGeneratorV5"' in source
    assert '<summary>高清放大二采重绘</summary>' in source
    assert "root.append(solDetails,t8Details,sigmaDetails,secondPassDetails)" in source
    assert 'widget(node,"启用高清二采")' in source
    assert 'widget(node,"采样步数")' in source
    assert "主控采样步数已停用" in source
    assert "二采起始Sigma" in source
    assert "高清二采与西格玛调节互斥" in source
    assert "nanfeng.h3.multi.reference.v50" in source


def test_h3_model_filter_accepts_third_party_fl2va_names_and_keeps_selected_fl2va(monkeypatch):
    """第三方H3权重不应因文件名没有 minimax_h3_ 前缀而被节点隐藏。"""
    pink = "H3\\PinkCherry_h3_fl2va_int8_convrot_v0.4-alpha.safetensors"
    standard = "H3\\minimax_h3_fl2va_int8_convrot.safetensors"
    fake_folder_paths = SimpleNamespace(
        get_filename_list=lambda kind: (
            [pink, standard] if kind == "diffusion_models" else
            [MODULE.DEFAULT_TEXT_ENCODER] if kind == "text_encoders" else
            [MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE]
        ),
        get_input_directory=lambda: str(ROOT),
    )
    monkeypatch.setitem(sys.modules, "folder_paths", fake_folder_paths)
    choices = MODULE.NanFengH3MultiReferenceGeneratorV3.INPUT_TYPES()["required"]["模型"][0]
    assert pink in choices
    assert MODULE._select_fl2va_model(pink, [pink, standard]) == pink
    assert MODULE._select_fl2va_model("H3\\minimax_h3_ref2va_int8_convrot.safetensors", [pink, standard]) == standard



def test_v3_frontend_labels_real_prompt_socket_and_locks_editor_when_linked():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert "function promptInput(node)" in source
    assert "function promptIsLinked(node)" in source
    assert "node.__nfh3SyncPromptConnection" in source
    assert "prompt.disabled=linked" in source
    assert 'slotName==="提示词"' in source
    assert "this.pos[1]+72" in source
    assert 'promptSlot.label="提示词列表输入"' in source
    assert 'className="nfh3-prompt-input-row"' not in source
    assert 'output.name==="图像"' in source
    assert 'output.name==="音频"' in source
    assert 'output.label="图像输出"' in source
    assert 'output.label="音频输出"' in source
    assert 'outputName==="图像"?52:72' in source
    assert "onConnectionsChange" in source


def test_v3_schema_and_chain_add_real_t8_after_sol_before_sampler():
    required = MODULE.NanFengH3MultiReferenceGeneratorV3.INPUT_TYPES()["required"]
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGeneratorV3"] == "南风H3多参视频生成V3"
    assert required["启用T8缓存"][1]["default"] is False
    assert required["T8残差阈值"][1]["default"] == 0.12
    assert required["T8开始比例"][1]["default"] == 0.08
    assert required["T8结束比例"][1]["default"] == 0.95
    assert required["T8连续命中"][1]["default"] == 2
    assert required["T8缓存设备"][1]["default"] == "cpu"
    assert required["T8指标步幅"][1]["default"] == 8

    result = MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "auto", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
        启用LoRA=True, LoRA1="h3_style.safetensors", LoRA1强度=0.8,
        LoRA2="未选择", LoRA2强度=1.0, LoRA3="未选择", LoRA3强度=1.0,
        启用SolAttn=False, SolAttn_tau=1.2, SolAttn阈值类型="diag", SolAttn精确模式="exact_kv",
        SolAttn完整末步=1, SolAttn末段比例=0.0, SolAttn前缀Token=0,
        启用T8缓存=True, T8残差阈值=0.12, T8开始比例=0.08, T8结束比例=0.95,
        T8连续命中=2, T8缓存设备="cpu", T8指标步幅=8, T8详细日志=False,
    )
    graph = result["expand"]
    ids = {node["class_type"]: node_id for node_id, node in graph.items() if node["class_type"] in {
        "UNETLoader", "LoraLoaderModelOnly", "PathchSageAttentionKJ", "MiniMaxH3BlockCacheT8"
    }}
    assert graph[ids["LoraLoaderModelOnly"]]["inputs"]["model"] == [ids["UNETLoader"], 0]
    # T8 uses exception-based block short-circuiting. Until its combination with the
    # generic Sage override is proven by a real cache-hit run, V3 must choose T8 only.
    assert "PathchSageAttentionKJ" not in ids
    t8 = graph[ids["MiniMaxH3BlockCacheT8"]]
    assert t8["inputs"]["model"] == [ids["LoraLoaderModelOnly"], 0]
    assert t8["inputs"]["residual_diff_threshold"] == 0.12
    sampling_id, sampling_ready = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeSampling")
    condition_loader_barrier_id, condition_loader_barrier = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeConditionLoaders")
    assert "model" not in condition_loader_barrier["inputs"]
    assert sampling_ready["inputs"]["model"] == [ids["MiniMaxH3BlockCacheT8"], 0]
    guider = next(node for node in graph.values() if node["class_type"] == "BasicGuider")
    scheduler = next(node for node in graph.values() if node["class_type"] == "BasicScheduler")
    assert guider["inputs"]["model"] == [sampling_id, 0]
    assert scheduler["inputs"]["model"] == [sampling_id, 0]


def test_v3_rejects_sol_and_t8_enabled_together():
    with pytest.raises(ValueError, match="不能同时开启"):
        MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
            "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
            MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
            "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
            "res_multistep", "simple", 20, 1.0,
            图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
            **{f"视频{i}": "未选择" for i in range(1, 4)},
            **{f"音频{i}": "未选择" for i in range(1, 4)},
            启用SolAttn=True, 启用T8缓存=True,
        )


def test_933_media_slots_exist():
    required = MODULE.NanFengH3MultiReferenceGenerator.INPUT_TYPES()["required"]
    assert all(f"图片{i}" in required for i in range(1, 10))
    assert all(f"视频{i}" in required for i in range(1, 4))
    assert all(f"音频{i}" in required for i in range(1, 4))
    assert required["提示词"][1]["default"] == ""
    assert required["百万像素"][1]["default"] == 0.4
    assert MODULE.DEFAULT_TEXT_ENCODER == "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    available_encoders = required["文本编码器"][0]
    expected_encoder = MODULE.DEFAULT_TEXT_ENCODER if MODULE.DEFAULT_TEXT_ENCODER in available_encoders else available_encoders[0]
    assert required["文本编码器"][1]["default"] == expected_encoder
    assert required["SageAttention"][1]["default"] == "auto"
    assert required["模型"][1]["default"].replace("\\", "/").endswith("minimax_h3_ref2va_int8_convrot.safetensors")
    assert "pruned" not in required["模型"][1]["default"].lower()
    assert required["文生视频"][1]["default"] is False
    assert required["图生视频"][1]["default"] is False
    assert required["首尾帧"][1]["default"] is False
    keys = list(required)
    assert keys.index("降噪强度") < keys.index("图片1") < keys.index("文生视频")


def test_duration_formula_matches_source_workflow():
    assert MODULE.duration_to_frames(5) == 124
    assert MODULE.duration_to_frames(8) == 192
    assert MODULE.duration_to_frames(15) == 362
    assert all((MODULE.duration_to_frames(x) - 5) % 17 == 0 for x in (1, 2.5, 5, 8, 10, 15))


def test_megapixel_table_matches_user_reference():
    expected = {
        0.2:(608,352), 0.3:(736,416), 0.4:(864,480), 0.5:(960,544),
        0.6:(1056,608), 0.7:(1152,640), 0.8:(1216,672), 0.9:(1280,736),
        0.98:(1344,768), 1.0:(1376,768), 1.2:(1504,832), 1.5:(1664,928),
        1.8:(1824,1024), 2.0:(1920,1088),
    }
    assert MODULE.MEGAPIXELS == list(expected)
    for mp, size in expected.items():
        assert MODULE.resolution_from_megapixels("16:9 (Widescreen)", mp, 32) == size


def test_native_mentions_include_video_soundtrack_audio_order():
    prompt = "@图片1 动作参考 @视频1，视频原声是 @视频音频1，额外声音 @音频1。"
    output = MODULE.build_native_prompt(prompt, 1, [True], 1)
    assert "<Picture 1>" in output
    assert "<Video 1>" in output
    assert "<Audio 1>" in output
    assert "<Audio 2>" in output


def test_unknown_mention_rejected():
    try:
        MODULE.build_native_prompt("使用 @图片2", 1, [], 0)
    except ValueError as exc:
        assert "@图片2" in str(exc)
    else:
        raise AssertionError("missing media mention must fail")


def test_generate_expands_to_native_cached_subgraph():
    result = MODULE.NanFengH3MultiReferenceGenerator().generate(
        MODULE.DEFAULT_MODEL_OPTIONS[0], MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.98, 32, 5, "@图片1 转头", 7, "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    )
    graph = result["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert types == ["NanFengH3ReleaseAtStart", "UNETLoader", "CLIPLoader", "VAELoader", "VAELoader", "LoadImage", "NanFengH3LimitImageLongEdge", "MiniMaxH3ReferenceToVideo", "NanFengH3ReleaseBeforeSampling", "RandomNoise", "BasicGuider", "KSamplerSelect", "BasicScheduler", "SamplerCustomAdvanced", "NanFengH3ReleaseBeforeDecode", "VAEDecode", "VAEDecodeAudio"]
    start_id, start = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseAtStart")
    loader = next(node for node in graph.values() if node["class_type"] == "UNETLoader")
    clip_loader = next(node for node in graph.values() if node["class_type"] == "CLIPLoader")
    video_vae_loader, audio_vae_loader = [node for node in graph.values() if node["class_type"] == "VAELoader"]
    assert start["inputs"]["unet_name"].replace("\\", "/").endswith("minimax_h3_ref2va_pruned_int8_convrot.safetensors")
    assert loader["inputs"]["unet_name"] == [start_id, 0]
    assert clip_loader["inputs"]["clip_name"] == [start_id, 1]
    assert video_vae_loader["inputs"]["vae_name"] == [start_id, 2]
    assert audio_vae_loader["inputs"]["vae_name"] == [start_id, 3]
    prepare = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ReferenceToVideo")
    assert prepare["inputs"]["prompt"] == "<Picture 1> 转头"
    assert (prepare["inputs"]["width"], prepare["inputs"]["height"], prepare["inputs"]["length"]) == (1344, 768, 124)
    assert result["result"][0][1] == 0 and result["result"][1][1] == 0
    release_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeDecode")
    image_decode = next(node for node in graph.values() if node["class_type"] == "VAEDecode")
    audio_decode = next(node for node in graph.values() if node["class_type"] == "VAEDecodeAudio")
    assert image_decode["inputs"]["samples"] == [release_id, 0]
    assert audio_decode["inputs"]["samples"] == [release_id, 0]


def test_v3_sol_wrapper_is_not_behind_aggressive_release_that_destroys_flex_compile_state():
    result = MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
        启用SolAttn=True, SolAttn_tau=1.4, SolAttn阈值类型="diag", SolAttn精确模式="exact_kv",
        SolAttn完整末步=1, SolAttn末段比例=0.0, SolAttn前缀Token=0,
    )
    graph = result["expand"]
    sampling_barrier_id, sampling_barrier = next((node_id, n) for node_id, n in graph.items() if n["class_type"] == "NanFengH3ReleaseBeforeSampling")
    sol_id, sol = next((node_id, n) for node_id, n in graph.items() if n["class_type"] == "SolAttnMiniMaxH3Patcher")
    assert sol["inputs"]["model"] == [sampling_barrier_id, 0]
    assert sampling_barrier["inputs"]["model"][0] != sol_id


def test_v3_conditioning_phase_does_not_depend_on_dit_patcher_or_force_it_to_prepare_first():
    result = MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    )
    graph = result["expand"]
    barrier_id, barrier = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeConditionLoaders")
    assert "model" not in barrier["inputs"]
    clip_loader = next(node for node in graph.values() if node["class_type"] == "CLIPLoader")
    assert clip_loader["inputs"]["clip_name"] == [barrier_id, 0]


def test_v3_sol_bypasses_sage_override_instead_of_stacking_two_attention_patches():
    result = MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "auto", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
        启用SolAttn=True, SolAttn_tau=1.2, SolAttn阈值类型="diag", SolAttn精确模式="exact_kv",
        SolAttn完整末步=1, SolAttn末段比例=0.0, SolAttn前缀Token=0,
    )
    types = [node["class_type"] for node in result["expand"].values()]
    assert "SolAttnMiniMaxH3Patcher" in types
    assert "PathchSageAttentionKJ" not in types


def test_aggressive_release_resets_dynamic_cast_buffers_after_unloading():
    calls = []

    class FakeMM:
        @staticmethod
        def unload_all_models(): calls.append("unload")
        @staticmethod
        def reset_cast_buffers(): calls.append("reset_cast_buffers")
        @staticmethod
        def cleanup_models(): calls.append("cleanup_models")
        @staticmethod
        def cleanup_models_gc(): calls.append("cleanup_models_gc")
        @staticmethod
        def soft_empty_cache(force=False): calls.append(("soft_empty_cache", force))
        @staticmethod
        def get_free_memory(torch_free_too=False):
            return (30 * 1024**3, 0) if torch_free_too else 30 * 1024**3

    MODULE._aggressive_h3_vram_release(FakeMM, lambda: calls.append("gc"))
    assert calls == [
        "unload", "reset_cast_buffers", "gc", "cleanup_models",
        "cleanup_models_gc", ("soft_empty_cache", True),
    ]


def test_start_release_is_changed_every_queue_not_merely_node_id_scoped():
    # NOT_IDEMPOTENT only adds the stable node id to ComfyUI's cache key; it does not force a rerun.
    # NaN is intentionally unequal to itself, so every queued H3 task executes the release barrier.
    assert math.isnan(MODULE.NanFengH3ReleaseAtStart.IS_CHANGED())
    assert math.isnan(MODULE.NanFengH3ReleaseBeforeConditionLoaders.IS_CHANGED())
    assert math.isnan(MODULE.NanFengH3ReleaseBeforeConditioning.IS_CHANGED())
    assert math.isnan(MODULE.NanFengH3ReleaseBeforeSampling.IS_CHANGED())


def test_ref2va_has_release_barrier_before_conditioning_loads_clip_and_vaes_after_unet():
    result = MODULE.NanFengH3MultiReferenceGeneratorV3().generate(
        MODULE.DEFAULT_MODEL_OPTIONS[0], MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.98, 32, 5, "@图片1 转头", 7, "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    )
    graph = result["expand"]
    unet_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "UNETLoader")
    barrier_id, barrier = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeConditionLoaders")
    assert "model" not in barrier["inputs"]
    clip_loader = next(node for node in graph.values() if node["class_type"] == "CLIPLoader")
    vae_loaders = [node for node in graph.values() if node["class_type"] == "VAELoader"]
    assert clip_loader["inputs"]["clip_name"] == [barrier_id, 0]
    assert vae_loaders[0]["inputs"]["vae_name"] == [barrier_id, 1]
    assert vae_loaders[1]["inputs"]["vae_name"] == [barrier_id, 2]


def test_video_and_audio_are_native_subnodes_not_custom_helpers():
    result = MODULE.NanFengH3MultiReferenceGenerator().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "auto", False,
        "9:16 (Portrait Widescreen)", 0.4, 32, 8, "<Video 1> <Audio 2>", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        视频1="one.mp4", 视频2="未选择", 视频3="未选择",
        音频1="one.wav", 音频2="未选择", 音频3="未选择",
    )
    graph = result["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert "NanFengH3PrepareReferences" not in types
    assert "NanFengH3ProgressSampler" not in types
    assert "LoadVideo" in types and "GetVideoComponents" in types and "LoadAudio" in types
    condition = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ReferenceToVideo")
    assert "ref_videos.ref_video_0" in condition["inputs"]
    assert "ref_video_audios.ref_video_audio_0" in condition["inputs"]
    assert "ref_audios.ref_audio_0" in condition["inputs"]


def test_sage_auto_matches_actual_f_drive_workflow_and_feeds_guider_scheduler():
    result = MODULE.NanFengH3MultiReferenceGenerator().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "auto", False,
        "9:16 (Portrait Widescreen)", 0.4, 32, 8, "<Picture 1> test", 7,
        "res_multistep", "simple", 20, 1.0,
        图片1="one.png", **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    )
    graph = result["expand"]
    patch_id, patch = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "PathchSageAttentionKJ")
    assert patch["inputs"]["sage_attention"] == "auto"
    assert patch["inputs"]["allow_compile"] is False
    sampling_id, sampling_ready = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeSampling")
    assert sampling_ready["inputs"]["model"] == [patch_id, 0]
    guider = next(node for node in graph.values() if node["class_type"] == "BasicGuider")
    scheduler = next(node for node in graph.values() if node["class_type"] == "BasicScheduler")
    assert guider["inputs"]["model"] == [sampling_id, 0]
    assert scheduler["inputs"]["model"] == [sampling_id, 0]


def _generate_fl(*, text=False, image=False, first_last=False, images=()):
    slots = {f"图片{i}": (images[i - 1] if i <= len(images) else "未选择") for i in range(1, 10)}
    return MODULE.NanFengH3MultiReferenceGenerator().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "camera move", 7, "res_multistep", "simple", 20,
        1.0, "match", 文生视频=text, 图生视频=image, 首尾帧=first_last, **slots,
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    )


def test_fl_modes_are_mutually_exclusive_and_validate_required_frames():
    with pytest.raises(ValueError, match="只能开启一个"):
        _generate_fl(text=True, image=True)
    with pytest.raises(ValueError, match="必须上传1张"):
        _generate_fl(image=True)
    with pytest.raises(ValueError, match="必须上传2张"):
        _generate_fl(first_last=True, images=("first.png",))


@pytest.mark.parametrize("mode,images,expected_inputs", [
    ("text", (), set()),
    ("image", ("first.png",), {"first_frame"}),
    ("first_last", ("first.png", "last.png"), {"first_frame", "last_frame"}),
])
def test_fl_modes_switch_model_and_expand_exact_native_i2v_graph(mode, images, expected_inputs):
    result = _generate_fl(text=mode == "text", image=mode == "image", first_last=mode == "first_last", images=images)
    graph = result["expand"]
    start = next(node for node in graph.values() if node["class_type"] == "NanFengH3ReleaseAtStart")
    assert start["inputs"]["unet_name"].replace("\\", "/").endswith("minimax_h3_fl2va_int8_convrot.safetensors")
    condition = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
    release_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "NanFengH3ReleaseBeforeConditioning")
    assert condition["inputs"]["clip"] == [release_id, 0]
    assert condition["inputs"]["vae"] == [release_id, 1]
    assert {key for key in ("first_frame", "last_frame") if key in condition["inputs"]} == expected_inputs
    assert not any(node["class_type"] in {"LoadVideo", "GetVideoComponents", "LoadAudio", "MiniMaxH3ReferenceToVideo"} for node in graph.values())


def test_fl_image_inputs_are_limited_to_1920_before_native_i2v_conditioning():
    graph = _generate_fl(image=True, images=("first.png",))["expand"]
    load_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "LoadImage")
    limit_id, limit_node = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3LimitImageLongEdge")
    condition = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
    assert limit_node["inputs"] == {"image": [load_id, 0], "max_long_edge": 1920}
    assert condition["inputs"]["first_frame"] == [limit_id, 0]


@pytest.mark.parametrize("mode,images", [("image", ("first.png",)), ("first_last", ("first.png", "last.png"))])
def test_v4_original_ratio_uses_limited_first_frame_canvas_size(mode, images):
    slots = {f"图片{i}": (images[i - 1] if i <= len(images) else "未选择") for i in range(1, 10)}
    result = MODULE.NanFengH3MultiReferenceGeneratorV4().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "原图比例", 0.4, 32, 5, "camera move", 7, "res_multistep", "simple", 20, 1.0,
        文生视频=False, 图生视频=mode == "image", 首尾帧=mode == "first_last", **slots,
        **{f"视频{i}": "未选择" for i in range(1, 4)}, **{f"音频{i}": "未选择" for i in range(1, 4)},
    )
    graph = result["expand"]
    first_limit_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "NanFengH3LimitImageLongEdge")
    size_id, size = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3ImageCanvasSize32")
    condition = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ImageToVideo")
    assert size["inputs"] == {"image": [first_limit_id, 0], "megapixels": 0.4}
    assert condition["inputs"]["width"] == [size_id, 0]
    assert condition["inputs"]["height"] == [size_id, 1]


def test_v4_original_ratio_is_rejected_outside_image_modes():
    slots = {"图片1": "one.png", **{f"图片{i}": "未选择" for i in range(2, 10)}}
    with pytest.raises(ValueError, match="只适用于图生视频或首尾帧"):
        MODULE.NanFengH3MultiReferenceGeneratorV4().generate(
            "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
            MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
            "原图比例", 0.4, 32, 5, "test", 7, "res_multistep", "simple", 20, 1.0,
            文生视频=False, 图生视频=False, 首尾帧=False, **slots,
            **{f"视频{i}": "未选择" for i in range(1, 4)}, **{f"音频{i}": "未选择" for i in range(1, 4)},
        )


def test_ref2va_image_inputs_are_limited_to_1920_and_ignore_legacy_reference_size():
    graph = _generate_fl(images=("one.png",))["expand"]
    load_id = next(node_id for node_id, node in graph.items() if node["class_type"] == "LoadImage")
    limit_id, limit_node = next((node_id, node) for node_id, node in graph.items() if node["class_type"] == "NanFengH3LimitImageLongEdge")
    condition = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3ReferenceToVideo")
    assert limit_node["inputs"] == {"image": [load_id, 0], "max_long_edge": 1920}
    assert condition["inputs"]["ref_images.ref_image_0"] == [limit_id, 0]
    assert condition["inputs"]["ref_image_size"] == "max"


def test_v4_frontend_removes_legacy_reference_size_control():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    panel_fields = source.split("const PANEL_FIELDS = [", 1)[1].split("];", 1)[0]
    assert '"参考图尺寸"' not in panel_fields
    assert "参考图最长边固定1920" in source
    assert "原图比例" in source
    assert "首帧只决定宽高比" in source


def test_v6_frontend_mode_switches_never_change_the_selected_model():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert "modelForMode" not in source
    assert 'setWidget(node,"模型"' not in source
    assert 'if(mode)setWidget(this,"模型"' not in source


def test_v6_backend_mode_switches_use_the_exact_user_selected_model(monkeypatch):
    selected = "H3/custom_h3_ref2va_quality_model.safetensors"
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: [selected, "H3/minimax_h3_fl2va_int8_convrot.safetensors"]
    ))
    for mode in ("文生视频", "图生视频", "首尾帧"):
        kwargs = {"图片1": "未选择"}
        if mode == "图生视频":
            kwargs["图片1"] = "first.png"
        elif mode == "首尾帧":
            kwargs.update(图片1="first.png", 图片2="last.png")
        graph = MODULE.NanFengH3MultiReferenceGeneratorV6().generate(
            selected, MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
            MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
            "16:9 (Widescreen)", 0.4, 32, 5, "test", 7, "res_multistep", "simple", 8, 1.0,
            **{mode: True}, **kwargs,
            **{f"图片{i}": "未选择" for i in range(3 if mode == "首尾帧" else 2, 10)},
            **{f"视频{i}": "未选择" for i in range(1, 4)},
            **{f"音频{i}": "未选择" for i in range(1, 4)},
        )["expand"]
        start = next(node for node in graph.values() if node["class_type"] == "NanFengH3ReleaseAtStart")
        assert start["inputs"]["unet_name"] == selected


def test_long_edge_limiter_preserves_small_images_and_downscales_large_images(monkeypatch):
    import torch
    calls = []
    monkeypatch.setitem(sys.modules, "comfy.utils", SimpleNamespace(
        common_upscale=lambda samples, width, height, method, crop: calls.append((width, height, method, crop)) or torch.zeros(
            (samples.shape[0], samples.shape[1], height, width), dtype=samples.dtype
        )
    ))
    node = MODULE.NanFengH3LimitImageLongEdge()
    small = torch.zeros((1, 800, 1200, 3))
    small_out, = node.limit(small, 1920)
    assert small_out is small and calls == []
    large = torch.zeros((1, 2000, 4000, 3))
    large_out, = node.limit(large, 1920)
    assert large_out.shape == (1, 960, 1920, 3)
    assert calls == [(1920, 960, "lanczos", "disabled")]


def test_all_modes_off_preserves_ref2va_behavior():
    result = _generate_fl(images=("one.png",))
    assert any(node["class_type"] == "MiniMaxH3ReferenceToVideo" for node in result["expand"].values())


def _generate_v6(**overrides):
    kwargs = {
        "图片1": "one.png",
        **{f"图片{i}": "未选择" for i in range(2, 10)},
        **{f"视频{i}": "未选择" for i in range(1, 4)},
        **{f"音频{i}": "未选择" for i in range(1, 4)},
    }
    kwargs.update(overrides)
    return MODULE.NanFengH3MultiReferenceGeneratorV6().generate(
        "H3/minimax_h3_ref2va_int8_convrot.safetensors", MODULE.DEFAULT_TEXT_ENCODER, "minimax", "default",
        MODULE.DEFAULT_VIDEO_VAE, MODULE.DEFAULT_AUDIO_VAE, "default", "disabled", False,
        "16:9 (Widescreen)", 0.4, 32, 5, "<Picture 1> test", 7,
        "res_multistep", "simple", 8, 1.0, **kwargs,
    )


def test_v6_schema_is_append_only_and_face_refine_is_off_by_default():
    v5_required = MODULE.NanFengH3MultiReferenceGeneratorV5.INPUT_TYPES()["required"]
    required = MODULE.NanFengH3MultiReferenceGeneratorV6.INPUT_TYPES()["required"]
    assert list(required)[:len(v5_required)] == list(v5_required)
    assert required["启动准备"][1]["default"] == MODULE.FACE_REFINE_OFF
    assert MODULE.NODE_DISPLAY_NAME_MAPPINGS["NanFengH3MultiReferenceGeneratorV6"] == "南风H3多参视频生成V6"


def test_v6_schema_adds_mutually_exclusive_single_and_multi_face_refine_controls():
    required = MODULE.NanFengH3MultiReferenceGeneratorV6.INPUT_TYPES()["required"]
    assert required["单人小脸修复"][1]["default"] is False
    assert required["多人小脸修复"][1]["default"] is False
    assert required["人物1身份参考"][1]["default"] == "图片1"
    assert required["人物2身份参考"][1]["default"] == "图片2"
    assert required["人物1图中位置"][1]["default"] == "自动（最大脸）"
    assert required["人物2图中位置"][1]["default"] == "自动（最大脸）"


def test_v6_frontend_labels_face_refine_and_renders_exclusive_switches():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '["__小脸修复","小脸修复","face-refine-switches"]' in source
    assert 'for(const mode of ["单人小脸修复","多人小脸修复"])' in source
    assert 'turnOn&&other===mode' in source


def test_v6_frontend_clearly_labels_sampling_scope_and_acceleration_compatibility():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '高级模型、注意力与主采样设置（一采）' in source
    assert 'Sol-Attn Blackwell 加速（RTX 5090可开启）' in source
    assert 'MiniMax H3 Block Cache T8（通用加速，可开启）' in source
    assert 'Sage之后' not in source
    assert 'Sol-Attn之后、采样前' not in source
    assert '小脸修复使用固定独立4步FaceRefine' in source
    assert '高清二采开启后，改用“高清放大二采重绘”里的独立一采步数和二采步数' in source


def test_v6_frontend_has_persistent_storyboards_with_new_copy_delete_semantics():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'nanfeng_storyboards' in source
    assert '新建分镜' in source
    assert '复制分镜' in source
    assert '删除分镜' in source
    assert 'captureStoryboard' in source
    assert 'applyStoryboard' in source
    assert 'prompt:"",图片:[],视频:[],音频:[]' in source
    assert 'structuredClone' in source
    assert 'shots.length<=1' in source


def test_v6_frontend_doubles_prompt_editor_height_and_shows_selectable_shot_tabs():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'height:clamp(176px,34cqw,270px)' in source
    assert 'className="nfh3-storyboard-tabs"' in source
    assert '`分镜 ${i+1}`' in source


def test_v6_storyboard_layout_wraps_evenly_and_expands_without_horizontal_scroll():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '.nfh3-storyboard-tabs{display:grid;grid-template-columns:repeat(auto-fit,minmax(86px,1fr))' in source
    assert 'overflow-x:auto' not in source
    assert '.nfh3-storyboard-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))' in source
    assert 'storyboardActions.className="nfh3-storyboard-actions"' in source
    assert 'storyboardBar.append(storyboardTabs,storyboardActions)' in source


def test_v6_face_refine_off_preserves_v5_output_path():
    graph = _generate_v6(启动准备=MODULE.FACE_REFINE_OFF)["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert "H3FaceTrackCrop" not in types
    assert "H3InjectVideoLatent" not in types
    assert "H3PerFrameDenoise" not in types
    assert "H3FaceStitch" not in types


def test_v6_rejects_enabling_single_and_multi_face_refine_together():
    with pytest.raises(ValueError, match="单人小脸修复与多人小脸修复只能开启一个"):
        _generate_v6(单人小脸修复=True, 多人小脸修复=True)


def test_v6_face_refine_builds_official_tracker_inject_denoise_sample_stitch_chain(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    result = _generate_v6(单人小脸修复=True)
    graph = result["expand"]
    by_type = {}
    for node_id, node in graph.items():
        by_type.setdefault(node["class_type"], []).append((node_id, node))
    tracker_id, tracker = by_type["H3FaceTrackCrop"][0]
    assert tracker["inputs"]["images"] in ([i, 0] for i, _ in by_type["VAEDecode"])
    assert tracker["inputs"]["canvas_mode"] == "auto_capped_768"
    prepared_id, prepared = by_type["MiniMaxH3ReferenceToVideo"][-1]
    assert prepared["inputs"]["width"] == [tracker_id, 4]
    assert prepared["inputs"]["height"] == [tracker_id, 5]
    inject_id, inject = by_type["H3InjectVideoLatent"][0]
    assert inject["inputs"]["av_latent"] == [prepared_id, 1]
    assert inject["inputs"]["images"] == [tracker_id, 0]
    audio_lock_id, audio_lock = by_type["MiniMaxH3NativeAudioLock"][0]
    assert audio_lock["inputs"]["av_latent"] == [inject_id, 0]
    assert audio_lock["inputs"]["audio_vae"] in ([i, 0] for i, _ in by_type["VAELoader"])
    assert audio_lock["inputs"]["audio"] in ([i, 0] for i, _ in by_type["VAEDecodeAudio"])
    per_frame_id, per_frame = by_type["H3PerFrameDenoise"][0]
    assert per_frame["inputs"]["av_latent"] == [audio_lock_id, 1]
    assert per_frame["inputs"]["transform"] == [tracker_id, 1]
    refine_lora = by_type["LoraLoaderModelOnly"][-1][1]
    assert refine_lora["inputs"]["lora_name"].endswith("turbo_4step_ema_ckpt850_pruned_comfyui.safetensors")
    assert refine_lora["inputs"]["strength_model"] == 0.75
    refine_scheduler = by_type["BasicScheduler"][-1][1]
    assert refine_scheduler["inputs"]["steps"] == 4
    assert refine_scheduler["inputs"]["denoise"] == 0.32
    stitch_id, stitch = by_type["H3FaceStitch"][0]
    assert stitch["inputs"]["transform"] == [tracker_id, 1]
    assert stitch["inputs"]["paste_region"] == "face_only"
    assert result["result"][0] == [stitch_id, 0]


def test_v6_multi_face_refine_builds_two_identity_locked_independent_chains(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    graph = _generate_v6(
        图片1="person-a.png", 图片2="person-b.png",
        多人小脸修复=True, 人物1身份参考="图片1", 人物2身份参考="图片2",
    )["expand"]
    by_type = {}
    for node_id, node in graph.items():
        by_type.setdefault(node["class_type"], []).append((node_id, node))
    assert len(by_type["H3FaceTrackCrop"]) == 2
    assert len(by_type["H3InjectVideoLatent"]) == 2
    assert len(by_type["H3PerFrameDenoise"]) == 2
    assert len(by_type["H3FaceStitch"]) == 2
    identities = [node["inputs"]["identity_reference"] for _, node in by_type["H3FaceTrackCrop"]]
    assert identities[0] != identities[1]
    first_stitch_id = by_type["H3FaceStitch"][0][0]
    second_stitch = by_type["H3FaceStitch"][1][1]
    assert second_stitch["inputs"]["base_images"] == [first_stitch_id, 0]


def test_v6_multi_face_refine_requires_distinct_people_when_using_one_identity_image(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    with pytest.raises(ValueError, match="同一张图中的不同人物位置"):
        _generate_v6(多人小脸修复=True, 人物1身份参考="图片1", 人物2身份参考="图片1")


def test_v6_multi_face_refine_can_select_left_and_right_people_from_same_image(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    graph = _generate_v6(
        图片1="two-people.png", 多人小脸修复=True,
        人物1身份参考="图片1", 人物2身份参考="图片1",
        人物1图中位置="最左人物", 人物2图中位置="最右人物",
    )["expand"]
    selectors = [node for node in graph.values() if node["class_type"] == "H3SelectIdentityFace"]
    assert [node["inputs"]["selection"] for node in selectors] == ["最左人物", "最右人物"]
    trackers = [node for node in graph.values() if node["class_type"] == "H3FaceTrackCrop"]
    assert len(trackers) == 2
    assert trackers[0]["inputs"]["identity_reference"] != trackers[1]["inputs"]["identity_reference"]


def test_v6_multi_face_refine_rejects_same_image_and_same_person_selection(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    with pytest.raises(ValueError, match="同一张图中的不同人物位置"):
        _generate_v6(
            图片1="two-people.png", 多人小脸修复=True,
            人物1身份参考="图片1", 人物2身份参考="图片1",
            人物1图中位置="最左人物", 人物2图中位置="最左人物",
        )


def test_face_refine_external_identity_never_falls_through_to_the_only_other_face():
    source = ROOT / "integrations" / "ComfyUI-H3-FaceRefine" / "nodes.py"
    text = source.read_text(encoding="utf-8")
    assert "strict_identity = identity_reference is not None and ref_emb is not None" in text
    assert "if strict_identity:" in text
    assert "else:\n                    continue" in text


@pytest.mark.parametrize("mode,image_values", [
    ("文生视频", {}),
    ("图生视频", {"图片1": "first.png"}),
    ("首尾帧", {"图片1": "first.png", "图片2": "last.png"}),
])
def test_v6_face_refine_supports_all_fl_modes_with_universal_refine_conditioning(monkeypatch, mode, image_values):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    overrides = {"启动准备": MODULE.FACE_REFINE_ON, mode: True, **image_values}
    if mode == "文生视频":
        overrides["图片1"] = "未选择"
    graph = _generate_v6(**overrides)["expand"]
    types = [node["class_type"] for node in graph.values()]
    assert types.count("H3FaceTrackCrop") == 1
    assert types.count("H3InjectVideoLatent") == 1
    assert types.count("H3PerFrameDenoise") == 1
    assert types.count("H3FaceStitch") == 1
    # 二次修复统一使用Ref2VA条件容器；T2VA允许零参考，I2VA/FL2VA复用首尾图锁身份。
    assert types.count("MiniMaxH3ReferenceToVideo") == 1


def test_v6_face_refine_uses_temporally_stable_pullout_defaults(monkeypatch):
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(
        get_filename_list=lambda kind: ["H3/minimax_h3_turbo_4step_ema_ckpt850_pruned_comfyui.safetensors"] if kind == "loras" else []
    ))
    graph = _generate_v6(单人小脸修复=True)["expand"]
    by_type = {}
    for node in graph.values():
        by_type.setdefault(node["class_type"], []).append(node)
    tracker = by_type["H3FaceTrackCrop"][0]
    per_frame = by_type["H3PerFrameDenoise"][0]
    scheduler = by_type["BasicScheduler"][-1]
    stitch = by_type["H3FaceStitch"][0]
    assert tracker["inputs"]["smooth_window"] <= 15
    assert tracker["inputs"]["size_smooth_window"] >= 71
    assert per_frame["inputs"]["smooth_frames"] >= 21
    assert per_frame["inputs"]["strength_small_face"] <= 0.85
    assert scheduler["inputs"]["denoise"] <= 0.35
    assert stitch["inputs"]["blend"] <= 0.85

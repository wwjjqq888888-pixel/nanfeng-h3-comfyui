from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nanfeng_v10_dynamic_lora", ROOT / "h3_generator.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_v10_schema_appends_eight_individually_switchable_lora_slots():
    required = MODULE.NanFengH3MultiReferenceGeneratorV10.INPUT_TYPES()["required"]
    assert all(f"LoRA{i}" in required and f"LoRA{i}强度" in required and f"LoRA{i}启用" in required for i in range(1, 9))
    assert required["LoRA1启用"][1]["default"] is True
    assert required["LoRA3启用"][1]["default"] is True
    assert required["LoRA4启用"][1]["default"] is False


def test_h3_model_filter_accepts_renamed_models_inside_h3_folder():
    assert MODULE._is_h3_video_model(r"H3\南风自合满血BF16多参模型.safetensors") is True
    assert MODULE._is_h3_video_model(r"other\南风自合满血BF16多参模型.safetensors") is False


def test_v10_enabled_lora_stack_keeps_visible_order_and_skips_disabled_slots():
    rows = MODULE._enabled_lora_stack({
        "启用LoRA": False,
        "LoRA1": "one.safetensors", "LoRA1强度": 0.8, "LoRA1启用": True,
        "LoRA2": "two.safetensors", "LoRA2强度": 0.6, "LoRA2启用": False,
        "LoRA3": "three.safetensors", "LoRA3强度": 0.4, "LoRA3启用": True,
    }, individual=True)
    assert rows == [("one.safetensors", 0.8), ("three.safetensors", 0.4)]


def test_v10_frontend_has_sequential_add_delete_without_master_toggle():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert "MAX_LORA_SLOTS = 8" in source
    assert "buildDynamicLoraPanel" in source
    assert "添加 LoRA" in source
    assert "删除" in source
    assert "LoRA${i}启用" in source
    assert '["启用LoRA","启用 LoRA","boolean"]' not in source


def test_v10_lora_rows_use_one_compact_horizontal_grid():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'row.append(enabled,title,modelControl,strengthControl,remove)' in source
    assert 'grid-template-columns:28px 58px minmax(0,1fr) 86px 48px' in source
    assert '.nfh3-lora-row-head' not in source
    assert '.nfh3-lora-row-fields' not in source


def test_v10_add_is_incremental_and_lora_model_uses_native_select():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const appendLoraRow=index=>' in source
    assert 'appendLoraRow(next);updateAddButton();' in source
    assert 'name.startsWith("LoRA")' in source
    assert 'type==="select"&&isV7(node)&&!name.startsWith("LoRA")' in source


def test_v10_lora_rows_can_delete_to_zero_and_new_rows_start_disabled():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'node.properties.nfh3_lora_slot_count=Math.max(0,count-1)' in source
    assert 'node.properties.nfh3_lora_slot_count=highest' in source
    assert 'setWidget(node,`LoRA${next}启用`,false)' in source
    assert 'Math.max(3,count-1)' not in source
    assert 'Math.max(3,highest)' not in source
    assert 'setWidget(node,`LoRA${next}启用`,true)' not in source


def test_v10_refresh_hook_reloads_model_defs_without_native_combo_dependency():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'async function refreshNanFengModelCombos' in source
    assert 'await api.fetchApi("/nanfeng/v10/h3/refresh-models"' in source
    assert 'document.addEventListener("keydown",async event=>' in source
    assert 'if(event.key.toLocaleLowerCase()!=="r"||event.ctrlKey||event.metaKey||event.altKey)return' in source
    assert 'await refreshNanFengModelCombos()' in source
    assert 'wrap.__nfh3SetValues=values=>' in source


def test_v10_model_choices_never_fall_back_to_fake_bundled_names():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'or list(DEFAULT_MODEL_OPTIONS)' not in source
    assert 'or [DEFAULT_TEXT_ENCODER]' not in source
    assert 'or [DEFAULT_VIDEO_VAE]' not in source
    assert 'or [DEFAULT_AUDIO_VAE]' not in source
    assert 'def _live_combo(values, preferred=None):' in source


def test_v10_custom_select_marks_empty_and_missing_live_models():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const LIVE_MODEL_WIDGETS=new Set(["模型","文本编码器","视频VAE","音频VAE","H3潜空间放大模型"])' in source
    assert '未检测到本机模型' in source
    assert '⚠ 未安装：${raw}' in source


def test_v10_package_has_no_machine_specific_runtime_skill_path():
    source = (ROOT / "storyboard_api.py").read_text(encoding="utf-8")
    assert 'C:/Users/' not in source
    assert 'NS_SKILL_PATH = Path(' not in source
    assert '"skill_path": PORTABLE_NS_SKILL_PATH' in source


def test_v10_latent_upscaler_uses_one_live_folder_everywhere():
    generator = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    refresh = (ROOT / "model_refresh_api.py").read_text(encoding="utf-8")
    assert 'choices = list(latent_models) or [preferred]' not in generator
    assert 'cls._live_combo(latent_models)' in generator
    assert 'get_filename_list("latent_upscale_models")' in refresh
    assert '"latent_upscale_models"' in refresh


def test_v10_runtime_model_selection_never_returns_uninstalled_literal():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'FL2VA_MODEL_NAME,' not in source
    assert 'kwargs.get("H3潜空间放大模型", "minimax_h3_latent_upscaler_3d_fp16.safetensors")' not in source


def test_v10_lora_restore_does_not_seed_or_restore_uninstalled_old_environment_names():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'H3/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors' not in source
    assert 'const liveLoras=choices(model)' in source
    assert 'liveLoras.includes(name)?name:(match||"未选择")' in source


def test_v10_each_lora_row_has_keyword_search_and_stale_backend_guard():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'function makeLoraSearchControl(node,index)' in source
    assert 'input.type="search"' in source
    assert 'placeholder="输入关键词搜索 LoRA…"' in source
    assert 'datalist.append(...values.map' in source
    assert '需重启 ComfyUI 加载此 LoRA 槽位' in source
    assert 'const modelControl=makeLoraSearchControl(node,index)' in source

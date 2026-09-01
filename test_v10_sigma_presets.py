from pathlib import Path

ROOT = Path(__file__).resolve().parent
JS = ROOT / "web" / "h3_multiref.js"


def test_v10_sigma_preset_has_nanfeng_10_step_default():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'const NANFENG_10_STEP_SIGMA="1, 0.988235, 0.972973, 0.952381, 0.923077, 0.878049, 0.8, 0.631579, 0.42, 0.18, 0"' in source
    assert '"南风10步":NANFENG_10_STEP_SIGMA' in source


def test_v10_sigma_preset_select_applies_to_native_sigma_widget():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'sigmaPresetSelect.onchange=()=>applySigmaPreset(sigmaPresetSelect.value)' in source
    assert 'setWidget(node,"H3完整Sigma序列",value)' in source
    assert 'completeSigmaInput.value=value' in source
    assert 'node.properties.nfh3_selected_sigma_preset=name' in source
    assert 'sync(node,root)' in source
    assert 'setWidget(node,"H3一采步数",6)' in source
    assert 'setWidget(node,"H3二采步数",4)' in source


def test_v10_sigma_presets_can_be_created_deleted_and_persisted():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'node.properties.nfh3_sigma_presets' in source
    assert 'sigmaPresetSave.textContent="保存"' in source
    assert 'const currentSigmaText=()=>String(completeSigmaInput?.value??widget(node,"H3完整Sigma序列")?.value??"").trim()' in source
    assert 'completeSigmaInput.oninput=()=>setWidget(node,"H3完整Sigma序列",completeSigmaInput.value)' in source
    assert 'customSigmaPresets[name]=value' in source
    assert 'sigmaPresetNew.textContent="新建"' in source
    assert 'window.prompt("新预设名称"' in source
    assert 'const requested=prompt("新预设名称"' not in source
    assert 'sigmaPresetDelete.textContent="删除"' in source
    assert 'delete customSigmaPresets[name]' in source
    assert 'node.graph?.change?.()' in source


def test_v10_sigma_presets_survive_restart_with_versioned_browser_fallback():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'const SIGMA_PRESET_STORAGE_KEY="nanfeng_h3_v10_sigma_presets_v1"' in source
    assert 'localStorage.setItem(SIGMA_PRESET_STORAGE_KEY' in source
    assert 'localStorage.getItem(SIGMA_PRESET_STORAGE_KEY)' in source
    assert '...storedSigmaPresets,...nodeSigmaPresets' in source
    assert 'selected_sigma_preset' in source


def test_sigma_preset_ui_is_v10_only_and_next_to_complete_sigma():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'if(isV9(node)&&completeSigmaControl)' in source
    assert 'completeSigmaControl.append(sigmaPresetManager)' in source

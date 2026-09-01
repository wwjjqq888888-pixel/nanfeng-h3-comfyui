from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "ns-storyboard-skill" / "SKILL.md"
SPEC = importlib.util.spec_from_file_location("nanfeng_v10_ref_opening", ROOT / "storyboard_api.py")
API = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(API)


def test_ns_ref2va_references_are_not_first_frame_anchors():
    text = SKILL.read_text(encoding="utf-8")
    assert "多参素材不是首帧" in text
    assert "Ref2VA不锁定任何Picture为0.00秒首帧" in text
    assert "不得先完整展示参考素材画面" in text
    assert "不得从参考图原始构图、原始姿势或单人素材画面起步" in text
    assert "每一段`00:00.000`直接呈现目标剧情画面" in text


def test_ref2va_runtime_contract_forbids_material_flash_without_locking_first_frame():
    contract = API.mode_contract("ref2va", 3)
    assert "Ref2VA多参素材只提供身份、外观、场景、道具、风格或动作参考" in contract
    assert "不锁定任何Picture为0.00秒首帧" in contract
    assert "不得在段首先闪现或完整展示任一参考素材的原始画面" in contract
    assert "00:00直接生成该段目标剧情构图" in contract


def test_i2va_and_fl2va_still_keep_true_frame_alignment():
    assert "0.00秒" in API.mode_contract("i2va", 1)
    fl = API.mode_contract("fl2va", 1)
    assert "Picture 1对齐0.00秒" in fl
    assert "Picture 2对齐该段结束时刻" in fl

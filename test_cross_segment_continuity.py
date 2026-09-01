import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nanfeng_v10_storyboard_continuity", ROOT / "storyboard_api.py")
API = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(API)


def test_runtime_contract_requires_joint_cross_segment_cut_design():
    text = API.mode_contract("ref2va", 3)
    assert "相邻两段必须作为一个整体联合设计" in text
    assert "不得使用相同景别且相同机位角度" in text
    assert "正反打" in text
    assert "站位关系" in text
    assert "动作轴" in text


def test_all_v10_skills_have_boundary_pair_and_spatial_ledger_rules():
    for relative in ("storyboard-skill/SKILL.md", "ns-storyboard-skill/SKILL.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "Boundary Pair Design" in text
        assert "same shot size and the same camera angle" in text
        assert "reverse shot" in text
        assert "screen-left" in text and "foreground" in text


def test_frontend_persists_selected_smart_storyboard_skill():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert "NANFENG_SMART_SKILL_STORAGE_KEY" in source
    assert "nanfeng_smart_storyboard_skill_id" in source
    assert "loadPersistedSmartSkill" in source
    assert "savePersistedSmartSkill" in source

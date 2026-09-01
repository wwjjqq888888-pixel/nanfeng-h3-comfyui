from pathlib import Path

SKILL = Path(__file__).parent / "ns-storyboard-skill" / "SKILL.md"


def test_ns_distinguishes_deliberate_cut_from_material_flash():
    text = SKILL.read_text(encoding="utf-8")
    assert "硬切不是闪素材" in text
    assert "允许在段内或跨段边界直接硬切" in text
    assert "闪素材是参考图原始画面或错误默认画面短暂出现" in text
    assert "不能把正常切镜误判为闪烁" in text


def test_ns_allows_variable_shot_count_per_segment():
    text = SKILL.read_text(encoding="utf-8")
    assert "每段可以一镜到底，也可以包含2镜、3镜或更多必要镜头" in text
    assert "镜头数量不要求各段一致" in text
    assert "所有镜头的时间戳必须落在该段时长内" in text


def test_ns_cross_segment_cut_requires_relation_not_same_view():
    text = SKILL.read_text(encoding="utf-8")
    assert "联系不等于同景别、同角度或像素连续" in text
    assert "硬切后的第一幅目标画面必须在叙事、动作、空间或反应关系上承接前段" in text
    assert "可以直接换景别、换角度、正反打或切反应镜头" in text

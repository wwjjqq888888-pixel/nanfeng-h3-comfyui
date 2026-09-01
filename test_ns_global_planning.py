from pathlib import Path

SKILL = Path(__file__).parent / "ns-storyboard-skill" / "SKILL.md"


def test_ns_skill_requires_evidence_first_global_timeline_planning():
    text = SKILL.read_text(encoding="utf-8")
    assert "先收齐资料，再规划，再输出" in text
    assert "总叙事时长 = 段数 × 每段时长" in text
    assert "不得读取一部分资料就开始写段1" in text
    assert "不得按图片顺序分段" in text
    assert "不得把一张图片机械对应一段" in text
    assert "先形成一条完整的全局事件时间线" in text
    assert "最后才逐段写正式提示词" in text


def test_ns_skill_keeps_ref2va_images_semantic_only():
    text = SKILL.read_text(encoding="utf-8")
    assert "Ref2VA不锁定任何Picture为0.00秒首帧" in text
    assert "多参图片不能充当任何一段的首帧素材" in text
    assert "不得把参考图原始画面作为段首建立镜头" in text
    assert "每段`00:00.000`直接生成该段在全局时间线中的目标剧情构图" in text


def test_ns_global_plan_accounts_for_all_inputs_and_boundaries():
    text = SKILL.read_text(encoding="utf-8")
    assert "用户完整自然语言" in text
    assert "全部逐图分析结果" in text
    assert "人物身份合并" in text
    assert "全部跨段边界镜头对" in text
    assert "内部全局规划不输出" in text

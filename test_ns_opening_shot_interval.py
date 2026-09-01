from pathlib import Path

SKILL = Path(__file__).parent / "ns-storyboard-skill" / "SKILL.md"


def test_ns_opening_continuity_uses_the_actual_first_shot_interval():
    text = SKILL.read_text(encoding="utf-8")
    assert "段首约束必须覆盖首镜完整时间区间" in text
    assert "首镜区间从00:00.000开始，到下一镜时间戳为止" in text
    assert "如果该段一镜到底，则覆盖到该段结束" in text
    assert "不得固定写成0至3秒、前0.5秒或任何统一秒数" in text


def test_ns_first_shot_interval_contains_continuous_observable_action():
    text = SKILL.read_text(encoding="utf-8")
    assert "不能只在00:00.000声明一个静态继承状态" in text
    assert "整个首镜区间都必须写明可持续、可观察的承接动作" in text
    assert "首镜结束状态必须成为下一镜的动作起点" in text


def test_ns_opening_interval_is_derived_after_shot_timestamps_are_planned():
    text = SKILL.read_text(encoding="utf-8")
    assert "先按该段内容规划镜头数和全部时间戳" in text
    assert "再由下一镜时间戳反推首镜持续时间" in text
    assert "2镜、3镜或一镜到底分别得到不同的首镜区间" in text

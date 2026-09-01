from pathlib import Path

SKILL = Path(__file__).parent / "ns-storyboard-skill" / "SKILL.md"


def test_each_timestamp_defines_an_executable_interval():
    text = SKILL.read_text(encoding="utf-8")
    assert "每个[Shot N]时间戳定义的是该镜头的开始" in text
    assert "该镜头持续到下一条[Shot N+1]时间戳" in text
    assert "最后一镜持续到该段结束时刻" in text
    assert "必须为每个镜头区间分配足够且可执行的内容" in text


def test_no_static_handoff_filler_or_instantaneous_action_for_long_interval():
    text = SKILL.read_text(encoding="utf-8")
    assert "不得用remains、stays或同义静态句占满一个本应推进剧情的首镜区间" in text
    assert "不能用一个瞬时动作填满数秒区间" in text
    assert "承接状态必须与该区间内的新动作写在同一个镜头中" in text


def test_duration_budget_covers_dialogue_and_concurrent_action():
    text = SKILL.read_text(encoding="utf-8")
    assert "对白必须完整落在其所属镜头区间内" in text
    assert "对白期间同步发生的动作必须标明同时进行" in text
    assert "动作过多时移动下一镜时间戳或减少次要动作" in text


def test_retention_shot_membership_matches_detailed_description():
    text = SKILL.read_text(encoding="utf-8")
    assert "retention_analysis中的appears in必须与detailed_description逐镜一致" in text
    assert "任何在某镜出现、说话、被看见或执行动作的Subject都必须列入该镜" in text

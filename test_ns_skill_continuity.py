from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
SKILL_PATH = ROOT / "ns-storyboard-skill" / "SKILL.md"
SPEC = importlib.util.spec_from_file_location("nanfeng_v10_ns_continuity", ROOT / "storyboard_api.py")
API = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(API)


def test_ns_skill_has_subject_instance_contract_without_changing_ns_content_rules():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "主体实例合同" in text
    assert "同一人物的多张参考图" in text
    assert "每个真人角色在同一镜头只能出现一个物理实例" in text
    assert "近景、局部特写、正反打和切镜不得复制" in text
    assert "所有可见的脸、头、躯干、手脚和身体部位" in text
    assert "# 九、NSFW逻辑" in text
    assert "不自行降级" in text


def test_ns_skill_forbids_segment_start_flash_and_reestablishment():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert "跨段起始防闪烁" in text
    assert "下一段整个首镜完整时间区间" in text
    assert "该区间长度由下一镜时间戳动态决定，不使用固定秒数" in text
    assert "不得先闪出默认构图" in text
    assert "不得重新建立站位" in text
    assert "下一段第一帧直接生成承接上一段尾镜的目标剧情构图" in text
    assert "这不是把上一段像素尾帧锁成Picture首帧" in text
    assert "跨段边界可以从`00:00.000`直接硬切到新的景别或角度" in text
    assert "完整时间区间持续承接相同世界状态和动作阶段" in text


def test_v10_runtime_contract_repeats_no_flash_boundary_requirement():
    contract = API.mode_contract("ref2va", 3)
    assert "下一段第一帧就必须落在上一段尾镜的状态" in contract
    assert "不得先闪出默认构图" in contract
    assert "不得重新建立人物站位" in contract
    assert "换景别或换角度只能发生在状态继承成立之后" in contract

from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("nanfeng_v10_audio_lock", ROOT / "h3_generator.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_v10_schema_appends_audio_lock_toggle_only_to_v10():
    v9 = MODULE.NanFengH3MultiReferenceGeneratorV9.INPUT_TYPES()["required"]
    v10 = MODULE.NanFengH3MultiReferenceGeneratorV10.INPUT_TYPES()["required"]
    assert "启用锁音频" not in v9
    assert "启用锁音频" in v10
    assert v10["启用锁音频"][1]["default"] is False
    assert list(v10).index("启用锁音频") == len(v10) - 11
    assert list(v10)[-10:] == ["开启音频驱动模式", "音频驱动文件", "音频驱动打点", "音频驱动分段图片", "音频驱动分段分镜", "音频驱动创意", "音频驱动排除范围", "音频驱动当前起点", "音频驱动当前终点", "恒定触发词"]


def test_v10_frontend_places_audio_lock_as_right_column_fold():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'audioLockDetails.innerHTML="<summary>数字人·MV·锁音频</summary>"' in source
    assert '["启用锁音频","开启锁音频","boolean"]' in source
    assert 'optionalTopLevel=[audioLockDetails,' in source


def test_generator_routes_model_and_latent_through_native_audio_lock_only_when_enabled():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert '"MiniMaxH3NativeAudioLock", model=sampling_model_input' in source
    assert 'bool(kwargs.get("启用锁音频", False))' in source
    assert 'lock_audio_name = audio_drive_filename if audio_drive_enabled else audio_names[0]' in source
    assert 'lock_audio_source = g.node("LoadAudio", audio=lock_audio_name)' in source
    assert '"TrimAudioDuration", audio=lock_audio_source.out(0)' in source
    assert 'sampling_model_input = audio_lock.out(0)' in source
    assert 'sampling_latent_input = audio_lock.out(1)' in source


def test_enabled_audio_lock_returns_exact_source_audio_instead_of_vae_decode():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'exact_audio_output = audio_lock.out(2)' in source
    assert 'final_audio = exact_audio_output if exact_audio_output is not None else audio_decode.out(0)' in source
    assert '"result": (final_images, final_audio)' in source


def test_audio_drive_and_audio_lock_are_composable_and_use_segment_audio_range():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'if audio_drive_enabled and not audio_lock_enabled:' in source
    assert 'audio_drive_filename = _clean_filename(kwargs.get("音频驱动文件"))' in source
    assert 'lock_audio_name = audio_drive_filename if audio_drive_enabled else audio_names[0]' in source
    assert 'lock_audio_start = float(kwargs.get("音频驱动当前起点", 0.0)) if audio_drive_enabled else 0.0' in source
    assert 'start_index=lock_audio_start, duration=float(时长秒)' in source
    assert '音频驱动模式与原“开启锁音频”参考链路互斥' not in source


def test_audio_drive_storyboard_switch_publishes_segment_start_for_backend_lock_trim():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'setWidget(node,"音频驱动当前起点",Number(shot.audioDriveStart)||0)' in source
    assert 'setWidget(node,"音频驱动当前终点",Number(shot.audioDriveEnd)||0)' in source

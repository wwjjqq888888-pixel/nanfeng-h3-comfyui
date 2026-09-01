from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_v10_audio_lock_fold_uses_new_digital_human_mv_title():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'audioLockDetails.innerHTML="<summary>数字人·MV·锁音频</summary>"' in source
    assert 'audioLockDetails.innerHTML="<summary>锁音频</summary>"' not in source


def test_v10_audio_lock_explanation_returns_to_a_short_note():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'audioLockNote=document.createElement("div")' in source
    assert 'audioLockNote.className="nfh3-note"' in source
    assert 'audioLockGrid.append(audioLockNote)' in source
    assert 'audioLockAction=document.createElement("button")' not in source

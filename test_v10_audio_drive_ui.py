from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_v10_schema_appends_audio_drive_toggle_after_audio_lock():
    import importlib.util
    spec = importlib.util.spec_from_file_location("nanfeng_v10_audio_drive", ROOT / "h3_generator.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    required = module.NanFengH3MultiReferenceGeneratorV10.INPUT_TYPES()["required"]
    assert required["开启音频驱动模式"][1]["default"] is False
    keys = list(required)
    assert keys[-11:] == ["启用锁音频", "开启音频驱动模式", "音频驱动文件", "音频驱动打点", "音频驱动分段图片", "音频驱动分段分镜", "音频驱动创意", "音频驱动排除范围", "音频驱动当前起点", "音频驱动当前终点", "恒定触发词"]
    assert required["音频驱动分段图片"][1]["default"] == "{}"
    assert required["音频驱动分段分镜"][1]["default"] == "{}"
    assert required["音频驱动创意"][1]["default"] == ""
    assert required["音频驱动排除范围"][1]["default"] == "{}"


def test_audio_drive_button_is_short_black_until_enabled_then_yellow():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '["开启音频驱动模式","开启音频驱动模式","boolean"]' in source
    assert 'audioDriveAction.textContent="智能音频驱动"' in source
    assert 'audioDriveAction.disabled=!audioDriveEnabled' in source
    assert 'audioDriveAction.classList.toggle("enabled",audioDriveEnabled)' in source
    assert '.nfh3-audio-drive-action{' in source
    assert '.nfh3-audio-drive-action.enabled{' in source
    assert 'background:#0b0b08!important' in source
    assert 'background:#f4d20b!important' in source
    assert 'min-height:38px' in source


def test_audio_drive_opens_a_separate_overlay_ui_like_smart_storyboard():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'function openAudioDriveUI(node)' in source
    assert 'audioDriveAction.onclick=()=>openAudioDriveUI(node)' in source
    assert 'className="nfh3-audio-drive-modal"' in source
    assert 'className="nfh3-audio-drive-dialog"' in source
    assert 'audioDriveUpload.accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a,.aac"' in source
    assert 'audioDriveCanvas=document.createElement("canvas")' in source
    assert 'audioDriveAddMarker.textContent="添加打点"' in source
    assert 'audioDriveRemoveMarker.textContent="删除选中"' in source
    assert '`/nfypnode/audio-waveform?audio_file=${encodeURIComponent(audioFile)}&bins=1400`' in source
    assert 'setWidget(node,"音频驱动文件",audioFile)' in source
    assert 'setWidget(node,"音频驱动打点",JSON.stringify' in source
    assert 'const snapAudioDriveTime=value=>Math.round' in source
    assert 'snapAudioDriveTime(audioDriveAudio.currentTime||0)' in source
    assert 'className="nfh3-audio-drive-segments"' in source
    assert 'className="nfh3-audio-drive-image-row"' in source
    assert '图片${index+1}' in source
    assert 'Math.min(9' in source
    assert 'Math.max(4' in source
    assert 'setWidget(node,"音频驱动分段图片",JSON.stringify' in source
    assert 'mediaUrl(file' in source
    assert '智能音频驱动' in source
    assert '返回主界面' in source
    assert 'modal.onclick=e=>' not in source
    assert 'back.onclick=()=>{saveExcludedRanges();closeAudioDriveModal();}' in source


def test_audio_drive_segment_cards_are_square_and_flow_horizontally():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '.nfh3-audio-drive-dialog{width:min(1440px,96vw);height:min(920px,95vh)' in source
    assert '.nfh3-audio-drive-segments{display:flex;flex-direction:row' in source
    assert 'overflow-x:scroll' in source
    assert 'overscroll-behavior-x:contain' in source
    assert '.nfh3-audio-drive-segment{flex:0 0 220px;width:220px;min-width:220px;max-width:220px;height:300px' in source
    assert '.nfh3-audio-drive-image-row{display:grid;grid-template-columns:38px 78px 40px' in source


def test_audio_drive_horizontal_stage_and_footer_are_fixed_not_stretched():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '.nfh3-audio-drive-body{display:grid;grid-template-rows:auto 160px 44px 132px minmax(0,1fr)' in source
    assert '.nfh3-audio-drive-segments{display:flex;flex-direction:row;flex-wrap:nowrap' in source
    assert 'overflow-x:scroll' in source
    assert '.nfh3-audio-drive-segments::-webkit-scrollbar{height:14px' in source
    assert '.nfh3-audio-drive-segment{flex:0 0 220px;width:220px;min-width:220px;max-width:220px;height:300px' in source
    assert '.nfh3-audio-drive-footer{display:flex;align-items:center;justify-content:flex-end' in source
    assert '.nfh3-audio-drive-footer>button{flex:0 0 220px;width:220px;min-width:220px;max-width:220px' in source


def test_audio_drive_waveform_canvas_keeps_fixed_css_geometry_without_bitmap_stretching():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '.nfh3-audio-drive-waveform{display:block;width:100%;height:160px;min-height:160px;max-height:160px' in source
    assert 'const resizeAudioDriveCanvas=()=>{' in source
    assert 'window.devicePixelRatio||1' in source
    assert 'const nextWidth=Math.round(rect.width*dpr),nextHeight=Math.round(rect.height*dpr)' in source
    assert 'ctx.setTransform(dpr,0,0,dpr,0,0)' in source
    assert 'new ResizeObserver(resizeAudioDriveCanvas)' in source


def test_audio_drive_uses_a_dedicated_api_config_not_storyboard_credentials():
    frontend = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    backend = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    package = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert 'audioDriveApiButton.textContent="API配置"' in frontend
    assert 'className="nfh3-audio-drive-api-panel"' in frontend
    assert '/nanfeng/v10/h3/audio-drive/config' in frontend
    assert '/nanfeng/v10/h3/audio-drive/models' in frontend
    assert '/nanfeng/v10/h3/storyboard/config' not in frontend[frontend.index('function openAudioDriveUI(node)'):frontend.index('function addStyle()')]
    assert 'AUDIO_DRIVE_ENV_PATH = ROOT / ".audio-drive.env"' in backend
    assert 'NANFENG_AUDIO_DRIVE_VISION_API_KEY' in backend
    assert 'NANFENG_AUDIO_DRIVE_TEXT_API_KEY' in backend
    assert '@routes.get("/nanfeng/v10/h3/audio-drive/config")' in backend
    assert '@routes.post("/nanfeng/v10/h3/audio-drive/models")' in backend
    assert 'audio_drive_api as _audio_drive_api' in package


def test_audio_drive_has_an_independent_copy_of_regular_storyboard_skill():
    regular = ROOT / "storyboard-skill"
    audio_drive = ROOT / "audio-drive-skill"
    assert (audio_drive / "SKILL.md").read_bytes() == (regular / "SKILL.md").read_bytes()
    assert (audio_drive / "references" / "base-en.txt").read_bytes() == (regular / "references" / "base-en.txt").read_bytes()
    assert (audio_drive / "references" / "ref-en.txt").read_bytes() == (regular / "references" / "ref-en.txt").read_bytes()
    backend = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert 'AUDIO_DRIVE_SKILL_DIR = ROOT / "audio-drive-skill"' in backend
    assert 'AUDIO_DRIVE_SKILL_PATH = AUDIO_DRIVE_SKILL_DIR / "SKILL.md"' in backend


def test_audio_drive_has_global_natural_language_idea_and_compact_square_image_slots():
    frontend = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    backend = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert '音频驱动创意' in backend
    assert 'className="nfh3-audio-drive-idea"' in frontend
    assert '直接描述整支视频怎么拍' in frontend
    assert 'setWidget(node,"音频驱动创意",audioDriveIdea.value)' in frontend
    assert '.nfh3-audio-drive-image-preview{display:grid;place-items:center;width:78px;height:78px' in frontend
    assert '.nfh3-audio-drive-segment{flex:0 0 220px;width:220px;min-width:220px;max-width:220px;height:300px' in frontend


def test_audio_drive_segment_images_support_smart_storyboard_style_reordering():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const moveSegmentImage=(key,from,to)=>{' in source
    assert 'row.draggable=!!file' in source
    assert 'row.ondragstart=' in source
    assert 'row.ondrop=' in source
    assert 'moveSegmentImage(key,segmentImageDrag.index,index)' in source
    assert 'audioDriveImageMove.textContent="↔"' in source


def test_audio_drive_backend_deduplicates_vision_and_keeps_segment_slot_mapping():
    backend = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert 'def build_reference_manifest(segments: list[dict])' in backend
    assert 'unique_images.setdefault(filename' in backend
    assert 'segment_index' in backend and 'slot_index' in backend
    assert 'duration_seconds' in backend
    assert '每张唯一图片只看一次' in backend
    assert '@routes.post("/nanfeng/v10/h3/audio-drive/generate")' in backend
    assert 'AUDIO_DRIVE_SKILL_PATH.read_text' in backend


def test_audio_drive_fold_has_distinct_transparent_to_yellow_summary():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'audioLockDetails.className="nfh3-advanced nfh3-primary-fold nfh3-audio-drive-fold"' in source
    assert '.nfh3-v9-horizontal .nfh3-audio-drive-fold>summary{' in source
    assert 'linear-gradient(90deg,rgba(5,5,3,.08)' in source
    assert '#f4d20b 100%' in source


def test_audio_drive_uses_one_global_natural_language_idea_without_per_segment_prompt_editors():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'generateAllStoryboards.textContent="生成智能分镜"' in source
    assert 'backBar.append(audioDriveEnableBar,generateAllStoryboards,back)' in source
    assert 'segmentSeconds=Math.max(1,Math.ceil(range.end-range.start))' in source
    assert 'className="nfh3-audio-drive-idea"' in source
    assert 'JSON.stringify({idea:audioDriveIdea.value,segments})' in source
    assert 'storyboardDuration.value=segmentSeconds' not in source
    assert 'className="nfh3-audio-drive-storyboard"' not in source
    assert '本段分镜（${segmentSeconds}秒）' not in source


def test_audio_drive_api_config_uses_full_body_view_with_vertical_scroll():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert "body.classList.toggle('api-open',opening)" in source
    assert '.nfh3-audio-drive-body.api-open{display:block;overflow-y:auto}' in source
    assert '.nfh3-audio-drive-body.api-open>.nfh3-audio-drive-toolbar' in source


def test_audio_drive_can_exclude_intro_and_outro_ranges_from_rendered_segments():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'audioDriveExcludeIntro.type="checkbox"' in source
    assert 'audioDriveExcludeOutro.type="checkbox"' in source
    assert 'audioDriveExcludeIntroLabel.append(audioDriveExcludeIntro,document.createTextNode("排除首段"))' in source
    assert 'audioDriveExcludeOutroLabel.append(audioDriveExcludeOutro,document.createTextNode("排除尾段"))' in source
    assert 'audioDriveExcludeIntro.checked=excludedRanges.intro' in source
    assert 'audioDriveExcludeOutro.checked=excludedRanges.outro' in source
    assert 'const segmentRanges=()=>{const bounds=segmentBounds()' in source
    assert 'audioDriveExcludeIntro.onchange=' in source
    assert 'const segmentKey=range=>`${Number(range.start).toFixed(3)}-${Number(range.end).toFixed(3)}`' in source
    assert 'setWidget(node,"音频驱动排除范围",JSON.stringify(excludedRanges))' in source
    assert 'const ranges=segmentRanges();audioDriveStatus.title=' in source
    assert 'audioDriveSegments.replaceChildren()' in source
    assert 'for(const [segmentIndex,range] of ranges.entries())' in source
    assert 'const enabledRanges=segmentRanges().filter(range=>!disabledSegmentKeys.has(segmentKey(range)))' in source
    assert 'segment_index:range.source_index+1,source_segment_index:range.source_index+1,start:range.start,end:range.end' in source


def test_audio_drive_generated_results_fill_outer_storyboard_slots_with_per_segment_duration():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'node.__nfh3ImportAudioDriveStoryboards=generated=>' in source
    assert 'durationSeconds:integerDuration' in source
    assert '图片:Array.isArray(item.images)?item.images.filter(Boolean).slice(0,LIMITS.图片):[]' in source
    assert 'audioDriveStart:Number(item.start)' in source
    assert 'audioDriveEnd:Number(item.end)' in source
    assert 'setWidget(node,"时长秒",Number(shot.durationSeconds' in source
    assert 'sync(node,root);node.__nfh3SyncBasicDuration?.(Number(shot.durationSeconds));persistStoryboards();render();' in source
    assert 'const audioDriveShot=shot.audioDriveEnabled===true&&Number.isFinite(Number(shot.audioDriveStart))&&Number.isFinite(Number(shot.audioDriveEnd))' in source
    assert 'b.innerHTML=audioDriveShot?`<span class="nfh3-storyboard-time-icon"' in source
    assert 'b.title=audioDriveShot?`音频驱动分镜' in source
    assert '.nfh3-storyboard-time-icon{' in source
    assert 'const imported=node.__nfh3ImportAudioDriveStoryboards?.(data.segments||[])' in source
    assert 'closeAudioDriveModal();node.__nfh3Render?.();' in source
    assert '已写入外部节点分镜槽位' in source


def test_audio_drive_exclusion_checks_survive_modal_close_and_reopen():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'node.properties.nfh3_audio_drive_exclusions' in source
    assert 'const saved=node.properties?.nfh3_audio_drive_exclusions' in source
    assert 'node.properties.nfh3_audio_drive_exclusions={...excludedRanges}' in source
    assert 'back.onclick=()=>{saveExcludedRanges();closeAudioDriveModal();}' in source


def test_audio_drive_waveform_is_compact_and_global_idea_is_large_and_prominent():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'grid-template-rows:auto 160px 44px 132px minmax(0,1fr)' in source
    assert 'height:160px;min-height:160px;max-height:160px;flex:0 0 160px' in source
    assert 'className="nfh3-audio-drive-idea-panel"' in source
    assert '整支视频自然语言创意' in source
    assert '上游大模型会结合每段秒数和图片顺序，自动拆分为各段分镜' in source
    assert '.nfh3-audio-drive-idea-panel{height:132px' in source
    assert '.nfh3-audio-drive-idea{display:block;width:100%;height:96px' in source


def test_audio_drive_segment_wheel_prefers_internal_vertical_scroll_and_compact_controls():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const card=event.target.closest?.(".nfh3-audio-drive-segment")' in source
    assert 'canScrollDown=card.scrollTop+card.clientHeight<card.scrollHeight-1' in source
    assert 'if((event.deltaY<0&&canScrollUp)||(event.deltaY>0&&canScrollDown))return' in source
    assert 'className="nfh3-audio-drive-image-media"' in source
    assert 'mediaWrap.append(preview,audioDriveImageMove)' in source
    assert 'row.append(label,mediaWrap,remove,picker)' in source
    assert 'flex:0 0 220px;width:220px;min-width:220px;max-width:220px' in source
    assert 'grid-template-columns:38px 78px 40px' in source


def test_audio_drive_mode_hides_regular_reference_area_in_frontend():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const audioDriveEnabled=!!widget(node,"开启音频驱动模式")?.value' in source
    assert 'const regularMedia=node.__nfh3MediaSection' in source
    assert 'regularMedia.hidden=audioDriveEnabled' in source


def test_audio_drive_workspace_is_node_owned_and_all_mutations_dirty_the_workflow():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const persistAudioDriveWorkspace=node=>{' in source
    assert 'node.properties.nfh3_audio_drive_workspace={' in source
    for field in ('音频驱动文件', '音频驱动打点', '音频驱动分段图片', '音频驱动分段分镜', '音频驱动创意', '音频驱动排除范围'):
        assert f'"{field}":' in source
    assert 'const restoreAudioDriveWorkspace=node=>{' in source
    assert 'restoreAudioDriveWorkspace(this)' in source
    assert 'AUDIO_DRIVE_BACKUP_STORAGE_KEY' in source
    assert 'const snapshotAudioDriveWorkspace=node=>({' in source
    assert 'const recoverAudioDriveWorkspaceFromStoryboards=node=>{' in source
    assert 'shot.audioDriveEnabled===true' in source
    assert 'shot.audioDriveFilename===audioFile' in source
    assert 'recoveredMarkers' in source
    assert 'restoreBestAudioDriveWorkspace(this)' in source
    assert 'recoverAudioDriveWorkspaceFromStoryboards(this)' not in source
    assert 'restoreBestAudioDriveWorkspace(this);syncSeedControlMode(this)' in source
    assert 'scoreAudioDriveWorkspace' in source
    assert 'nfh3_audio_drive_workspace_history' in source
    assert 'if(current&&typeof current==="object")return false' in source
    assert 'const initializeAudioDriveMarkersFromTimedStoryboards=node=>{' in source
    assert 'shot?.audioDriveEnabled===true' in source
    assert 'node.properties.nfh3_audio_drive_marker_authority="internal-v2"' in source
    assert 'initializeAudioDriveMarkersFromTimedStoryboards(this)' in source
    assert 'shots.slice(0,-1).map(shot=>Number(shot.audioDriveEnd))' in source
    assert 'Number(shot.audioDriveEnd)>Number(shot.audioDriveStart)' in source
    assert 'persistAudioDriveWorkspace(node)' in source
    assert 'localStorage' in source[source.index('const persistAudioDriveWorkspace=node=>{'):source.index('function loadPersistedSmartSkill')]


def test_audio_drive_original_segment_cards_remain_visible_with_card_level_enable_controls():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const segmentRanges=()=>{const bounds=segmentBounds()' in source
    assert 'const ranges=segmentRanges();audioDriveStatus.title=' in source
    assert 'audioDriveSegments.replaceChildren()' in source
    assert 'const disabledSegmentKeys=' in source
    assert 'nfh3_audio_drive_disabled_segments' in source
    assert 'const disabledSegmentKeys=new Set' in source
    assert 'enable.checked=!disabledSegmentKeys.has(key)' in source
    assert 'const enabledRanges=segmentRanges().filter(range=>!disabledSegmentKeys.has(segmentKey(range)))' in source
    assert 'node.__nfh3SplitAudioDriveTimeline' not in source
    assert 'node.__nfh3MergeAudioDriveTimeline' not in source
    assert 'const segmentRanges=()=>{const bounds=segmentBounds()' in source
    assert 'audioDriveAddMarker.onclick=()=>{if(!(duration>0))return;const time=' in source
    assert 'markers.push(time)' in source
    assert 'saveMarkers();render();renderSegments()' in source
    assert 'audioDriveRemoveMarker.onclick=()=>{if(selectedMarker<0||selectedMarker>=markers.length)return' in source
    assert 'markers.splice(selectedMarker,1)' in source
    assert 'node.__nfh3ImportAudioDriveStoryboards?.(data.segments||[])' in source
    assert 'shots.push(...imported)' in source
    assert 'const markerHitRadiusPx=8' in source
    assert 'hitIndex=markers.reduce' in source
    assert 'Math.abs(markerX-clickX)<=markerHitRadiusPx?hitIndex:-1' in source
    assert 'selectedMarker=-1' in source
    assert '主节点分镜未改变' in source
    assert 'restoreBestAudioDriveWorkspace(this);syncSeedControlMode(this)' in source
    assert 'restoreBestAudioDriveWorkspace(this);recoverAudioDriveWorkspaceFromStoryboards(this)' not in source
    assert 'const audioDriveWorkspaceValue=(node,name,fallback)=>' in source
    assert 'enableLabel.append(enable,document.createTextNode("启用"))' in source
    assert 'audioDriveEnableAll.textContent="全选"' in source
    assert 'audioDriveEnableNone.textContent="全不选"' in source
    assert 'segment.classList.toggle("current",' in source
    assert 'const enabledRanges=segmentRanges().filter(range=>!disabledSegmentKeys.has(segmentKey(range)))' in source
    assert 'source_segment_index:range.source_index+1' in source
    assert 'segment_index:range.source_index+1' in source
    assert 'const resultByOriginalIndex=new Map' in source
    assert 'resultByOriginalIndex.get(range.source_index+1)' in source
    api = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert '本次共选择{len(expected)}段' in api
    assert '保留原始段号' in api
    assert 'const closeAudioDriveModal=()=>{audioDriveAudio.pause();audioDriveAudio.ontimeupdate=null;audioDriveAudio.onloadedmetadata=null;audioDriveResizeObserver?.disconnect();modal.remove();}' in source
    assert 'audioDriveFramePending=false' in source
    assert 'if(audioDriveFramePending)return;audioDriveFramePending=true;requestAnimationFrame(()=>{audioDriveFramePending=false;render()' in source
    assert 'back.onclick=()=>{saveExcludedRanges();closeAudioDriveModal();}' in source


def test_audio_drive_manifest_rejects_segments_outside_h3_duration_range():
    source = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert 'if duration_seconds < 1.0 or duration_seconds > 15.0:' in source
    assert 'duration_seconds = float(max(1, math.ceil(duration_seconds)))' in source


def test_audio_drive_last_fractional_segment_ceil_rounds_and_pads_silence():
    frontend = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    backend = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    api = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert 'segmentSeconds=Math.max(1,Math.ceil(range.end-range.start))' in frontend
    assert 'const integerDuration=Math.max(1,Math.ceil(Number(item.end)-Number(item.start)))' in frontend
    assert 'duration_seconds = float(max(1, math.ceil(duration_seconds)))' in api
    assert '"NanFengAudioPadToDuration", audio=lock_audio_trimmed.out(0), duration=float(时长秒)' in backend
    assert 'expected_duration = max(1, math.ceil(audio_drive_end - lock_audio_start))' in backend


def test_audio_drive_segments_use_integer_duration_for_model_widget_and_trim():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const integerDuration=Math.max(1,Math.ceil(Number(item.end)-Number(item.start)))' in source
    assert 'durationSeconds:integerDuration' in source
    assert 'toFixed(3)' not in source[source.index('node.__nfh3ImportAudioDriveStoryboards=generated=>'):source.index('const storyboardTabs=', source.index('node.__nfh3ImportAudioDriveStoryboards=generated=>'))]


def test_audio_drive_audio_itself_satisfies_reference_input_requirement():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'effective_audio_names = [audio_drive_filename] if audio_drive_enabled else audio_names' in source
    assert 'not any(image_names + video_names + effective_audio_names)' in source


def test_audio_drive_import_and_switch_force_exact_basic_duration_and_trim_state():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const integerDuration=Math.max(1,Math.ceil(Number(item.end)-Number(item.start)))' in source
    assert 'durationSeconds:integerDuration' in source
    assert 'audioDriveEnabled:true' in source
    assert 'audioLockEnabled:true' in source
    assert 'setWidget(node,"时长秒",Number(shot.durationSeconds))' in source
    assert 'setWidget(node,"音频驱动文件",String(shot.audioDriveFilename||""))' in source
    assert 'setWidget(node,"音频驱动当前起点",Number(shot.audioDriveStart)||0)' in source
    assert 'setWidget(node,"音频驱动当前终点",Number(shot.audioDriveEnd)||0)' in source
    assert 'node.__nfh3SyncBasicDuration?.(Number(shot.durationSeconds))' in source


def test_storyboards_use_current_workflow_properties_as_authority_and_deleted_shots_stay_deleted():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const storyboardStorageKey=node=>`${STORYBOARD_STORAGE_KEY}:${workflowStorageScope(node)}:${node.id}`' in source
    assert 'const persistedStoryboards=nodeShots?null:loadPersistedStoryboards(node)' in source
    assert 'node.__nfh3RestoreStoryboardsFromProperties=()=>{' in source
    assert 'const candidate=configured||backup?.shots' in source
    assert 'configured.length>=backup.shots.length' not in source
    assert 'legacyRecovery=nodeShots?.length===1' not in source
    assert 'this.__nfh3RestoreStoryboardsFromProperties?.()' in source
    assert 'node.graph?.change?.()' in source
    assert 'loadPersistedStoryboards(node)' in source
    assert 'savePersistedStoryboards(node,shots,activeShot)' in source
    assert 'audioDriveEnabled:true' in source
    assert 'const audioDriveFilename=String(widget(node,"音频驱动文件")?.value||"")' in source
    assert 'setWidget(node,"开启音频驱动模式",!!shot.audioDriveEnabled)' in source
    assert 'setWidget(node,"启用锁音频",!!shot.audioLockEnabled)' in source


def test_audio_drive_backend_validates_saved_end_after_start():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'audio_drive_end = float(kwargs.get("音频驱动当前终点", 0.0))' in source
    assert 'if audio_drive_end <= lock_audio_start:' in source


def test_regular_smart_storyboard_freezes_clicked_shot_duration_for_request_and_all_generated_shots():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'duration_seconds:requestedDuration' in source
    assert 'durationSeconds:requestedDuration' in source


def test_audio_drive_prompt_tells_model_only_ordered_segment_durations():
    source = (ROOT / "audio_drive_api.py").read_text(encoding="utf-8")
    assert 'f"第{segment[\'segment_index\']}段：{segment[\'duration_seconds\']:g}秒；槽位映射：{refs}"' in source
    assert "segment['start']:g" not in source
    assert "segment['end']:g" not in source


def test_ordinary_storyboards_never_gain_audio_time_icon_and_legacy_shots_are_recovered():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'parseStoryboardBackup(localStorage.getItem(STORYBOARD_STORAGE_KEY))' in source
    assert 'localStorage.setItem(storyboardStorageKey(node),JSON.stringify(recovered))' in source
    assert 'if(existing.audioDriveEnabled){' in source
    assert 'else{delete next.audioDriveStart;delete next.audioDriveEnd;delete next.audioDriveFilename;}' in source
    assert 'const audioDriveShot=shot.audioDriveEnabled===true&&Number.isFinite(Number(shot.audioDriveStart))' in source
    assert 'audioDriveStart:Number(shots[activeShot]?.audioDriveStart)||0' not in source


def test_v10_storyboard_bar_uses_normal_flow_and_cannot_overlay_prompt_textarea():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert '.nfh3-v9-horizontal .nfh3-prompt{display:grid!important;grid-template-rows:auto 600px 268px!important;' in source
    assert '.nfh3-v9-horizontal .nfh3-storyboard-bar{grid-row:3;position:static!important;' in source
    assert '.nfh3-v9-horizontal .nfh3-storyboard-tabs{position:static!important;' in source
    assert '.nfh3-v9-horizontal .nfh3-storyboard-actions{position:static!important;' in source
    assert 'activeStoryboardButton.scrollIntoView' not in source


def test_audio_drive_time_formatter_is_available_to_main_storyboard_renderer():
    source = (ROOT / "web" / "h3_multiref.js").read_text(encoding="utf-8")
    assert 'const formatAudioDriveTime=value=>' in source
    assert '${formatAudioDriveTime(shot.audioDriveStart)} → ${formatAudioDriveTime(shot.audioDriveEnd)}' in source
    assert '${formatTime(shot.audioDriveStart)}' not in source


def test_audio_drive_and_legacy_reference_routes_are_fail_closed_until_lock_is_enabled():
    source = (ROOT / "h3_generator.py").read_text(encoding="utf-8")
    assert 'audio_drive_enabled = (' in source
    assert 'if audio_drive_enabled and not audio_lock_enabled:' in source
    assert '智能音频驱动生成必须同时勾选“开启锁音频”' in source
    assert 'lock_audio_name = audio_drive_filename if audio_drive_enabled else audio_names[0]' in source

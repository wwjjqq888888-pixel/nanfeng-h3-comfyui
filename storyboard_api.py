"""南风H3 V8.1 智能分镜：服务端读取.env，逐图看图后调用语言模型。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import mimetypes
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
SKILL_DIR = ROOT / "storyboard-skill"
SKILL_PATH = SKILL_DIR / "SKILL.md"
SKILL_REFERENCE_PATHS = (
    SKILL_DIR / "references" / "base-en.txt",
    SKILL_DIR / "references" / "ref-en.txt",
)
MAX_IMAGES = 9
MAX_IMAGE_BYTES = 30 * 1024 * 1024
_VISION_ANALYSIS_CACHE: dict[tuple[str, str, str], str] = {}
_VISION_ANALYSIS_CACHE_LIMIT = 64
VISION_CACHE_PATH = ROOT / ".vision-analysis-cache.json"
_STORYBOARD_JOBS: dict[str, "StoryboardJob"] = {}
_JOB_LOCK = threading.Lock()
CONFIG_FIELDS = (
    "NANFENG_VISION_BASE_URL", "NANFENG_VISION_API_KEY", "NANFENG_VISION_MODEL", "NANFENG_VISION_PROTOCOL",
    "NANFENG_TEXT_BASE_URL", "NANFENG_TEXT_API_KEY", "NANFENG_TEXT_MODEL", "NANFENG_TEXT_PROTOCOL",
)
CONFIG_PUBLIC_FIELDS = (
    "NANFENG_VISION_BASE_URL", "NANFENG_VISION_MODEL",
    "NANFENG_TEXT_BASE_URL", "NANFENG_TEXT_MODEL",
)
CONFIG_PROTOCOLS = {"chat_completions", "responses"}
STORYBOARD_MODES = {
    "ref2va": "多参 Ref2VA",
    "i2va": "I2V 图生视频",
    "t2va": "T2V 文生视频",
    "fl2va": "首尾帧 FL2VA",
}


class TransientAPIError(RuntimeError):
    """网络/上游瞬时故障：任务层可以安全继续等待并重试。"""


class StoryboardFormatError(ValueError):
    """已付费文本已返回但格式不标准：只做本地解析，不得重新付费请求。"""


def _load_vision_cache() -> None:
    if not VISION_CACHE_PATH.exists():
        return
    try:
        rows = json.loads(VISION_CACHE_PATH.read_text(encoding="utf-8"))
        for item in rows if isinstance(rows, list) else []:
            _VISION_ANALYSIS_CACHE[(str(item["base"]), str(item["model"]), str(item["digest"]))] = str(item["text"])
    except Exception:
        pass


def _save_vision_cache() -> None:
    rows = [{"base": k[0], "model": k[1], "digest": k[2], "text": v} for k, v in _VISION_ANALYSIS_CACHE.items()]
    temp = VISION_CACHE_PATH.with_suffix(VISION_CACHE_PATH.suffix + ".tmp")
    temp.write_text(json.dumps(rows[-_VISION_ANALYSIS_CACHE_LIMIT:], ensure_ascii=False), encoding="utf-8")
    os.replace(temp, VISION_CACHE_PATH)


class StoryboardJob:
    def __init__(self, job_id: str, payload: dict):
        self.id, self.payload = job_id, payload
        self.status, self.stage = "running", "准备任务"
        self.result, self.error, self.cancelled = None, "", False
        self.cancel_event = threading.Event()

    def public(self) -> dict:
        return {"job_id": self.id, "status": self.status, "stage": self.stage,
                "result": self.result if self.status == "completed" else None,
                "error": self.error if self.status == "failed" else ""}


def _run_storyboard_job(job: StoryboardJob) -> None:
    attempt = 0
    while not job.cancelled:
        attempt += 1
        job.stage = "逐图分析并生成完整分镜" if attempt == 1 else f"上游暂时中断，正在继续等待并恢复（第{attempt}轮）"
        try:
            value = generate_storyboard(job.payload)
            job.result = asyncio.run(value) if hasattr(value, "__await__") else value
            job.status, job.stage = "completed", "完成"
            return
        except TransientAPIError as exc:
            job.error = str(exc)
            if not job.cancelled:
                job.cancel_event.wait(min(20.0, 2.0 * attempt))
        except Exception as exc:
            job.error = str(exc)
            job.status, job.stage = "failed", "返回内容需要检查，未重复付费生成"
            return
    job.status, job.stage = "cancelled", "已取消"


_load_vision_cache()


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values


def config_status(env: dict[str, str] | None = None) -> dict:
    cfg = env or load_env()
    vision = all(cfg.get(k, "").strip() for k in (
        "NANFENG_VISION_API_KEY", "NANFENG_VISION_BASE_URL", "NANFENG_VISION_MODEL"
    ))
    text = all(cfg.get(k, "").strip() for k in (
        "NANFENG_TEXT_API_KEY", "NANFENG_TEXT_BASE_URL", "NANFENG_TEXT_MODEL"
    ))
    return {"vision_configured": vision, "text_configured": text, "skill_exists": SKILL_PATH.exists()}


def config_for_browser(env: dict[str, str] | None = None) -> dict:
    """Return editable non-secret fields and only booleans for stored keys."""
    cfg = env or load_env()
    result = config_status(cfg)
    result.update({key: cfg.get(key, "") for key in CONFIG_PUBLIC_FIELDS})
    result["vision_key_saved"] = bool(cfg.get("NANFENG_VISION_API_KEY", "").strip())
    result["text_key_saved"] = bool(cfg.get("NANFENG_TEXT_API_KEY", "").strip())
    return result


def normalize_base_url(value: str) -> str:
    """Normalize an OpenAI-compatible base URL to end at /v1."""
    base = str(value or "").strip().rstrip("/")
    if not base:
        return ""
    base = re.sub(r"/(?:chat/completions|responses|models)$", "", base, flags=re.I).rstrip("/")
    if not re.search(r"/v\d+$", base, re.I):
        base += "/v1"
    return base


def _validate_config_payload(payload: dict) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("配置参数格式错误")
    values: dict[str, str] = {}
    for key in CONFIG_FIELDS:
        value = payload.get(key)
        if value is None:
            continue
        if key.endswith("_PROTOCOL"):
            continue
        if not isinstance(value, str):
            raise ValueError(f"{key}必须是文本")
        value = value.strip()
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key}不能包含换行")
        values[key] = value
    for key in ("NANFENG_VISION_BASE_URL", "NANFENG_TEXT_BASE_URL"):
        value = values.get(key)
        if value and not re.match(r"^https?://", value, re.I):
            raise ValueError(f"{key}必须以http://或https://开头")
        if value:
            values[key] = normalize_base_url(value)
    for key in ("NANFENG_VISION_PROTOCOL", "NANFENG_TEXT_PROTOCOL"):
        value = values.get(key)
        if value and value not in CONFIG_PROTOCOLS:
            raise ValueError(f"{key}只支持chat_completions或responses")
    return values


def save_config(payload: dict, path: Path = ENV_PATH) -> dict:
    """Atomically update package .env; blank key means retain the stored key."""
    current = load_env(path)
    values = _validate_config_payload(payload)
    for key, value in values.items():
        if key.endswith("_API_KEY") and not value:
            continue
        current[key] = value
    current["NANFENG_VISION_PROTOCOL"] = "chat_completions"
    current["NANFENG_TEXT_PROTOCOL"] = "chat_completions"
    lines = ["# 南风H3 V8.1 智能分镜API配置（仅服务端读取）"]
    for key in CONFIG_FIELDS:
        lines.append(f"{key}={current.get(key, '')}")
        if key == "NANFENG_VISION_PROTOCOL":
            lines.append("")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)
    return config_for_browser(current)


def clear_config(path: Path = ENV_PATH) -> dict:
    blank = {key: "" for key in CONFIG_FIELDS}
    blank["NANFENG_VISION_PROTOCOL"] = "chat_completions"
    blank["NANFENG_TEXT_PROTOCOL"] = "chat_completions"
    lines = ["# 南风H3 V8.1 智能分镜API配置（仅服务端读取）"]
    for key in CONFIG_FIELDS:
        lines.append(f"{key}={blank[key]}")
        if key == "NANFENG_VISION_PROTOCOL":
            lines.append("")
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)
    return config_for_browser(blank)


def _endpoint(base_url: str, protocol: str) -> str:
    base = base_url.rstrip("/")
    suffix = "/responses" if protocol == "responses" else "/chat/completions"
    return base if base.endswith(suffix) else base + suffix


def list_models(base_url: str, api_key: str, timeout: int = 60) -> list[str]:
    base = normalize_base_url(base_url)
    if not base or not api_key.strip():
        raise ValueError("请先填写Base URL和API Key")
    req = urllib.request.Request(
        base.rstrip("/") + "/models",
        headers={"Accept": "application/json", "Authorization": f"Bearer {api_key.strip()}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"识别模型失败 HTTP {exc.code}: {body[:500]}") from exc
    except Exception as exc:
        raise RuntimeError(f"识别模型连接失败：{exc}") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"模型接口返回的不是JSON：{body[:300]}") from exc
    raw = data.get("data", data.get("models", [])) if isinstance(data, dict) else data
    models: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        value = item.get("id") or item.get("name") if isinstance(item, dict) else item
        if isinstance(value, str) and value.strip():
            models.append(value.strip())
    models = sorted(set(models), key=str.lower)
    if not models:
        raise RuntimeError("中转/models没有返回可用模型ID")
    return models


def _extract_text(data: dict) -> str:
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        text = "\n".join(str(x.get("text", "")) for x in content if isinstance(x, dict)).strip()
        if text:
            return text
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    pieces = []
    for item in data.get("output", []):
        for part in item.get("content", []):
            value = part.get("text") or part.get("output_text")
            if isinstance(value, str):
                pieces.append(value)
    text = "\n".join(pieces).strip()
    if not text:
        choices = data.get("choices") if isinstance(data, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), dict) else {}
        reasoning_used = bool(message.get("reasoning_content")) or int(details.get("reasoning_tokens") or 0) > 0
        if choice.get("finish_reason") == "length" or reasoning_used:
            raise StoryboardFormatError("模型已返回但正文为空：输出预算可能被思考过程耗尽；未重复付费请求")
        raise StoryboardFormatError("模型已返回成功响应但正文为空；未重复付费请求")
    return text


def _is_official_deepseek(base_url: str) -> bool:
    """Only send DeepSeek-specific fields to the official endpoint, preserving relay compatibility."""
    from urllib.parse import urlparse
    try:
        return (urlparse(normalize_base_url(base_url)).hostname or "").lower() == "api.deepseek.com"
    except Exception:
        return False


def request_model(base_url: str, api_key: str, model: str, messages: list[dict], *, protocol: str = "chat_completions",
                  temperature: float = 0.0, timeout: int = 300, attempts: int = 5,
                  max_output_tokens: int | None = None, disable_reasoning: bool = False) -> str:
    protocol = protocol.strip().lower() or "chat_completions"
    if protocol == "responses":
        payload = {"model": model, "input": messages, "stream": False}
        if max_output_tokens is not None:
            payload["max_output_tokens"] = int(max_output_tokens)
    else:
        payload = {"model": model, "messages": messages, "temperature": temperature, "stream": False}
        if max_output_tokens is not None:
            payload["max_tokens"] = int(max_output_tokens)
        if disable_reasoning and _is_official_deepseek(base_url):
            payload["thinking"] = {"type": "disabled"}
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        req = urllib.request.Request(
            _endpoint(base_url, protocol),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", "replace")
            data = json.loads(body)
            text = _extract_text(data)
            return text
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                raise RuntimeError(f"API HTTP {exc.code}: {body[:800]}") from exc
            last_error = RuntimeError(f"API HTTP {exc.code}: {body[:800]}")
        except (urllib.error.URLError, ssl.SSLError, ConnectionError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
        except StoryboardFormatError:
            raise
        except RuntimeError as exc:
            raise StoryboardFormatError(f"模型已返回但内容无法使用：{exc}；未重复付费请求") from exc
        except Exception as exc:
            last_error = exc
        if attempt + 1 < max(1, attempts):
            time.sleep(1.5 * (attempt + 1))
    raise TransientAPIError(f"API连接或返回失败（本轮已重试{max(1, attempts)}次）：{last_error}") from last_error


def resolve_input_images(names: list[str]) -> list[dict]:
    import folder_paths

    images = []
    for index, raw in enumerate(names[:MAX_IMAGES], 1):
        name = str(raw or "").strip()
        if not name or name in {"未选择", "None", "null"}:
            continue
        path = Path(folder_paths.get_annotated_filepath(name)).resolve()
        input_root = Path(folder_paths.get_input_directory()).resolve()
        if input_root not in path.parents and path != input_root:
            raise ValueError(f"图片{index}不在ComfyUI input目录")
        if not path.is_file():
            raise FileNotFoundError(f"图片{index}不存在：{name}")
        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            raise ValueError(f"图片{index}超过30MB")
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"图片{index}只支持JPEG、PNG、WebP")
        images.append({"index": index, "name": path.name, "mime": mime, "base64": base64.b64encode(path.read_bytes()).decode("ascii")})
    return images


def vision_messages(image: dict) -> list[dict]:
    index = image["index"]
    text = (
        f"你现在只分析一张参考图片，固定编号是@图片{index}。严格分类为人物图、场景图、产品或道具图三类之一。"
        "提取人物身份、外貌、服装、姿态和朝向，或场景空间结构、光线、时间天气，或道具材质、颜色、朝向和状态。"
        "只分析当前图片，不关联其他图片，不编造。不要自行添加其他@图片编号。"
    )
    return [{"role": "user", "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:{image['mime']};base64,{image['base64']}"}},
    ]}]


async def analyze_images(images: list[dict], cfg: dict[str, str]) -> str:
    semaphore = asyncio.Semaphore(max(1, min(3, len(images) or 1)))

    async def one(image: dict) -> str:
        async with semaphore:
            digest = hashlib.sha256(image["base64"].encode("ascii")).hexdigest()
            cache_key = (normalize_base_url(cfg["NANFENG_VISION_BASE_URL"]), cfg["NANFENG_VISION_MODEL"], digest)
            cached = _VISION_ANALYSIS_CACHE.get(cache_key)
            if cached is not None:
                return f"@图片{image['index']}：{cached}"
            raw = await asyncio.to_thread(
                request_model,
                cfg["NANFENG_VISION_BASE_URL"], cfg["NANFENG_VISION_API_KEY"], cfg["NANFENG_VISION_MODEL"],
                vision_messages(image), protocol=cfg.get("NANFENG_VISION_PROTOCOL", "chat_completions"), temperature=0.0,
                max_output_tokens=1600,
            )
            clean = re.sub(r"^\s*@图片\d+\s*[:：]\s*", "", raw).strip()
            if len(_VISION_ANALYSIS_CACHE) >= _VISION_ANALYSIS_CACHE_LIMIT:
                _VISION_ANALYSIS_CACHE.pop(next(iter(_VISION_ANALYSIS_CACHE)))
            _VISION_ANALYSIS_CACHE[cache_key] = clean
            _save_vision_cache()
            return f"@图片{image['index']}：{clean}"

    return "\n\n".join(await asyncio.gather(*(one(image) for image in images)))


def validate_mode(mode: str, images: list[dict]) -> str:
    mode = str(mode or "ref2va").strip().lower()
    if mode not in STORYBOARD_MODES:
        raise ValueError("提示词模式无效")
    required = {"t2va": 0, "i2va": 1, "fl2va": 2}
    if mode in required and len(images) != required[mode]:
        labels = {"t2va": "T2V文生视频不能使用参考图片", "i2va": "I2V图生视频必须且只能使用@图片1", "fl2va": "首尾帧必须使用@图片1首帧和@图片2尾帧"}
        raise ValueError(labels[mode])
    if mode == "ref2va" and not images:
        raise ValueError("多参模式至少需要1张参考图片")
    return mode


def mode_contract(mode: str, count: int) -> str:
    common = f"严格输出{count}段。从段1开始依次编号到段{count}；每个标题行只能写对应的‘段N’，不得写‘段1到段{count}’或其他文字。段之间用---分隔。每段必须是可直接复制使用的完整官方提示词。"
    if mode == "ref2va":
        return common + "当前模式为Ref2VA多参。每段严格依次输出subject_definitions、summary、retention_analysis、detailed_description、overall_soundscape、non_diegetic_music六段，使用<Subject N>/<Picture N>。"
    if mode == "i2va":
        return common + "当前模式为I2VA图生视频。每段先写@图片1对应Picture 1在0.00秒的官方首帧对齐句，再依次输出integrated_multimodal_description、overall_soundscape、non_diegetic_music。"
    if mode == "fl2va":
        return common + "当前模式为FL2VA首尾帧。每段先写Picture 1对齐0.00秒、Picture 2对齐该段结束时刻的官方首尾对齐句，再依次输出integrated_multimodal_description、overall_soundscape、non_diegetic_music。"
    return common + "当前模式为T2VA文生视频。不得写任何Picture/Video/Audio引用或对齐句；每段严格依次输出integrated_multimodal_description、overall_soundscape、non_diegetic_music。"


def storyboard_messages(skill: str, idea: str, count: int, images: list[dict], analysis: str,
                        mode: str = "ref2va", duration_seconds: float = 5.0) -> list[dict]:
    manifest = "\n".join(f"@图片{x['index']}：{x['name']}" for x in images) or "无图片"
    duration_label = f"{duration_seconds:g}"
    return [
        {"role": "system", "content": "严格执行下面的H3官方提示词Skill和当前模式契约，只输出正式结果，不解释。\n\n" + skill},
        {"role": "user", "content": (
            f"当前官方模式：{STORYBOARD_MODES[mode]}\n"
            f"硬性时长先决条件：每个分镜对应{duration_label}秒视频。必须先按{duration_label}秒重新规划动作密度、镜头数量、对白长度、动作收束和段尾状态；不得按默认5秒或其他时长写作。\n"
            f"{mode_contract(mode, count)}\n\n"
            f"用户想法：\n{idea or '请根据参考素材合理创作。'}\n\n"
            f"固定上传槽位：\n{manifest}\n\n逐图看图结果：\n{analysis or '无'}\n\n"
            "禁止追问。图片编号严格绑定上传槽位，不重排、不编造；用户原有对白必须保留说话人、原意和顺序。"
        )},
    ]


def parse_storyboard(text: str, count: int) -> dict:
    raw = re.sub(r"```(?:text)?|```", "", str(text)).strip()
    global_match = re.search(r"全局提示词\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:---\s*)?\n?\s*段\s*1\b|$)", raw)
    global_prompt = global_match.group(1).strip() if global_match else ""
    matches = list(re.finditer(r"(?m)^\s*段\s*(\d+)\s*[:：]?\s*$", raw))
    if any(int(match.group(1)) != index for index, match in enumerate(matches, 1)):
        raise StoryboardFormatError("模型返回的段号存在跳号、重复或顺序错误")
    segments = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        segments.append(raw[match.start():end].strip().rstrip("-").strip())
    if len(segments) != count:
        if count == 1 and not matches and raw:
            segments = [raw]
        else:
            blocks = [x.strip() for x in re.split(r"(?m)^\s*---+\s*$", raw) if x.strip()]
            if len(blocks) == count:
                segments = [f"段{i}\n\n{block}" for i, block in enumerate(blocks, 1)]
            else:
                raise StoryboardFormatError(f"模型返回{len(segments)}段，但要求{count}段；原始完整输出已收到，未重复生成")
    return {"global": global_prompt, "segments": segments, "raw": raw}


def load_storyboard_skill(mode: str = "ref2va") -> str:
    if not SKILL_PATH.exists():
        return "输出适合MiniMax H3官方结构的连续视频提示词。"
    sections = [SKILL_PATH.read_text(encoding="utf-8")]
    reference_name = "ref-en.txt" if str(mode).strip().lower() == "ref2va" else "base-en.txt"
    path = SKILL_DIR / "references" / reference_name
    if path.exists():
        sections.append(f"\n\n---\n\n# Embedded reference: {path.name}\n\n{path.read_text(encoding='utf-8')}")
    return "".join(sections)


def storyboard_output_budget(segment_count: int) -> int:
    """Keep enough room for complete official fields while avoiding a universal 24K reasoning budget."""
    count = max(1, min(12, int(segment_count)))
    return min(24000, 4200 + 1800 * count)


async def generate_storyboard(payload: dict, cfg: dict[str, str] | None = None) -> dict:
    config = cfg or load_env()
    status = config_status(config)
    if not status["text_configured"]:
        raise ValueError("语言模型API尚未在节点包.env完整配置")
    count = int(payload.get("segment_count", 1))
    if count < 1 or count > 12:
        raise ValueError("分镜段数必须为1到12")
    duration_seconds = float(payload.get("duration_seconds", 5.0))
    if duration_seconds < 1.0 or duration_seconds > 15.0:
        raise ValueError("视频时长必须为1到15秒")
    names = payload.get("images") or []
    if not isinstance(names, list):
        raise ValueError("图片参数格式错误")
    images = resolve_input_images(names)
    mode = validate_mode(payload.get("mode", "ref2va"), images)
    if images and not status["vision_configured"]:
        raise ValueError("已添加图片，但看图API尚未在节点包.env完整配置")
    skill = load_storyboard_skill(mode)
    analysis = await analyze_images(images, config) if images else ""
    messages = storyboard_messages(skill, str(payload.get("idea", "")).strip(), count, images, analysis, mode, duration_seconds)
    result = await asyncio.to_thread(
        request_model,
        config["NANFENG_TEXT_BASE_URL"], config["NANFENG_TEXT_API_KEY"], config["NANFENG_TEXT_MODEL"], messages,
        protocol=config.get("NANFENG_TEXT_PROTOCOL", "chat_completions"), temperature=0.7, timeout=600,
        max_output_tokens=storyboard_output_budget(count), disable_reasoning=True,
    )
    parsed = parse_storyboard(result, count)
    parsed["vision_analysis"] = analysis
    return parsed


def register_routes() -> None:
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception:
        return

    prompt_server = getattr(PromptServer, "instance", None)
    if prompt_server is None:
        return
    routes = prompt_server.routes

    @routes.get("/nanfeng/h3/storyboard/config")
    async def get_config(_request):
        return web.json_response(config_for_browser())

    @routes.post("/nanfeng/h3/storyboard/config")
    async def update_config(request):
        try:
            return web.json_response({"ok": True, **save_config(await request.json())})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.delete("/nanfeng/h3/storyboard/config")
    async def delete_config(_request):
        try:
            return web.json_response({"ok": True, **clear_config()})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/nanfeng/h3/storyboard/models")
    async def discover_models(request):
        try:
            payload = await request.json()
            kind = str(payload.get("kind", "vision")).strip().lower()
            if kind not in {"vision", "text"}:
                raise ValueError("模型类型必须是vision或text")
            cfg = load_env()
            prefix = "NANFENG_VISION" if kind == "vision" else "NANFENG_TEXT"
            base_url = str(payload.get("base_url", "")).strip() or cfg.get(f"{prefix}_BASE_URL", "")
            api_key = str(payload.get("api_key", "")).strip() or cfg.get(f"{prefix}_API_KEY", "")
            models = await asyncio.to_thread(list_models, base_url, api_key)
            return web.json_response({"ok": True, "base_url": normalize_base_url(base_url), "models": models})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/nanfeng/h3/storyboard/generate")
    async def generate(request):
        try:
            payload = await request.json()
            return web.json_response({"ok": True, **(await generate_storyboard(payload))})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)

    @routes.post("/nanfeng/h3/storyboard/jobs")
    async def create_job(request):
        job_id = uuid.uuid4().hex
        job = StoryboardJob(job_id, await request.json())
        with _JOB_LOCK:
            _STORYBOARD_JOBS[job_id] = job
        threading.Thread(target=_run_storyboard_job, args=(job,), daemon=True, name=f"nanfeng-storyboard-{job_id[:8]}").start()
        return web.json_response({"ok": True, "job_id": job_id})

    @routes.get("/nanfeng/h3/storyboard/jobs/{job_id}")
    async def get_job(request):
        job = _STORYBOARD_JOBS.get(request.match_info["job_id"])
        if job is None:
            return web.json_response({"ok": False, "error": "任务不存在"}, status=404)
        return web.json_response({"ok": True, **job.public()})

    @routes.delete("/nanfeng/h3/storyboard/jobs/{job_id}")
    async def cancel_job(request):
        job = _STORYBOARD_JOBS.get(request.match_info["job_id"])
        if job is None:
            return web.json_response({"ok": False, "error": "任务不存在"}, status=404)
        job.cancelled = True
        job.cancel_event.set()
        return web.json_response({"ok": True, "status": "cancelling"})


register_routes()

from pathlib import Path

ROOT = Path(__file__).resolve().parent
JS = ROOT / "web" / "h3_multiref.js"
PY = ROOT / "h3_generator.py"


def test_v10_schema_appends_constant_trigger_after_existing_v10_fields():
    source = PY.read_text(encoding="utf-8")
    class_start = source.index("class NanFengH3MultiReferenceGeneratorV10")
    class_end = source.index("NODE_CLASS_MAPPINGS", class_start)
    block = source[class_start:class_end]
    assert 'schema["required"]["恒定触发词"]' in block
    assert block.index('schema["required"]["音频驱动当前终点"]') < block.index('schema["required"]["恒定触发词"]')


def test_v10_prompt_section_is_not_collapsible():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'const promptSection=isV9(node)?plainSection("提示词与 @ 素材引用",[triggerBox,promptBox])' in source


def test_constant_trigger_is_single_line_and_prefixes_without_blank_lines():
    source = JS.read_text(encoding="utf-8-sig")
    assert 'trigger.type="text"' in source
    assert 'trigger.dataset.widgetName="恒定触发词"' in source
    assert 'function composeTriggeredPrompt(triggerText,promptText)' in source
    assert 'return head&&body?`${head}\\n${body}`:head||body;' in source
    assert 'prompt:stripConstantTrigger(trigger.value,prompt.value)' not in source
    assert 'setWidget(node,"恒定触发词",trigger.value)' in source

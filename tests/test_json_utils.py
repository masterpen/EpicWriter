"""json_utils 单元测试：LLM 输出 JSON 解析的鲁棒性。"""
import json
from app.core.json_utils import parse_llm_json, strip_code_fences


class TestStripCodeFences:
    def test_plain_text_unchanged(self):
        assert strip_code_fences("hello world") == "hello world"

    def test_empty_string(self):
        assert strip_code_fences("") == ""

    def test_none_returns_empty(self):
        assert strip_code_fences(None) == ""

    def test_markdown_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        # strip_code_fences 移除围栏标记，保留内容（含尾部换行，parse_llm_json 会处理）
        result = strip_code_fences(text)
        assert result.strip() == '{"key": "value"}'
        # 确认 json 能被正常解析
        assert json.loads(result) == {"key": "value"}

    def test_plain_markdown_fence(self):
        text = '```\n{"key": "value"}\n```'
        result = strip_code_fences(text)
        assert result.strip() == '{"key": "value"}'
        assert json.loads(result) == {"key": "value"}

    def test_triple_single_quote_fence(self):
        text = "'''json\n{\"key\": \"value\"}\n'''"
        result = strip_code_fences(text)
        assert result.strip() == '{"key": "value"}'
        assert json.loads(result) == {"key": "value"}

    def test_chinese_quotes_preserved_in_valid_json(self):
        """合法 JSON 中的中文引号（字符串值）应保留，不被替换（避免破坏结构）"""
        text = '{"key": "value\u201d}'
        cleaned = strip_code_fences(text)
        # strip_code_fences 不再替换中文引号
        assert "\u201d" in cleaned

    def test_chinese_quotes_parse_success(self):
        """含中文引号的合法 JSON 应能直接解析（json.loads 无需替换）"""
        # U+201D 在字符串值内部（由 ASCII 引号闭合），是合法 JSON
        text = '{"key": "value\u201d"}'
        result = parse_llm_json(text)
        assert result == {"key": "value\u201d"}

    def test_chinese_quotes_repair_after_fail(self):
        """仅当 JSON 结构因中文引号损坏时，parse_llm_json 才修复引号后重试"""
        # LLM 把 JSON 键/值的引号写成了中文引号（“ ”），json.loads 直接失败
        text = '{“key”: “value”}'
        result = parse_llm_json(text)
        # repair 后是合法 JSON 且能解析出正确结构
        assert result == {"key": "value"}


class TestParseLlmJson:
    def test_valid_json_object(self):
        text = '{"name": "test", "value": 42}'
        result = parse_llm_json(text)
        assert result == {"name": "test", "value": 42}

    def test_valid_json_array(self):
        text = '[1, 2, 3]'
        result = parse_llm_json(text, extract_array=True)
        assert result == [1, 2, 3]

    def test_json_with_code_fence(self):
        text = '```json\n{"chapter_title": "test"}\n```'
        result = parse_llm_json(text)
        assert result == {"chapter_title": "test"}

    def test_json_embedded_in_text(self):
        text = '好的，以下是结果：\n{"scene": "battle"}\n以上是结果。'
        result = parse_llm_json(text)
        assert result == {"scene": "battle"}

    def test_invalid_json_returns_default(self):
        result = parse_llm_json("not json at all", default={})
        assert result == {}

    def test_empty_string_returns_default(self):
        result = parse_llm_json("", default=None)
        assert result is None

    def test_none_returns_default(self):
        result = parse_llm_json(None, default=[])
        assert result == []

    def test_default_none_when_not_specified(self):
        result = parse_llm_json("invalid")
        assert result is None

    def test_extract_array_finds_first_array(self):
        text = '好的，以下是结果：\n[{"option": "A"}, {"option": "B"}]\n以上。'
        result = parse_llm_json(text, extract_array=True)
        assert result == [{"option": "A"}, {"option": "B"}]

    def test_nested_object(self):
        text = '{"outer": {"inner": "value"}}'
        result = parse_llm_json(text)
        assert result == {"outer": {"inner": "value"}}

    def test_chinese_quotes_in_json(self):
        text = '{\u201ckey\u201d: \u201cvalue\u201d}'
        result = parse_llm_json(text)
        assert result == {"key": "value"}

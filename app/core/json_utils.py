"""LLM 输出的 JSON 解析工具。

统一处理:
- 剥离 ```json / ``` / ''' / \"\"\" 等代码块包裹
- 修复中文引号
- 提取首个 {...} 或 [...] JSON 片段
- 解析失败时返回默认值
"""
import json
import re
from typing import Any, Union

# 各种包裹格式的剥离模式
_FENCE_PATTERNS = [
    r"^```json\s*", r"^```\s*", r"```$",
    r"^'''json\s*", r"^'''\s*", r"'''$",
    r'^"""json\s*', r'^"""\s*', r'"""$',
]

# 中文引号 → 英文引号
_QUOTE_REPLACEMENTS = {
    "\u201c": '"',  # 左双引号 "
    "\u201d": '"',  # 右双引号 "
    "\u2018": "'",  # 左单引号 '
    "\u2019": "'",  # 右单引号 '
}


def strip_code_fences(text: str) -> str:
    """剥离 LLM 输出中的代码块包裹（```json / ''' / \"\"\" 等）"""
    if not text:
        return ""
    cleaned = text.strip()
    for pattern in _FENCE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE)
    return cleaned


def _repair_quotes(text: str) -> str:
    """把中文引号替换为英文引号（仅在 JSON 解析失败后尝试，避免破坏合法 JSON）"""
    for cn, en in _QUOTE_REPLACEMENTS.items():
        text = text.replace(cn, en)
    return text


def parse_llm_json(
    text: str,
    default: Any = None,
    extract_array: bool = False,
) -> Union[dict, list, Any]:
    """鲁棒地解析 LLM 输出为 JSON。

    Args:
        text: LLM 原始输出
        default: 解析失败时返回的默认值（默认 None）
        extract_array: 是否提取 [...] 数组片段（默认提取 {...} 对象）

    Returns:
        解析后的 dict / list，或 default
    """
    if not text:
        return default

    cleaned = strip_code_fences(text)

    # 1. 直接解析（中文引号在 JSON 字符串值中合法，不预先替换）
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. 正则提取首个 JSON 片段
    pattern = r"\[[\s\S]*\]" if extract_array else r"\{[\s\S]*\}"
    try:
        match = re.search(pattern, cleaned)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    # 3. 修复中文引号后重试（仅此时替换，避免破坏合法 JSON）
    repaired = _repair_quotes(cleaned)
    try:
        return json.loads(repaired)
    except Exception:
        pass

    return default

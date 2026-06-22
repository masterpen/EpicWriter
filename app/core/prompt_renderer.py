"""Prompt 渲染器：用字典变量渲染模板字符串（支持 {var} 格式）"""
from typing import Dict


def render_prompt(template: str, variables: Dict[str, str]) -> str:
    """安全渲染模板字符串，替换 {key} 占位符"""
    result = template
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value))
    return result
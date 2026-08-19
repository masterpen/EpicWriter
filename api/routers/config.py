from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.core.agent_config import (
    AgentLLMConfig, LLMConfig, LLMProvider, ProviderConfig, ModelOption,
    _DEFAULT_BASE_URLS, _DEFAULT_MODELS, _DEFAULT_MODELS_LIST
)
from app.core.database import db
from app.core.logger import logger
import asyncio

router = APIRouter(prefix="/api/config", tags=["Config"])


def _load_llm_config_from_db() -> Optional[AgentLLMConfig]:
    """从Neo4j加载LLM配置"""
    try:
        stored = db.get_system_config("llm_config")
        if stored:
            return AgentLLMConfig.model_validate_json(stored)
    except Exception as e:
        logger.warning(f"从数据库加载LLM配置失败: {e}")
    return None


def _save_llm_config_to_db(config: AgentLLMConfig):
    """保存LLM配置到Neo4j"""
    db.set_system_config("llm_config", config.model_dump_json())
    # 同步到全局 llm_bridge
    from app.core.llm_bridge import llm_bridge
    llm_bridge.config = config
    llm_bridge._client = None


def _get_or_init_config() -> AgentLLMConfig:
    """获取或初始化配置"""
    cfg = _load_llm_config_from_db()
    if cfg:
        return cfg
    return AgentLLMConfig()


# ===================== 请求/响应模型 =====================

class ModelOptionRequest(BaseModel):
    model_name: str
    display_name: str = ""
    is_default: bool = False


class ProviderConfigUpdate(BaseModel):
    """更新提供商配置"""
    provider: str
    api_key: str = ""
    base_url: Optional[str] = None
    models: Optional[List[ModelOptionRequest]] = None  # 自定义模型列表
    current_model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096


class ProviderSwitchRequest(BaseModel):
    provider: str
    model: Optional[str] = None  # 切换时可同时指定模型


class AddModelRequest(BaseModel):
    """给指定提供商添加一个模型"""
    provider: str
    model_name: str
    display_name: str = ""


class RemoveModelRequest(BaseModel):
    """从指定提供商移除一个模型"""
    provider: str
    model_name: str


# ===================== API 端点 =====================

@router.get("/llm", response_model=Dict[str, Any])
def get_llm_config():
    """获取当前 LLM 配置（包含所有提供商和模型信息）"""
    # 确保先从DB加载最新配置
    from app.core.llm_bridge import llm_bridge
    llm_bridge._try_load_from_db()
    
    config = _get_or_init_config()
    result = config.model_dump()

    # 隐藏 API Key，只标记是否已配置
    for provider_name in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        pcfg = result.get(provider_name)
        if pcfg is None or not isinstance(pcfg, dict):
            # provider 字段为 None 或非 dict，填充默认
            result[provider_name] = {
                'provider': provider_name,
                'api_key': '',
                'base_url': _DEFAULT_BASE_URLS.get(provider_name, ''),
                'models': [m.model_dump() for m in _DEFAULT_MODELS_LIST.get(provider_name, [])],
                'current_model': _DEFAULT_MODELS.get(provider_name, ''),
                'temperature': 0.7,
                'max_tokens': 4096,
                'enabled': False,
            }
        elif pcfg.get('api_key'):
            pcfg['api_key_stored'] = True
            pcfg['api_key'] = '••••••••'  # 不返回真实 key
            pcfg['enabled'] = True
        else:
            pcfg['enabled'] = False

    result['configured'] = any(
        (result.get(p) or {}).get('api_key_stored') or (result.get(p) or {}).get('api_key')
        for p in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']
    )
    return result


@router.post("/llm")
def update_llm_config(req: ProviderConfigUpdate):
    """更新指定提供商的 LLM 配置"""
    provider = req.provider.lower()
    if provider not in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        raise HTTPException(status_code=400, detail=f"无效的提供商: {provider}")

    config = _get_or_init_config()
    provider_enum = LLMProvider(provider)

    # 获取或创建该提供商的配置
    existing = config.get_provider_config(provider_enum)

    # 处理 API Key：如果传入空字符串，保留旧值
    api_key = req.api_key
    if not api_key and existing and existing.api_key:
        api_key = existing.api_key  # 保留已存储的 key

    # 处理模型列表
    models = []
    if req.models:
        models = [ModelOption(**m.model_dump()) for m in req.models]
    elif existing and existing.models:
        models = existing.models
    else:
        models = _DEFAULT_MODELS_LIST.get(provider, [])

    # 确保当前模型在列表中
    current_model = req.current_model or (existing.current_model if existing else "")
    if current_model and not any(m.model_name == current_model for m in models):
        models.append(ModelOption(model_name=current_model, display_name=current_model))

    # 设置默认模型的 is_default 标记
    for m in models:
        m.is_default = (m.model_name == current_model)

    provider_config = ProviderConfig(
        provider=provider_enum,
        api_key=api_key,
        base_url=req.base_url or (existing.get_effective_base_url() if existing else _DEFAULT_BASE_URLS.get(provider, "")),
        models=models,
        current_model=current_model or (models[0].model_name if models else ""),
        temperature=req.temperature if req.temperature is not None else (existing.temperature if existing else 0.7),
        max_tokens=req.max_tokens if req.max_tokens is not None else (existing.max_tokens if existing else 4096),
        enabled=bool(api_key),
    )

    setattr(config, provider, provider_config)

    # 如果更新的是当前提供商，同步 current_model
    if config.current_provider == provider_enum and current_model:
        config.current_model = current_model

    _save_llm_config_to_db(config)
    return {"status": "success", "message": f"{provider} 配置已更新并持久化"}


@router.post("/llm/switch")
def switch_provider(req: ProviderSwitchRequest):
    """切换当前使用的 LLM 提供商和模型"""
    provider = req.provider.lower()
    if provider not in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        raise HTTPException(status_code=400, detail=f"无效的提供商: {provider}")

    config = _get_or_init_config()
    provider_enum = LLMProvider(provider)

    # 检查该提供商是否已配置
    pcfg = config.get_provider_config(provider_enum)
    if not pcfg or not pcfg.api_key:
        raise HTTPException(status_code=400, detail=f"{provider} 尚未配置 API Key，请先在设置页面配置。")

    # 切换提供商
    config.current_provider = provider_enum

    # 确定模型
    model = req.model or pcfg.current_model or pcfg.get_effective_model()
    config.current_model = model
    pcfg.current_model = model

    _save_llm_config_to_db(config)
    return {"status": "success", "current_provider": provider, "current_model": model}


@router.post("/llm/model/add")
def add_model(req: AddModelRequest):
    """给指定提供商添加一个自定义模型"""
    provider = req.provider.lower()
    if provider not in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        raise HTTPException(status_code=400, detail=f"无效的提供商: {provider}")

    config = _get_or_init_config()
    provider_enum = LLMProvider(provider)
    pcfg = config.get_or_create_provider_config(provider_enum)

    # 检查是否已存在
    if any(m.model_name == req.model_name for m in pcfg.models):
        raise HTTPException(status_code=400, detail=f"模型 {req.model_name} 已存在")

    pcfg.models.append(ModelOption(
        model_name=req.model_name,
        display_name=req.display_name or req.model_name,
    ))

    setattr(config, provider, pcfg)
    _save_llm_config_to_db(config)
    return {"status": "success", "message": f"已添加模型 {req.model_name}"}


@router.post("/llm/model/remove")
def remove_model(req: RemoveModelRequest):
    """从指定提供商移除一个模型"""
    provider = req.provider.lower()
    if provider not in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        raise HTTPException(status_code=400, detail=f"无效的提供商: {provider}")

    config = _get_or_init_config()
    provider_enum = LLMProvider(provider)
    pcfg = config.get_provider_config(provider_enum)

    if not pcfg:
        raise HTTPException(status_code=400, detail=f"{provider} 尚未配置")

    # 不能删除最后一个模型
    if len(pcfg.models) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个模型")

    # 不能删除当前使用的模型
    if pcfg.current_model == req.model_name:
        raise HTTPException(status_code=400, detail="不能删除当前使用的模型")

    pcfg.models = [m for m in pcfg.models if m.model_name != req.model_name]
    setattr(config, provider, pcfg)
    _save_llm_config_to_db(config)
    return {"status": "success", "message": f"已移除模型 {req.model_name}"}


@router.post("/llm/test")
async def test_llm_connection(req: ProviderConfigUpdate):
    """测试 LLM API 连接"""
    import openai

    provider = req.provider.lower()
    base_url = req.base_url or _DEFAULT_BASE_URLS.get(provider, "")

    if not base_url:
        raise HTTPException(status_code=400, detail="需要配置 Base URL")

    # 如果没传 api_key，尝试从已保存的配置中获取
    api_key = req.api_key
    if not api_key:
        config = _get_or_init_config()
        pcfg = config.get_provider_config(LLMProvider(provider))
        if pcfg and pcfg.api_key:
            api_key = pcfg.api_key
        else:
            raise HTTPException(status_code=400, detail="需要提供 API Key")

    # 确定测试模型
    model = req.current_model or _DEFAULT_MODELS.get(provider, "gpt-4o")

    def _do_test():
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=10.0
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        return True

    try:
        await asyncio.to_thread(_do_test)
        return {"status": "success", "message": f"API 连接成功！模型: {model}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"API 连接失败: {str(e)}")


@router.get("/llm/providers")
def get_available_providers():
    """获取所有可用的提供商及其模型（用于书籍页面选择）"""
    config = _get_or_init_config()
    result = []

    for provider_name in ['deepseek', 'openai', 'openrouter', 'anthropic', 'nvidia', 'custom']:
        pcfg = config.get_provider_config(LLMProvider(provider_name))
        provider_info = {
            "provider": provider_name,
            "name": _PROVIDER_DISPLAY_NAMES.get(provider_name, provider_name),
            "icon": _PROVIDER_ICONS.get(provider_name, "⚙️"),
            "enabled": bool(pcfg and pcfg.api_key),
            "current_model": pcfg.current_model if pcfg else "",
            "models": [],
            "base_url": pcfg.get_effective_base_url() if pcfg else _DEFAULT_BASE_URLS.get(provider_name, ""),
        }

        if pcfg and pcfg.api_key:
            for m in pcfg.models:
                provider_info["models"].append({
                    "model_name": m.model_name,
                    "display_name": m.display_name or m.model_name,
                    "is_default": m.is_default or m.model_name == pcfg.current_model,
                })
        else:
            # 未配置的提供商，展示默认模型列表
            for m in _DEFAULT_MODELS_LIST.get(provider_name, []):
                provider_info["models"].append({
                    "model_name": m.model_name,
                    "display_name": m.display_name or m.model_name,
                    "is_default": m.is_default,
                })

        result.append(provider_info)

    # 标记当前激活的提供商和模型
    active = {
        "provider": config.current_provider.value,
        "model": config.current_model or "",
    }

    return {"providers": result, "active": active}


# ===================== Prompt 配置端点 =====================

from pydantic import BaseModel as PydanticBaseModel2


class PromptUpdateRequest(PydanticBaseModel2):
    system: Optional[str] = None
    template: Optional[str] = None


@router.get("/prompts", response_model=Dict[str, Any])
def get_all_prompts():
    """获取所有阶段的 prompt 模板（返回默认 + 自定义覆盖）"""
    from app.core.prompt_config import get_all_prompts
    return get_all_prompts()


@router.put("/prompts/{stage}")
def update_prompt(stage: str, req: PromptUpdateRequest):
    """更新指定阶段的 prompt 自定义模板"""
    from app.core.prompt_config import update_prompt
    try:
        update_prompt(stage, req.system, req.template)
        return {"status": "success", "stage": stage}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/prompts/{stage}")
def reset_prompt(stage: str):
    """重置指定阶段的 prompt 为默认"""
    from app.core.prompt_config import reset_prompt
    reset_prompt(stage)
    return {"status": "success", "stage": stage, "message": "已恢复默认"}


@router.get("/prompts/meta")
def get_prompt_meta():
    """获取所有 prompt 阶段的元信息（名称、描述、可用变量）"""
    return {
        "stages": [
            {
                "key": "brainstorm",
                "label": "头脑风暴 (Brainstorm)",
                "description": "根据用户意图生成 3 个可选剧情走向",
                "variables": ["chapter_num", "plan_context", "prev_summary", "user_intent"]
            },
            {
                "key": "plan",
                "label": "大纲规划 (Plan)",
                "description": "根据全书总纲和节奏控制生成章节分镜大纲",
                "variables": ["chapter_num", "opening_instruction", "world_context", "plan_context",
                              "pacing_instruction", "user_intent", "prev_summary", "hero_context", "npc_context"]
            },
            {
                "key": "write_scene",
                "label": "分镜写作 (Write Scene)",
                "description": "逐分镜生成正文内容（分镜模式）",
                "variables": ["style", "writer_persona", "hero_profile", "opening_guide",
                              "world_constraints", "feedback_instruction", "planned_title",
                              "outline", "scene_index", "total_scenes", "scene", "length_guide",
                              "hook_instruction"]
            },
            {
                "key": "write_direct",
                "label": "直出写作 (Write Direct)",
                "description": "根据大纲一次性生成完整章节（直出模式）",
                "variables": ["style", "writer_persona", "hero_profile", "opening_guide",
                              "world_constraints", "feedback_instruction", "planned_title",
                              "outline", "target_words", "hook_instruction"]
            },
            {
                "key": "review",
                "label": "审核评分 (Review)",
                "description": "审核正文质量并给出评分和修改建议",
                "variables": ["chapter_num", "outline", "style", "draft"]
            },
            {
                "key": "fact_check",
                "label": "事实核查 (Fact Check)",
                "description": "核查正文是否存在设定冲突或逻辑漏洞",
                "variables": ["hero_state", "power_system", "prev_summary", "chapter_num", "draft"]
            },
            {
                "key": "maintainer",
                "label": "状态维护 (Maintainer)",
                "description": "分析正文提取角色状态变更和新实体",
                "variables": ["current_tags_dict", "draft", "hero_name"]
            },
            {
                "key": "unified_review",
                "label": "统一审核 (Unified Review)",
                "description": "质量评分+事实核查+状态维护三合一（system 生效，template 由代码内联构建）",
                "variables": []
            },
            {
                "key": "reader_sim",
                "label": "读者模拟 (Reader Simulation)",
                "description": "模拟真实读者的追读意愿，并产出 ReaderState 增量（新谜团/情绪债务/信息差/钩子）",
                "variables": ["chapter_num", "reader_profile", "draft"]
            }
        ]
    }


_PROVIDER_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "openrouter": "OpenRouter",
    "anthropic": "Anthropic",
    "nvidia": "NVIDIA NIM",
    "custom": "自定义",
}

_PROVIDER_ICONS = {
    "deepseek": "🔥",
    "openai": "🤖",
    "openrouter": "🌐",
    "anthropic": "🧠",
    "nvidia": "💚",
    "custom": "⚙️",
}

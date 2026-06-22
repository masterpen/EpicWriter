from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class LLMProvider(str, Enum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    NVIDIA = "nvidia"
    CUSTOM = "custom"


class LLMConfig(BaseModel):
    provider: LLMProvider = LLMProvider.OPENAI
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096


class ModelOption(BaseModel):
    """单个模型选项，用户可自定义添加多个模型"""
    model_name: str  # 模型ID，如 deepseek-chat, gpt-4o
    display_name: str = ""  # 显示名称，如 DeepSeek-V3, GPT-4o
    is_default: bool = False  # 是否为该提供商的默认模型


class ProviderConfig(BaseModel):
    """单个提供商的完整配置，支持多个模型"""
    provider: LLMProvider
    api_key: str = ""
    base_url: str = ""
    models: List[ModelOption] = []  # 该提供商下可用的模型列表
    current_model: str = ""  # 当前使用的模型
    temperature: float = 0.7
    max_tokens: int = 4096
    enabled: bool = False  # 是否已启用（配置了 api_key）

    def get_effective_base_url(self) -> str:
        if self.base_url:
            return self.base_url
        return _DEFAULT_BASE_URLS.get(self.provider.value, "")

    def get_effective_model(self) -> str:
        if self.current_model:
            return self.current_model
        if self.models:
            default = next((m for m in self.models if m.is_default), self.models[0])
            return default.model_name
        return _DEFAULT_MODELS.get(self.provider.value, "gpt-4o")


_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "anthropic": "https://api.anthropic.com",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "custom": "",
}

_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "deepseek": "deepseek-chat",
    "openrouter": "anthropic/claude-3-sonnet",
    "anthropic": "claude-3-5-sonnet-20241022",
    "nvidia": "deepseek-ai/deepseek-v3_2",
    "custom": "gpt-4o",
}

_DEFAULT_MODELS_LIST = {
    "openai": [
        ModelOption(model_name="gpt-4o", display_name="GPT-4o", is_default=True),
        ModelOption(model_name="gpt-4o-mini", display_name="GPT-4o Mini"),
        ModelOption(model_name="gpt-4-turbo", display_name="GPT-4 Turbo"),
        ModelOption(model_name="o1", display_name="o1"),
    ],
    "deepseek": [
        ModelOption(model_name="deepseek-chat", display_name="DeepSeek-V3", is_default=True),
        ModelOption(model_name="deepseek-reasoner", display_name="DeepSeek-R1"),
    ],
    "openrouter": [
        ModelOption(model_name="anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet", is_default=True),
        ModelOption(model_name="openai/gpt-4o", display_name="GPT-4o"),
        ModelOption(model_name="google/gemini-pro-1.5", display_name="Gemini Pro 1.5"),
        ModelOption(model_name="meta-llama/llama-3.1-70b-instruct", display_name="Llama 3.1 70B"),
    ],
    "anthropic": [
        ModelOption(model_name="claude-3-5-sonnet-20241022", display_name="Claude 3.5 Sonnet", is_default=True),
        ModelOption(model_name="claude-3-opus-20240229", display_name="Claude 3 Opus"),
        ModelOption(model_name="claude-3-haiku-20240307", display_name="Claude 3 Haiku"),
    ],
    "nvidia": [
        ModelOption(model_name="deepseek-ai/deepseek-v3_2", display_name="DeepSeek-V3 (NIM)", is_default=True),
        ModelOption(model_name="deepseek-ai/deepseek-r1", display_name="DeepSeek-R1 (NIM)"),
        ModelOption(model_name="meta/llama-3.1-405b-instruct", display_name="Llama 3.1 405B (NIM)"),
        ModelOption(model_name="mistralai/mixtral-8x22b-instruct-v0.1", display_name="Mixtral 8x22B (NIM)"),
    ],
    "custom": [
        ModelOption(model_name="gpt-4o", display_name="Default", is_default=True),
    ],
}


class AgentLLMConfig(BaseModel):
    """用户的LLM配置 - 支持多提供商多模型"""
    current_provider: LLMProvider = LLMProvider.OPENAI
    current_model: str = ""  # 全局当前使用的模型（覆盖 provider 级别的 current_model）

    # 各提供商配置（包含多个模型选项）
    openai: Optional[ProviderConfig] = None
    deepseek: Optional[ProviderConfig] = None
    openrouter: Optional[ProviderConfig] = None
    anthropic: Optional[ProviderConfig] = None
    nvidia: Optional[ProviderConfig] = None
    custom: Optional[ProviderConfig] = None

    def get_provider_config(self, provider: LLMProvider) -> Optional[ProviderConfig]:
        return getattr(self, provider.value, None)

    def get_or_create_provider_config(self, provider: LLMProvider) -> ProviderConfig:
        cfg = self.get_provider_config(provider)
        if cfg is None:
            cfg = ProviderConfig(
                provider=provider,
                models=_DEFAULT_MODELS_LIST.get(provider.value, [ModelOption(model_name="gpt-4o", display_name="Default", is_default=True)]),
            )
            setattr(self, provider.value, cfg)
        return cfg

    def get_active_llm_config(self) -> LLMConfig:
        """获取当前生效的 LLMConfig（兼容旧接口）"""
        provider_cfg = self.get_provider_config(self.current_provider)
        if provider_cfg and provider_cfg.api_key:
            return LLMConfig(
                provider=self.current_provider,
                api_key=provider_cfg.api_key,
                base_url=provider_cfg.get_effective_base_url(),
                model=self.current_model or provider_cfg.get_effective_model(),
                temperature=provider_cfg.temperature,
                max_tokens=provider_cfg.max_tokens,
            )
        # 回退到环境变量 - 找第一个有 api_key 的提供商
        for fallback_provider in [LLMProvider.OPENAI, LLMProvider.DEEPSEEK, LLMProvider.OPENROUTER, LLMProvider.ANTHROPIC, LLMProvider.NVIDIA, LLMProvider.CUSTOM]:
            fallback_cfg = self.get_provider_config(fallback_provider)
            if fallback_cfg and fallback_cfg.api_key:
                return LLMConfig(
                    provider=fallback_provider,
                    api_key=fallback_cfg.api_key,
                    base_url=fallback_cfg.get_effective_base_url(),
                    model=fallback_cfg.get_effective_model(),
                    temperature=fallback_cfg.temperature,
                    max_tokens=fallback_cfg.max_tokens,
                )
        # 完全没有配置，返回空默认值
        return LLMConfig()


class AgentConfig(BaseModel):
    """Agent的完整配置"""
    llm: AgentLLMConfig = AgentLLMConfig()

    # 写作参数
    max_review_retries: int = 2
    min_approval_score: int = 85

    # 批处理配置
    batch_size: int = 5
    enable_auto_archive: bool = True
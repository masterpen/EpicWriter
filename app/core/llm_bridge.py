import os
import time
from typing import Optional
from openai import OpenAI, AsyncOpenAI
from app.core.agent_config import AgentLLMConfig, LLMConfig, LLMProvider, ProviderConfig, _DEFAULT_BASE_URLS, _DEFAULT_MODELS_LIST
from app.core.config import settings

class LLMBridge:
    """LLM 插件桥接器 - 支持多种 LLM 提供商 + 多模型 + 异步"""
    
    def __init__(self, config: Optional[AgentLLMConfig] = None):
        self.config = config or self._load_from_env()
        self._client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None
        self._db_loaded = False
    
    def _load_from_env(self) -> AgentLLMConfig:
        """从环境变量加载配置（向后兼容）- 自动选择有 API Key 的提供商"""
        deepseek_cfg = ProviderConfig(
            provider=LLMProvider.DEEPSEEK,
            api_key=settings.OPENAI_API_KEY or "",
            base_url=settings.OPENAI_BASE_URL or "https://api.deepseek.com",
            models=_DEFAULT_MODELS_LIST.get("deepseek", []),
            current_model="deepseek-chat",
            enabled=bool(settings.OPENAI_API_KEY),
        )
        openrouter_cfg = ProviderConfig(
            provider=LLMProvider.OPENROUTER,
            api_key=settings.OPENROUTER_API_KEY or "",
            base_url=settings.OPENROUTER_BASE_URL or "https://openrouter.ai/api/v1",
            models=_DEFAULT_MODELS_LIST.get("openrouter", []),
            current_model="anthropic/claude-3.5-sonnet",
            enabled=bool(settings.OPENROUTER_API_KEY),
        )
        nvidia_cfg = ProviderConfig(
            provider=LLMProvider.NVIDIA,
            api_key=settings.NVIDIA_API_KEY or "",
            base_url=settings.NVIDIA_BASE_URL or "https://integrate.api.nvidia.com/v1",
            models=_DEFAULT_MODELS_LIST.get("nvidia", []),
            current_model="deepseek-ai/deepseek-v3_2",
            enabled=bool(settings.NVIDIA_API_KEY),
        )
        # 智能选择默认提供商：优先有 key 的
        if settings.OPENAI_API_KEY:
            default_provider = LLMProvider.DEEPSEEK
            default_model = "deepseek-chat"
        elif settings.NVIDIA_API_KEY:
            default_provider = LLMProvider.NVIDIA
            default_model = "deepseek-ai/deepseek-v3_2"
        elif settings.OPENROUTER_API_KEY:
            default_provider = LLMProvider.OPENROUTER
            default_model = "anthropic/claude-3.5-sonnet"
        else:
            default_provider = LLMProvider.OPENAI
            default_model = "gpt-4o"
        
        return AgentLLMConfig(
            current_provider=default_provider,
            current_model=default_model,
            deepseek=deepseek_cfg,
            openrouter=openrouter_cfg,
            nvidia=nvidia_cfg,
        )
    
    def get_current_config(self) -> LLMConfig:
        """获取当前使用的 LLM 配置（自动尝试从DB恢复）"""
        if not self._db_loaded:
            self._try_load_from_db()
        return self.config.get_active_llm_config()
    
    def get_client(self) -> OpenAI:
        """获取同步 OpenAI 客户端（懒创建，配置变更时重建）"""
        if not self._db_loaded:
            self._try_load_from_db()
        if self._client is None:
            config = self.get_current_config()
            if not config.api_key:
                raise ValueError(f"当前提供商 {config.provider.value} 未配置 API Key，请先在设置页面配置。")
            self._client = OpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=180.0
            )
        return self._client
    
    def get_async_client(self) -> AsyncOpenAI:
        """获取异步 OpenAI 客户端（懒创建，配置变更时重建）"""
        if not self._db_loaded:
            self._try_load_from_db()
        if self._async_client is None:
            config = self.get_current_config()
            if not config.api_key:
                raise ValueError(f"当前提供商 {config.provider.value} 未配置 API Key，请先在设置页面配置。")
            self._async_client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                timeout=180.0
            )
        return self._async_client
    
    def _invalidate_clients(self):
        """配置变更时使客户端缓存失效"""
        self._client = None
        self._async_client = None
    
    def chat(self, messages: list, temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        """同步发送聊天请求"""
        config = self.get_current_config()
        response = self.get_client().chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=temperature or config.temperature,
            max_tokens=max_tokens or config.max_tokens
        )
        return response.choices[0].message.content
    
    async def achat(self, messages: list, temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        """异步发送聊天请求"""
        config = self.get_current_config()
        response = await self.get_async_client().chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=temperature or config.temperature,
            max_tokens=max_tokens or config.max_tokens
        )
        return response.choices[0].message.content
    
    def update_provider_config(self, provider: LLMProvider, provider_config: ProviderConfig):
        """更新指定提供商的配置"""
        setattr(self.config, provider.value, provider_config)
        self._invalidate_clients()
        self._save_to_db()
    
    def switch_provider(self, provider: LLMProvider, model: str = ""):
        """切换 LLM 提供商及模型"""
        self.config.current_provider = provider
        if model:
            self.config.current_model = model
            pcfg = self.config.get_provider_config(provider)
            if pcfg:
                pcfg.current_model = model
        self._invalidate_clients()
        self._save_to_db()
    
    def _save_to_db(self):
        """保存配置到数据库（持久化）"""
        try:
            from app.core.database import db
            db.set_system_config("llm_config", self.config.model_dump_json())
            self._db_loaded = True
        except Exception as e:
            from app.core.logger import logger
            logger.warning(f"保存LLM配置到数据库失败: {e}")
    
    def _try_load_from_db(self):
        """尝试从数据库加载配置（懒加载，最多重试3次）"""
        if self._db_loaded:
            return
        for attempt in range(3):
            try:
                from app.core.database import db
                stored = db.get_system_config("llm_config")
                if stored:
                    loaded_config = AgentLLMConfig.model_validate_json(stored)
                    self._merge_config(loaded_config)
                    self._invalidate_clients()
                    self._db_loaded = True
                    from app.core.logger import logger
                    logger.info(f"✅ 从数据库恢复LLM配置成功 (当前: {self.config.current_provider.value} / {self.config.current_model})")
                    return
            except Exception as e:
                from app.core.logger import logger
                logger.warning(f"从数据库加载LLM配置失败 (尝试 {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        self._db_loaded = True
    
    def _merge_config(self, db_config: AgentLLMConfig):
        """将DB配置合并到当前配置，保留环境变量中的key作为兜底"""
        self.config = db_config
        env_config = self._load_from_env()
        for provider_name in ['openai', 'deepseek', 'openrouter', 'anthropic', 'nvidia', 'custom']:
            if not getattr(self.config, provider_name, None):
                env_provider = getattr(env_config, provider_name, None)
                if env_provider and env_provider.api_key:
                    setattr(self.config, provider_name, env_provider)
    
    def load_from_db(self):
        """从数据库加载配置（显式调用接口）"""
        self._try_load_from_db()
        return self._db_loaded


# 全局实例
llm_bridge = LLMBridge()
try:
    llm_bridge._try_load_from_db()
except Exception as e:
    from app.core.logger import logger
    logger.warning(f"[LLMBridge] 初始化从数据库加载配置失败: {e}")

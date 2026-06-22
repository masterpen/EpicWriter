from openai import OpenAI
from app.core.llm_bridge import llm_bridge
from app.core.config import settings
import json


class BaseAgent:
    def __init__(self, role_prompt="", stage_key: str = None):
        self.role_prompt = role_prompt
        self.stage_key = stage_key  # e.g. "plan", "write_scene", "review"

    def _get_system_prompt(self, override_stage: str = None) -> str:
        """从 prompt_config 获取系统提示，优先自定义，兜底 role_prompt"""
        stage = override_stage or self.stage_key
        if stage:
            from app.core.prompt_config import get_prompt
            cfg = get_prompt(stage)
            return cfg.get("system") or self.role_prompt
        return self.role_prompt

    def call_with_tools(self, prompt, tools, tool_choice="auto", model=None, temperature=1):
        """
        使用 function calling 调用 LLM，返回解析后的结构化数据。
        reasoner 类模型不支持 tools，直接返回 None 让上层走 json_mode 兜底
        """
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        actual_model = model or config.model
        
        # reasoner 类模型不支持 tools，直接跳过
        if "reasoner" in actual_model.lower() or "r1" in actual_model.lower():
            from app.core.logger import logger
            logger.info(f"[LLM Tool] 模型 {actual_model} 不支持 func-call，直接走 json_mode 兜底")
            return None
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        # 函数调用只重试 1 次（超时 = 网关问题，不是瞬时故障）
        for attempt in range(2):
            try:
                client = llm_bridge.get_client()
                response = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                )
                msg = response.choices[0].message
                if msg.tool_calls and len(msg.tool_calls) > 0:
                    args_str = msg.tool_calls[0].function.arguments
                    return json.loads(args_str)
                # fallback: try to parse content as JSON
                if msg.content:
                    try:
                        return json.loads(msg.content.strip())
                    except:
                        return {"raw_content": msg.content}
                return None
            except Exception as e:
                from app.core.logger import logger
                logger.warning(f"[LLM Tool] func-call 失败 (尝试 {attempt+1}/2), 将回退 json_mode: {str(e)[:80]}")
                if attempt == 0:
                    import time
                    time.sleep(2)
        from app.core.logger import logger
        logger.info(f"[LLM Tool] func-call 全部失败，上层会走 json_mode 兜底")
        return None

    async def acall_with_tools(self, prompt, tools, tool_choice="auto", model=None, temperature=1):
        """异步版 function calling — reasoner 模型直接跳过，上层走 json_mode 兜底"""
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        actual_model = model or config.model
        
        if "reasoner" in actual_model.lower() or "r1" in actual_model.lower():
            from app.core.logger import logger
            logger.info(f"[LLM Tool] 模型 {actual_model} 不支持 func-call，直接走 json_mode 兜底")
            return None
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        for attempt in range(2):
            try:
                client = llm_bridge.get_async_client()
                response = await client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                )
                msg = response.choices[0].message
                if msg.tool_calls and len(msg.tool_calls) > 0:
                    args_str = msg.tool_calls[0].function.arguments
                    return json.loads(args_str)
                if msg.content:
                    try:
                        return json.loads(msg.content.strip())
                    except:
                        return {"raw_content": msg.content}
                return None
            except Exception as e:
                from app.core.logger import logger
                logger.warning(f"[LLM Tool] async func-call 失败 (尝试 {attempt+1}/2), 将回退 json_mode: {str(e)[:80]}")
                if attempt == 0:
                    import asyncio
                    await asyncio.sleep(2)
        from app.core.logger import logger
        logger.info(f"[LLM Tool] async func-call 全部失败，上层会走 json_mode 兜底")
        return None

    def _call_with_stage(self, prompt, stage_override: str, model=None, temperature=1, json_mode=True):
        """调用 LLM 但使用指定 stage 的 system prompt（用于 brainstorm 等需要不同 system 的场景）"""
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        actual_model = model or config.model
        messages = [
            {"role": "system", "content": self._get_system_prompt(stage_override)},
            {"role": "user", "content": prompt}
        ]
        kwargs = {"model": actual_model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            try:
                client = llm_bridge.get_client()
                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as e:
                from app.core.logger import logger
                logger.error(f"[LLM] model {actual_model} call failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    import time
                    time.sleep(1 * (attempt + 1))
        from app.core.logger import logger
        logger.error(f"[LLM] model {actual_model} 3 retries exhausted")
        return ""

    async def _acall_with_stage(self, prompt, stage_override: str, model=None, temperature=1, json_mode=True):
        """异步调用 LLM 但使用指定 stage 的 system prompt"""
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        actual_model = model or config.model
        messages = [
            {"role": "system", "content": self._get_system_prompt(stage_override)},
            {"role": "user", "content": prompt}
        ]
        kwargs = {"model": actual_model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            try:
                client = llm_bridge.get_async_client()
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as e:
                from app.core.logger import logger
                logger.error(f"[LLM] async model {actual_model} call failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))
        from app.core.logger import logger
        logger.error(f"[LLM] async model {actual_model} 3 retries exhausted")
        return ""

    def call(self, prompt, model=None, temperature=1, json_mode=True):
        """同步模型调用接口（向后兼容）"""
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        print(f"[BaseAgent] calling model: {config.model}, provider: {config.provider}")
        actual_model = model or config.model
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        kwargs = {"model": actual_model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            try:
                client = llm_bridge.get_client()
                response = client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                print(f"[BaseAgent] response length: {len(content)}")
                return content
            except Exception as e:
                from app.core.logger import logger
                logger.error(f"[LLM] model {actual_model} call failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    import time
                    time.sleep(1 * (attempt + 1))
        from app.core.logger import logger
        logger.error(f"[LLM] model {actual_model} 3 retries exhausted")
        return ""

    async def acall(self, prompt, model=None, temperature=1, json_mode=True):
        """异步模型调用接口（推荐，不阻塞事件循环）"""
        from app.core.llm_bridge import llm_bridge
        config = llm_bridge.get_current_config()
        print(f"[BaseAgent] async calling model: {config.model}, provider: {config.provider}")
        actual_model = model or config.model
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        kwargs = {"model": actual_model, "messages": messages, "temperature": temperature}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            try:
                client = llm_bridge.get_async_client()
                response = await client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                print(f"[BaseAgent] async response length: {len(content)}")
                return content
            except Exception as e:
                from app.core.logger import logger
                logger.error(f"[LLM] async model {actual_model} call failed (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(1 * (attempt + 1))
        from app.core.logger import logger
        logger.error(f"[LLM] async model {actual_model} 3 retries exhausted")
        return ""


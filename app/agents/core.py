import json
from app.agents.base import BaseAgent
from app.core.database import db
from app.core.logger import logger
from app.core.style_system import get_writer_persona, get_few_shot_examples, get_style_review_prompt
from app.core.json_utils import parse_llm_json, strip_code_fences
from app.core.reader_state import get_reader_state, default_reader_state, render_for_planner
import re
import copy
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

class PlannerAgent(BaseAgent):
    # 🟢 Function Calling 工具定义：章节大纲结构化输出（Suspense Engine 版）
    PLAN_TOOL = {
        "type": "function",
        "function": {
            "name": "output_chapter_plan",
            "description": "输出章节大纲：读者目标、角色欲望、两难选择、分镜列表、信息揭示、不可逆改变与章末钩子",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_title": {"type": "string", "description": "本章标题（双关/悬念感）"},
                    "reader_objective": {"type": "string", "description": "本章结束后，读者应该知道了什么、还想知道什么（阅读目标）"},
                    "character_goal": {"type": "string", "description": "本章主角的具体欲望目标（想得到/做到什么）"},
                    "dilemma": {"type": "string", "description": "主角面临的两难/危险选择"},
                    "choice_cost": {"type": "string", "description": "主角做出选择所付出的代价"},
                    "scenes": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "beat_type": {"type": "string", "description": "分镜类型，如：危机引入/智斗博弈/高潮爆发/盘点收获"},
                                "plot_summary": {"type": "string", "description": "详细剧情：主角做了什么，对手做了什么，结果如何（约100字）"},
                                "key_info_reveal": {"type": "string", "description": "本段核心信息量"},
                                "emotion_goal": {"type": "string", "description": "读者读完这段应有的情绪：压抑/爽快/细思极恐"}
                            },
                            "required": ["beat_type", "plot_summary", "key_info_reveal", "emotion_goal"]
                        }
                    },
                    "information_reveal": {"type": "string", "description": "本章揭示的核心信息，以及向谁揭示（读者/主角/双方）"},
                    "irreversible_change": {"type": "string", "description": "本章结束后不可逆的改变（拒绝一切照旧）"},
                    "chapter_hook": {"type": "string", "description": "章末钩子 = 新信息 + 风险/悬念 + 下一步行动方向"},
                    "pacing_note": {"type": "string", "description": "本章节奏说明（如何分配详略，哪里快哪里慢）"}
                },
                "required": ["chapter_title", "character_goal", "scenes", "chapter_hook", "pacing_note"]
            }
        }
    }

    def __init__(self):
        super().__init__("你是一个精通各类网文结构的剧情策划大师，擅长把握节奏、伏笔和高潮设计。", stage_key="plan")
    
    def generate_brainstorming_options(self, user_intent, chapter_num, book_id):
        """
        【新功能】灵感生成器
        不直接写大纲，而是先提供 3 个可选的剧情走向 (Option A/B/C)
        """
        print(f"\n🧠 [Planner] 正在进行头脑风暴 (Book: {book_id} | Chapter {chapter_num})...")
        
        # 1. 获取全书总纲
        book_plan = db.get_book_plan(book_id)
        
        plan_context = "无总纲，请自由发挥。"
        if book_plan:
            volumes = book_plan.get('volumes', [])
            # 🟢 FIX: 从 chapter_num 反推当前卷（不依赖 mutable current_volume 字段）
            computed_vol_idx = 0
            _acc = 0
            for _i, _v in enumerate(volumes):
                _vlen = _v.get('estimated_chapters', 50)
                if chapter_num <= _acc + _vlen:
                    computed_vol_idx = _i
                    break
                _acc += _vlen
            else:
                computed_vol_idx = len(volumes) - 1 if volumes else 0
            current_vol_info = "未知分卷"
            if 0 <= computed_vol_idx < len(volumes):
                vol = volumes[computed_vol_idx]
                current_vol_info = f"【当前卷：{vol['title']}】\n本卷目标：{vol['goal']}"
            
            plan_context = f"""
            【全书规划指南】
            主线梗概: {book_plan['main_story']}
            {current_vol_info}
            """

        # 2. 获取上一章摘要
        prev_summary = db.get_prev_chapter_summary(book_id, chapter_num)

        # 3. 使用 prompt_config 模板
        from app.core.prompt_config import get_prompt
        from app.core.prompt_renderer import render_prompt
        cfg = get_prompt("brainstorm")
        prompt = render_prompt(cfg.get("template", ""), {
            "chapter_num": str(chapter_num),
            "plan_context": plan_context,
            "prev_summary": prev_summary,
            "user_intent": user_intent,
        })
        
        # 调用 LLM (使用 brainstorm stage 的 system prompt)
        response = self._call_with_stage(prompt, stage_override="brainstorm", json_mode=True)
        
        # ---------------------------------------------------------
        # 🟢 修复后的鲁棒解析逻辑
        # ---------------------------------------------------------
        try:
            # 1. 如果底层已经转成了 List，直接返回
            if isinstance(response, list):
                return response
            
            # 2. 如果是 Dict (LLM 有时会包一层 {"data": [...]})
            if isinstance(response, dict):
                # 尝试找常见的 key
                for key in ["options", "plans", "ideas", "data"]:
                    if key in response and isinstance(response[key], list):
                        return response[key]
                # 如果没找到，可能整个 dict 就是其中一个选项？（不太可能，但为了防崩）
                return [response]

            # 3. 如果是字符串，用统一工具解析（提取数组）
            if isinstance(response, str):
                parsed = parse_llm_json(response, default=None, extract_array=True)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict) and "options" in parsed:
                    return parsed["options"]

        except Exception as e:
            print(f"❌ 灵感生成解析失败: {e} | 原始返回: {response}")
        
        # 🔴 兜底数据 (防止 UI 报错崩溃)
        return [
            {"option": "A", "title": "默认推进", "desc": "解析失败，请尝试重新生成或手动输入。", "impact": "无"},
            {"option": "B", "title": "重试方案", "desc": "AI 返回格式异常。", "impact": "无"},
            {"option": "C", "title": "备用方案", "desc": "请检查后台日志。", "impact": "无"}
        ]

    async def agenerate_brainstorming_options(self, user_intent, chapter_num, book_id):
        """异步版灵感生成器"""
        print(f"\n🧠 [Planner] 正在异步头脑风暴 (Book: {book_id} | Chapter {chapter_num})...")
        
        # 异步并行获取 DB 数据
        book_plan, prev_summary = await asyncio.gather(
            asyncio.to_thread(db.get_book_plan, book_id),
            asyncio.to_thread(db.get_prev_chapter_summary, book_id, chapter_num),
        )
        
        plan_context = "无总纲，请自由发挥。"
        if book_plan:
            volumes = book_plan.get('volumes', [])
            # 🟢 FIX: 从 chapter_num 反推当前卷（不依赖 mutable current_volume 字段）
            computed_vol_idx = 0
            _acc = 0
            for _i, _v in enumerate(volumes):
                _vlen = _v.get('estimated_chapters', 50)
                if chapter_num <= _acc + _vlen:
                    computed_vol_idx = _i
                    break
                _acc += _vlen
            else:
                computed_vol_idx = len(volumes) - 1 if volumes else 0
            current_vol_info = "未知分卷"
            if 0 <= computed_vol_idx < len(volumes):
                vol = volumes[computed_vol_idx]
                current_vol_info = f"【当前卷：{vol['title']}】\n本卷目标：{vol['goal']}"
            plan_context = f"""
            【全书规划指南】
            主线梗概: {book_plan['main_story']}
            {current_vol_info}
            """

        from app.core.prompt_config import get_prompt
        from app.core.prompt_renderer import render_prompt
        cfg = get_prompt("brainstorm")
        prompt = render_prompt(cfg.get("template", ""), {
            "chapter_num": str(chapter_num),
            "plan_context": plan_context,
            "prev_summary": prev_summary,
            "user_intent": user_intent,
        })
        
        response = await self._acall_with_stage(prompt, stage_override="brainstorm", json_mode=True)

        # LLM 调用失败（重试耗尽）会返回空字符串，此时应抛出明确异常而非返回假方案
        if not response or not response.strip():
            from app.core.llm_bridge import llm_bridge
            cfg = llm_bridge.get_current_config()
            raise RuntimeError(
                f"LLM 调用失败（模型 {cfg.model} / provider {cfg.provider.value}），"
                f"请检查 API Key、base_url 和模型名是否正确配置。"
            )

        try:
            if isinstance(response, list):
                return response
            if isinstance(response, dict):
                for key in ["options", "plans", "ideas", "data"]:
                    if key in response and isinstance(response[key], list):
                        return response[key]
                return [response]
            if isinstance(response, str):
                parsed = parse_llm_json(response, default=None, extract_array=True)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    # 支持 {"option_a": {...}, "option_b": {...}, ...} 格式
                    option_keys = [k for k in parsed if k.lower().startswith("option")]
                    if option_keys:
                        result = []
                        for k in sorted(option_keys):
                            val = parsed[k]
                            if isinstance(val, dict):
                                opt_label = k.replace("_", " ").replace("option", "").strip().upper() or "A"
                                val.setdefault("option", opt_label)
                                result.append(val)
                        if result:
                            return result
                    # 支持 {"options": [...]} 格式
                    if "options" in parsed:
                        return parsed["options"]
        except Exception as e:
            logger.warning(f"[Planner] 灵感生成解析失败: {e} | 原始返回(前200字): {str(response)[:200]}")

        # JSON 解析失败但 LLM 有返回内容，返回原始文本供用户参考
        raise RuntimeError(
            f"LLM 返回内容无法解析为 JSON 方案列表，请尝试切换模型或调整 prompt。"
            f"原始返回(前200字): {str(response)[:200]}"
        )
    def create_plan(self, user_intent, chapter_num, book_id):
        print(f"\n🔍 [Planner] 正在为书[{book_id}]读取设定...")
        
        # ===== 并行优化：7个DB查询并行执行 =====
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {
                executor.submit(db.get_world_config, book_id): "world_config",
                executor.submit(db.get_book_plan, book_id): "book_plan",
                executor.submit(db.get_hero_state, book_id): "hero_context",
                executor.submit(db.get_active_npcs, book_id): "npc_context",
                executor.submit(db.get_prev_chapter_summary, book_id, chapter_num): "prev_summary",
                executor.submit(db.get_volume_context, book_id, chapter_num, 5): "volume_context",
                executor.submit(get_reader_state, book_id): "reader_state",
            }
            db_results = {}
            for future in as_completed(futures):
                db_results[futures[future]] = future.result()

        world_config = db_results.get("world_config", {})
        book_plan = db_results.get("book_plan")
        hero_context = db_results.get("hero_context", "（未检测到主角数据）")
        npc_context = db_results.get("npc_context", "无活跃NPC")
        prev_summary = db_results.get("prev_summary", "无（这是第一章）")
        volume_context = db_results.get("volume_context", "")
        reader_state = db_results.get("reader_state") or default_reader_state()
        # ===== 并行优化结束 =====
        
        # =========================================================
        # 🟢 核心修改：计算“双重进度”
        # =========================================================
        # 默认值
        global_progress = 0.1
        local_progress = 0.1
        current_vol_boss = {"name": "未知麻烦", "identity": "路障"}
        is_volume_climax = False
        
        if book_plan and 'volumes' in book_plan:
            volumes = book_plan['volumes']
            
            # 1. 计算总章节数 (Global Limit)
            total_chapters = sum([v.get('estimated_chapters', 30) for v in volumes])
            if total_chapters == 0: total_chapters = 100
            
            # 2. 计算全局进度
            global_progress = min(chapter_num / total_chapters, 1.0)
            
            # 3. 定位当前分卷 & 计算卷内进度
            accumulated_chaps = 0
            for vol in volumes:
                vol_len = vol.get('estimated_chapters', 30)
                
                # 如果当前章节号 <= 累加章节 + 本卷长度，说明就在这一卷里
                if chapter_num <= accumulated_chaps + vol_len:
                    # 找到了当前卷
                    current_vol_boss = vol.get('antagonist', {"name": "本卷反派", "identity": "对手"})
                    
                    # 卷内相对章节号
                    local_chap = chapter_num - accumulated_chaps
                    local_progress = local_chap / vol_len
                    
                    # 判定是否是卷末高潮 (最后 10%)
                    if local_progress > 0.9:
                        is_volume_climax = True
                    break
                    
                accumulated_chaps += vol_len

        # =========================================================
        # 🟢 构建动态上下文 (导演指示)
        # =========================================================
        
        # 1. 全局反派指令 (基于 Global Progress)
        full_villain = world_config.get('villain', {})
        global_villain_instruction = ""
        
        if global_progress < 0.2:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**隐匿期**。严禁正面登场，仅可作为背景传说提及。"
        elif global_progress > 0.9:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**决战期**。所有剧情服务于最终对决。"
        else:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**活跃期**。可以通过手下或阴谋侧面干扰主角。"

        # 2. 分卷反派指令 (基于 Local Progress)
        volume_boss_instruction = ""
        
        if local_progress < 0.2:
            volume_boss_instruction = f"本卷反派【{current_vol_boss.get('name')}】({current_vol_boss.get('identity')}) 尚未完全暴露。主角可能刚接触到他的爪牙。"
        elif local_progress < 0.8:
            volume_boss_instruction = f"本卷反派【{current_vol_boss.get('name')}】与主角冲突升级。主角正在积蓄力量准备对抗他。"
        else:
            # 卷末高潮！
            volume_boss_instruction = f"🔥 **高潮警报**：本卷即将结束！主角必须与本卷BOSS【{current_vol_boss.get('name')}】进行最终决战（或关键博弈）。剧情要紧凑，不要水字数！"
        world_context = f"""
        【🌍 世界观核心设定】
        世界简介: {world_config.get('intro', '无')}
        力量体系: {world_config.get('power_system', '无')}
        
        【🎯 当前剧情阶段指示 (Planner Guide)】
        1. **全局进度**: {int(global_progress*100)}%
           - {global_villain_instruction}
           
        2. **本卷进度**: {int(local_progress*100)}% (卷内节奏)
           - {volume_boss_instruction}
        
        【🚫 策划红线】
        1. **战力封锁**: 严禁安排超出主角当前等级太多的敌人（除非剧情杀）。
        2. **节奏聚焦**: 如果处于本卷高潮期，严禁开启新的无关支线。
        """
        # ====================================================
        # 🆕 新增：开篇特化逻辑 (黄金三章引导)
        # ====================================================
        opening_instruction = ""
        
        if chapter_num == 1:
            opening_instruction = """
            【🚨 第 1 章特殊指令：切入点与代入感】
            这是小说的第一章，读者对这个世界一无所知。
            1. **禁止**直接开始复杂的战斗或高层博弈。
            2. **必须**通过主角的视角，自然地通过“五感”描写周围环境（赛博霓虹、修真灵气等），引出世界观背景。
            3. **必须**交代主角当前的窘境/身份/生活状态（如：贫民窟的黑客、废柴外门弟子）。
            4. **核心事件**：设计一个具体的“金手指觉醒”或“突发危机”作为切入点。
            """
        elif chapter_num == 2:
            opening_instruction = """
            【🚨 第 2 章特殊指令：冲突升级与世界观铺陈】
            1. 承接第一章的变故，展示主角如何应对。
            2. 借由配角（反派路人或导师）的口，侧面透露出这个世界的力量体系的一角。
            3. 制造第一个小高潮/打脸情节的铺垫。
            """
        elif chapter_num == 3:
            opening_instruction = """
            【🚨 第 3 章特殊指令：初次收获与主线开启】
            1. 完成第一个小事件的解决。
            2. 主角获得第一次实质性的提升（获得装备、功法突破）。
            3. 结尾必须引出长线目标（如：为了救人、复仇或变强而决定离开新手村）。
            """
        # ----------------------------------------------------
        # 2. 读取全书总纲 & 计算节奏 (复用前面已查询的 book_plan)
        # ----------------------------------------------------
        plan_context = ""
        pacing_instruction = "当前无特定节奏要求，请根据前情提要自然推进剧情。" # 默认值
        
        if book_plan:
            # --- A. 基础信息 ---
            volumes = book_plan.get('volumes', [])
            main_story = book_plan.get('main_story', '主角的成长故事')
            # 🟢 FIX: 从 chapter_num 反推当前卷索引（不再依赖 mutable current_volume 字段）
            current_vol_idx = 0
            _acc_chaps = 0
            for _i, _v in enumerate(volumes):
                _vlen = _v.get('estimated_chapters', 50)
                if chapter_num <= _acc_chaps + _vlen:
                    current_vol_idx = _i
                    break
                _acc_chaps += _vlen
            else:
                current_vol_idx = len(volumes) - 1 if volumes else 0
            
            vol_goal = "无"
            current_vol_config = {}
            if 0 <= current_vol_idx < len(volumes):
                current_vol_config = volumes[current_vol_idx]
                vol_goal = current_vol_config.get('goal', '无')

            plan_context = f"""
            【剧情宏观导航】
            全书主线: {main_story}
            当前分卷目标: {vol_goal} (请确保本章剧情不偏离此目标)
            """

           # --- B. 节奏计算 (Pacing) ---
            if current_vol_config:
                target_len = current_vol_config.get('estimated_chapters', 50)
                
                # 1. 计算 Offset (前几卷的总章数)
                start_offset = 0
                for i in range(current_vol_idx):
                    start_offset += volumes[i].get('estimated_chapters', 50)
                
                # 2. 计算本卷内的相对章节号
                local_chapter_num = max(1, chapter_num - start_offset)
                
                # 3. 计算进度百分比
                progress = min(local_chapter_num / target_len, 1.0)
                
                # 🟢 动态计算“收尾缓冲区”长度
                # 逻辑：如果本卷很短(<10章)，只留1章收尾；如果是长卷，留3章收尾
                end_buffer = 1 if target_len < 10 else 3
                
                # ====================================================
                # 4. 生成指令 (逻辑分层：开局 -> 溢出 -> 收尾 -> 中间)
                # ====================================================
                
                # (a) 新卷开局 (绝对优先级：第1章)
                if local_chapter_num == 1:
                    prev_vol_name = volumes[current_vol_idx-1]['title'] if current_vol_idx > 0 else "序章"
                    
                    # 🟢 修复点：这里原来是 curr_vol['title']，改成 current_vol_config['title']
                    current_title = current_vol_config.get('title', '新卷')
                    
                    # 🟢 加载上一卷的收尾摘要（Maintainer 在卷末存储的）
                    vol_conclusion_text = ""
                    try:
                        prev_vol_end_chap = chapter_num - 1
                        conclusion = db.get_system_config(f"volume_conclusion_{prev_vol_end_chap}")
                        if conclusion:
                            vol_conclusion_text = f"\n【📋 上一卷收尾摘要 (由归档系统自动生成)】\n{conclusion}\n\n⚠️ 请基于以上收尾摘要，确保本章与前卷自然衔接，不要遗漏未解决的伏笔。"
                    except Exception as e:
                        logger.warning(f"[Planner] 加载上一卷收尾摘要失败 (chap={chapter_num}): {e}")
                    
                    pacing_instruction = f"""
                    【🚀 新卷开启：{current_title} - 第 1 章】
                    ⚠️ **切断旧节奏**：读者刚从上一卷【{prev_vol_name}】的高潮中走出来，需要新鲜感。
                    {vol_conclusion_text}
                    
                    ✅ **本章核心任务**：
                    1. **环境断裂感**：必须明确描写主角已处于新的环境/地图/时间点（与上一卷做出区分）。
                    2. **新悬念引入**：抛出本卷的核心谜题或目标【{current_vol_config['goal']}】的引子。
                    3. **衔接先端**：根据上文收尾摘要，承接近期剧情，不要丢失未解决的关键伏笔。
                    
                    🚫 **禁止**：继续描写上一卷的战斗细节或过度回忆旧人（除非是伏笔）。
                    """
                
                # (b) 溢出处理 (篇幅超标)
                elif local_chapter_num > target_len:
                    over_count = local_chapter_num - target_len
                    
                    # 🔴 自动切卷逻辑 (如果你想让 AI 自动切卷，请取消下面 3 行的注释)
                    if over_count >= 2 and (current_vol_idx + 1 < len(volumes)):
                        print(f"🔄 [Planner] 溢出过多，自动切换下一卷...")
                        db.update_book_plan_field(book_id, "current_volume", current_vol_idx + 2)
                    
                    pacing_instruction = f"""
                    【🏁 分卷收尾/过渡期 - 溢出第 {over_count} 章】
                    ⚠️ **强制刹车**：本卷剧情必须在此处彻底终结，不要再开新支线！
                    
                    ✅ **本章核心任务**：
                    1. **结算**：主角清点收获（宝物、经验、情报），平复心情。
                    2. **告别**：与本卷的配角暂别（或处理掉反派）。
                    3. **启程**：结尾必须落在“主角决定前往下一个目的地”或“时间飞逝”的节点上。
                    
                    💡 **给 Writer 的暗示**：使用由动转静的笔法，营造沧桑感或期待感。
                    """

                # (c) 收尾阶段 (根据动态 Buffer 判断)
                # 例如：总长4章，Buffer为1，则 >= 4+1-1=4 (即第4章) 进入收尾
                elif local_chapter_num >= (target_len - end_buffer + 1):
                    next_title = "未知"
                    if current_vol_idx + 1 < len(volumes):
                        next_title = volumes[current_vol_idx+1].get('title', '下一卷')
                        
                    pacing_instruction = f"""
                    【当前分卷进度：{local_chapter_num}/{target_len} 章 - 🔥 收尾/高潮阶段】
                    本卷即将结束。
                    ✅ 重点任务：完成本卷最高潮的剧情，清理战场，为下一卷【{next_title}】埋下伏笔。
                    """

                # (d) 铺垫期 (进度 < 15%)
                elif progress < 0.15:
                    pacing_instruction = f"""
                    【当前分卷进度：{local_chapter_num}/{target_len} 章 - 🟢 铺垫/发展期】
                    ⚠️ 严禁快速推进核心冲突。
                    ✅ 重点任务：通过小事件展示世界观，引入本卷新人物，确立本卷目标。
                    """
                
                # (e) 中间发展期 (剩下的都是中间)
                else:
                    # 简单二分：前半段发展，后半段高潮酝酿
                    if progress < 0.7:
                        pacing_instruction = f"""
                        【当前分卷进度：{local_chapter_num}/{target_len} 章 - 发展期】
                        ✅ 重点任务：制造障碍，让主角在解决小困难中积蓄力量，不要直接达成最终目标。
                        """
                    else:
                        pacing_instruction = f"""
                        【当前分卷进度：{local_chapter_num}/{target_len} 章 - 高潮酝酿期】
                        ✅ 重点任务：矛盾激化，反派或核心危机浮出水面，准备迎接决战。
                        """

        # 3/4/5. hero_context, npc_context, prev_summary 已在开头并行查询获得
        
        print(opening_instruction)

        # ----------------------------------------------------
        # 5.5 渲染读者认知状态指令块 (Suspense Engine 核心)
        # ----------------------------------------------------
        reader_block = render_for_planner(reader_state, chapter_num)

        # ----------------------------------------------------
        # 6. 组装 Prompt (保持不变)
        # ----------------------------------------------------
        prompt = f"""
        任务：设计第 {chapter_num} 章的【分镜大纲】。

        {opening_instruction}

        【世界观设定】
        {world_context}

        【全书总纲】
        {plan_context}

        >>> ⚡ 节奏控制指令 (必须严格执行) <<<
        {pacing_instruction}

        {reader_block}

        【用户意图 (最高优先级)】
        {user_intent}
        
        【前情提要】
        {prev_summary}
        
        【📚 近期剧情回溯 (确保跨卷衔接)】
        {volume_context}
        
        # ----------------------------------------------------
        # 🌍 世界背景信息 (仅供逻辑参考，非强制出场)
        # ----------------------------------------------------
        【主角当前档案】
        {hero_context}
        
        【关键人物动态监控】
        {npc_context}
        # ----------------------------------------------------
        
        要求：
        1. 风格必须符合【世界观核心设定】。
        2. 剧情发展必须服务于【剧情宏观导航】中的分卷目标。
        3. 必须紧接“前情提要”的结尾。
        
        4. ⚠️【资源调用原则】：
           - 上述【主角档案】和【关键人物动态】仅代表客观存在的事实。
           - **如果【用户意图】是独处、修炼或日常过渡，请忽略所有NPC，不要强行安排他们出场。**
           - **如果场景不需要战斗或解谜，不要强行使用道具。**
           - 只有当剧情逻辑确实需要（如遭遇强敌、需要特定物品解围）时，才调用上述数据。
        
        # ----------------------------------------------------
        # ⚠️ 核心指令：关于信息密度的强制要求
        # ----------------------------------------------------
        你必须把本章 4000 字的篇幅切分为 3-4 个【关键节拍 (Beats)】。
        每一个分镜（Beat）必须包含以下“干货”，拒绝纯粹的过渡：
        1. 【冲突/事件】：必须发生剧情推动的交互（战斗、博弈、发现、突破），不能只有心理活动。
        2. 【爽点/情绪】：本段必须包含一个情绪高点（震惊、期待、宣泄、疑惑）。
        
        # ----------------------------------------------------

        【输出格式要求 (JSON Only)】
        请严格返回以下 JSON 格式，不要包含 Markdown 代码块标记：
        {{
            "chapter_title": "本章标题 (双关/悬念感)",
            "reader_objective": "本章结束后，读者应该知道了什么、还想知道什么（阅读目标）",
            "character_goal": "本章主角的具体欲望目标（他想得到/做到什么）",
            "dilemma": "主角面临的两难/危险选择",
            "choice_cost": "主角做出选择所付出的代价",
            "scenes": [
                {{
                    "beat_type": "类型 (如：危机引入 / 智斗博弈 / 高潮爆发 / 盘点收获)",
                    "plot_summary": "详细剧情：主角做了什么，对手做了什么，结果如何 (约 100 字)",
                    "key_info_reveal": "本段核心信息量：(例如：发现遗迹是活体生物 / 获得道具[X] / 揭示反派是某人的父亲)",
                    "emotion_goal": "读者读完这段应有的情绪：(如：压抑、爽快、细思极恐)"
                }},
                {{
                     // 分镜 2 ...
                }},
                {{
                     // 分镜 3 ...
                }}
            ],
            "information_reveal": "本章揭示的核心信息，以及向谁揭示（读者/主角/双方）",
            "irreversible_change": "本章结束后不可逆的改变（拒绝一切照旧）",
            "chapter_hook": "章末钩子 = 新信息 + 风险/悬念 + 下一步行动方向",
            "pacing_note": "本章节奏说明 (如何分配详略，哪里快哪里慢)"
        }}
        """
        
        # ----------------------------------------------------
        # 🟢 使用 Function Calling 获取结构化大纲
        # ----------------------------------------------------
        result = self.call_with_tools(
            prompt,
            tools=[self.PLAN_TOOL],
            tool_choice="required",
        )
        
        if result and isinstance(result, dict) and "scenes" in result:
            return result
        
        # 兜底
        raw_response = self.call(prompt, json_mode=True)
        if isinstance(raw_response, str):
            default = {"chapter_title": f"第{chapter_num}章", "scenes": [raw_response], "pacing_note": "解析失败兜底"}
            result = parse_llm_json(raw_response, default=None)
            if result is None:
                print(f"❌ [Planner] JSON 解析失败，返回原始内容")
                return default
            return result
        return raw_response if isinstance(raw_response, dict) else {"chapter_title": f"第{chapter_num}章", "scenes": ["生成失败"], "pacing_note": "兜底"}

    async def acreate_plan(self, user_intent, chapter_num, book_id):
        """异步版 create_plan：DB 查询并行 + LLM 调用异步"""
        print(f"\n🔍 [Planner] 正在为书[{book_id}]读取设定 (异步)...")
        
        # ===== 异步并行：7个DB查询 =====
        db_results = {}
        tasks = {
            "world_config": asyncio.to_thread(db.get_world_config, book_id),
            "book_plan": asyncio.to_thread(db.get_book_plan, book_id),
            "hero_context": asyncio.to_thread(db.get_hero_state, book_id),
            "npc_context": asyncio.to_thread(db.get_active_npcs, book_id),
            "prev_summary": asyncio.to_thread(db.get_prev_chapter_summary, book_id, chapter_num),
            "volume_context": asyncio.to_thread(db.get_volume_context, book_id, chapter_num, 5),
            "reader_state": asyncio.to_thread(get_reader_state, book_id),
        }
        results = await asyncio.gather(*tasks.values())
        for key, result in zip(tasks.keys(), results):
            db_results[key] = result

        # 以下逻辑与 create_plan 完全相同，但使用 acall 替代 call
        world_config = db_results.get("world_config", {})
        book_plan = db_results.get("book_plan")
        hero_context = db_results.get("hero_context", "（未检测到主角数据）")
        npc_context = db_results.get("npc_context", "无活跃NPC")
        prev_summary = db_results.get("prev_summary", "无（这是第一章）")
        volume_context = db_results.get("volume_context", "")
        reader_state = db_results.get("reader_state") or default_reader_state()
        
        # 计算进度（复用逻辑）
        global_progress = 0.1
        local_progress = 0.1
        current_vol_boss = {"name": "未知麻烦", "identity": "路障"}
        is_volume_climax = False
        
        if book_plan and 'volumes' in book_plan:
            volumes = book_plan['volumes']
            total_chapters = sum([v.get('estimated_chapters', 30) for v in volumes])
            if total_chapters == 0: total_chapters = 100
            global_progress = min(chapter_num / total_chapters, 1.0)
            
            accumulated_chaps = 0
            for vol in volumes:
                vol_len = vol.get('estimated_chapters', 30)
                if chapter_num <= accumulated_chaps + vol_len:
                    current_vol_boss = vol.get('antagonist', {"name": "本卷反派", "identity": "对手"})
                    local_chap = chapter_num - accumulated_chaps
                    local_progress = local_chap / vol_len
                    if local_progress > 0.9:
                        is_volume_climax = True
                    break
                accumulated_chaps += vol_len

        # 反派指令
        full_villain = world_config.get('villain', {})
        global_villain_instruction = ""
        if global_progress < 0.2:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**隐匿期**。严禁正面登场，仅可作为背景传说提及。"
        elif global_progress > 0.9:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**决战期**。所有剧情服务于最终对决。"
        else:
            global_villain_instruction = f"全书最终反派【{full_villain.get('name')}】处于**活跃期**。可以通过手下或阴谋侧面干扰主角。"

        volume_boss_instruction = ""
        if local_progress < 0.2:
            volume_boss_instruction = f"本卷反派【{current_vol_boss.get('name')}】({current_vol_boss.get('identity')}) 尚未完全暴露。主角可能刚接触到他的爪牙。"
        elif local_progress < 0.8:
            volume_boss_instruction = f"本卷反派【{current_vol_boss.get('name')}】与主角冲突升级。主角正在积蓄力量准备对抗他。"
        else:
            volume_boss_instruction = f"🔥 **高潮警报**：本卷即将结束！主角必须与本卷BOSS【{current_vol_boss.get('name')}】进行最终决战（或关键博弈）。剧情要紧凑，不要水字数！"
        
        world_context = f"""
        【🌍 世界观核心设定】
        世界简介: {world_config.get('intro', '无')}
        力量体系: {world_config.get('power_system', '无')}
        
        【🎯 当前剧情阶段指示 (Planner Guide)】
        1. **全局进度**: {int(global_progress*100)}%
           - {global_villain_instruction}
           
        2. **本卷进度**: {int(local_progress*100)}% (卷内节奏)
           - {volume_boss_instruction}
        
        【🚫 策划红线】
        1. **战力封锁**: 严禁安排超出主角当前等级太多的敌人（除非剧情杀）。
        2. **节奏聚焦**: 如果处于本卷高潮期，严禁开启新的无关支线。
        """
        
        opening_instruction = ""
        if chapter_num == 1:
            opening_instruction = """
            【🚨 第 1 章特殊指令：切入点与代入感】
            这是小说的第一章，读者对这个世界一无所知。
            1. **禁止**直接开始复杂的战斗或高层博弈。
            2. **必须**通过主角的视角，自然地通过"五感"描写周围环境（赛博霓虹、修真灵气等），引出世界观背景。
            3. **必须**交代主角当前的窘境/身份/生活状态（如：贫民窟的黑客、废柴外门弟子）。
            4. **核心事件**：设计一个具体的"金手指觉醒"或"突发危机"作为切入点。
            """
        elif chapter_num == 2:
            opening_instruction = """
            【🚨 第 2 章特殊指令：冲突升级与世界观铺陈】
            1. 承接第一章的变故，展示主角如何应对。
            2. 借由配角（反派路人或导师）的口，侧面透露出这个世界的力量体系的一角。
            3. 制造第一个小高潮/打脸情节的铺垫。
            """
        elif chapter_num == 3:
            opening_instruction = """
            【🚨 第 3 章特殊指令：初次收获与主线开启】
            1. 完成第一个小事件的解决。
            2. 主角获得第一次实质性的提升（获得装备、功法突破）。
            3. 结尾必须引出长线目标（如：为了救人、复仇或变强而决定离开新手村）。
            """
        
        plan_context = ""
        pacing_instruction = "当前无特定节奏要求，请根据前情提要自然推进剧情。"
        
        if book_plan:
            volumes = book_plan.get('volumes', [])
            main_story = book_plan.get('main_story', '主角的成长故事')
            # 🟢 FIX: 从 chapter_num 反推当前卷索引（不再依赖 mutable current_volume 字段）
            current_vol_idx = 0
            _acc_chaps = 0
            for _i, _v in enumerate(volumes):
                _vlen = _v.get('estimated_chapters', 50)
                if chapter_num <= _acc_chaps + _vlen:
                    current_vol_idx = _i
                    break
                _acc_chaps += _vlen
            else:
                current_vol_idx = len(volumes) - 1 if volumes else 0
            
            vol_goal = "无"
            current_vol_config = {}
            if 0 <= current_vol_idx < len(volumes):
                current_vol_config = volumes[current_vol_idx]
                vol_goal = current_vol_config.get('goal', '无')

            plan_context = f"""
            【剧情宏观导航】
            全书主线: {main_story}
            当前分卷目标: {vol_goal} (请确保本章剧情不偏离此目标)
            """

            if current_vol_config:
                target_len = current_vol_config.get('estimated_chapters', 50)
                start_offset = 0
                for i in range(current_vol_idx):
                    start_offset += volumes[i].get('estimated_chapters', 50)
                
                local_chapter_num = max(1, chapter_num - start_offset)
                progress = min(local_chapter_num / target_len, 1.0)
                end_buffer = 1 if target_len < 10 else 3
                
                if local_chapter_num == 1:
                    prev_vol_name = volumes[current_vol_idx-1]['title'] if current_vol_idx > 0 else "序章"
                    current_title = current_vol_config.get('title', '新卷')
                    
                    # 🟢 加载上一卷的收尾摘要（Maintainer 在卷末存储的）
                    vol_conclusion_text = ""
                    try:
                        prev_vol_end_chap = chapter_num - 1
                        conclusion = db.get_system_config(f"volume_conclusion_{prev_vol_end_chap}")
                        if conclusion:
                            vol_conclusion_text = f"\n【📋 上一卷收尾摘要 (由归档系统自动生成)】\n{conclusion}\n\n⚠️ 请基于以上收尾摘要，确保本章与前卷自然衔接，不要遗漏未解决的伏笔。"
                    except Exception as e:
                        logger.warning(f"[Planner] 加载上一卷收尾摘要失败 (chap={chapter_num}): {e}")
                    
                    pacing_instruction = f"""
                    【🚀 新卷开启：{current_title} - 第 1 章】
                    ⚠️ **切断旧节奏**：读者刚从上一卷【{prev_vol_name}】的高潮中走出来，需要新鲜感。
                    {vol_conclusion_text}
                    ✅ **本章核心任务**：
                    1. **环境断裂感**：必须明确描写主角已处于新的环境/地图/时间点。
                    2. **新悬念引入**：抛出本卷的核心谜题或目标【{current_vol_config['goal']}】的引子。
                    3. **衔接先端**：根据上文收尾摘要，承接近期剧情，不要丢失未解决的关键伏笔。
                    🚫 **禁止**：继续描写上一卷的战斗细节或过度回忆旧人。
                    """
                elif local_chapter_num > target_len:
                    over_count = local_chapter_num - target_len
                    if over_count >= 2 and (current_vol_idx + 1 < len(volumes)):
                        print(f"🔄 [Planner] 溢出过多，自动切换下一卷...")
                        db.update_book_plan_field(book_id, "current_volume", current_vol_idx + 2)
                    pacing_instruction = f"""
                    【🏁 分卷收尾/过渡期 - 溢出第 {over_count} 章】
                    ⚠️ **强制刹车**：本卷剧情必须在此处彻底终结，不要再开新支线！
                    ✅ **本章核心任务**：
                    1. **结算**：主角清点收获，平复心情。
                    2. **告别**：与本卷的配角暂别。
                    3. **启程**：结尾必须落在"主角决定前往下一个目的地"的节点上。
                    """
                elif local_chapter_num >= (target_len - end_buffer + 1):
                    next_title = "未知"
                    if current_vol_idx + 1 < len(volumes):
                        next_title = volumes[current_vol_idx+1].get('title', '下一卷')
                    pacing_instruction = f"""
                    【当前分卷进度：{local_chapter_num}/{target_len} 章 - 🔥 收尾/高潮阶段】
                    ✅ 重点任务：完成本卷最高潮的剧情，清理战场，为下一卷【{next_title}】埋下伏笔。
                    """
                elif progress < 0.15:
                    pacing_instruction = f"""
                    【当前分卷进度：{local_chapter_num}/{target_len} 章 - 🟢 铺垫/发展期】
                    ⚠️ 严禁快速推进核心冲突。
                    ✅ 重点任务：通过小事件展示世界观，引入本卷新人物，确立本卷目标。
                    """
                else:
                    if progress < 0.7:
                        pacing_instruction = f"""
                        【当前分卷进度：{local_chapter_num}/{target_len} 章 - 发展期】
                        ✅ 重点任务：制造障碍，让主角在解决小困难中积蓄力量。
                        """
                    else:
                        pacing_instruction = f"""
                        【当前分卷进度：{local_chapter_num}/{target_len} 章 - 高潮酝酿期】
                        ✅ 重点任务：矛盾激化，反派或核心危机浮出水面，准备迎接决战。
                        """

        print(opening_instruction)

        # 读者认知状态指令块 (Suspense Engine 核心)
        reader_block = render_for_planner(reader_state, chapter_num)

        prompt = f"""
        任务：设计第 {chapter_num} 章的【分镜大纲】。

        {opening_instruction}

        【世界观设定】
        {world_context}

        【全书总纲】
        {plan_context}

        >>> ⚡ 节奏控制指令 (必须严格执行) <<<
        {pacing_instruction}

        {reader_block}

        【用户意图 (最高优先级)】
        {user_intent}
        
        【前情提要】
        {prev_summary}
        
        【📚 近期剧情回溯 (确保跨卷衔接)】
        {volume_context}
        
        【主角当前档案】
        {hero_context}
        
        【关键人物动态监控】
        {npc_context}
        
        要求：
        1. 风格必须符合【世界观核心设定】。
        2. 剧情发展必须服务于【剧情宏观导航】中的分卷目标。
        3. 必须紧接"前情提要"的结尾。
        4. ⚠️【资源调用原则】：如果【用户意图】是独处、修炼或日常过渡，请忽略所有NPC，不要强行安排他们出场。
        
        你必须把本章 4000 字的篇幅切分为 3-4 个【关键节拍 (Beats)】。
        每一个分镜必须包含以下"干货"：
        1. 【冲突/事件】：必须发生剧情推动的交互。
        2. 【爽点/情绪】：本段必须包含一个情绪高点。

        【输出格式要求 (JSON Only)】
        请严格返回以下 JSON 格式，不要包含 Markdown 代码块标记：
        {{
            "chapter_title": "本章标题 (双关/悬念感)",
            "reader_objective": "本章结束后，读者应该知道了什么、还想知道什么（阅读目标）",
            "character_goal": "本章主角的具体欲望目标（他想得到/做到什么）",
            "dilemma": "主角面临的两难/危险选择",
            "choice_cost": "主角做出选择所付出的代价",
            "scenes": [
                {{
                    "beat_type": "类型",
                    "plot_summary": "详细剧情 (约 100 字)",
                    "key_info_reveal": "本段核心信息量",
                    "emotion_goal": "读者读完这段应有的情绪"
                }}
            ],
            "information_reveal": "本章揭示的核心信息，以及向谁揭示（读者/主角/双方）",
            "irreversible_change": "本章结束后不可逆的改变（拒绝一切照旧）",
            "chapter_hook": "章末钩子 = 新信息 + 风险/悬念 + 下一步行动方向",
            "pacing_note": "本章节奏说明"
        }}
        """
        
        # 🟢 使用 Function Calling 获取结构化大纲（替代 json_mode）
        result = await self.acall_with_tools(
            prompt,
            tools=[self.PLAN_TOOL],
            tool_choice={"type": "function", "function": {"name": "output_chapter_plan"}},
        )
        
        if result and isinstance(result, dict) and "scenes" in result:
            return result
        
        # 兜底：function calling 失败时用旧版 json_mode + 正则解析
        raw_response = await self.acall(prompt, json_mode=True)
        if isinstance(raw_response, str):
            default = {"chapter_title": f"第{chapter_num}章", "scenes": [raw_response], "pacing_note": "解析失败兜底"}
            result = parse_llm_json(raw_response, default=default)
            return result if result is not None else default
        return raw_response if isinstance(raw_response, dict) else {"chapter_title": f"第{chapter_num}章", "scenes": ["生成失败"], "pacing_note": "兜底"}




class WriterAgent(BaseAgent):
    def __init__(self):
        # 初始化时不写死风格，只给最基础的能力定义
        super().__init__("你是一个擅长各种风格的网文生成引擎，能够精准执行大纲要求。", stage_key="write_scene")
        
        # ==================================================================
        # 🎭 五维风格系统 (Five-Dimension Style System)
        # 已迁移到 app.core.style_system 模块
        # 旧 STYLE_CONFIGS 保留为 fallback，当风格卡不存在时使用
        # ==================================================================
        self.STYLE_CONFIGS = {
            "男频-热血玄幻": """
            【文风基调】暴烈、直球、极致的压迫与反弹。
            【剧情推进引擎】
            1. **危机前置**：不要先写"风和日丽"，要先写"杀气逼近"。环境描写只服务于"危险预警"（如：鸟兽惊散、空气凝固）。
            2. **破坏性反馈**：不用形容词堆砌招式威力，用环境的"物理损坏"来结算伤害（如：余波震碎了百米外的石碑）。
            【拒绝水文-执行标准】
            1. **去形容词化**：少用"惊天动地"，多用动词。
            2. **三句一转折**：如果连续三句话都在平铺直叙，第四句必须出现变故（敌人偷袭/宝物出世）。
            """,
            "男频-诡秘智斗": """
            【文风基调】信息碎片化、逻辑闭环、每句话都是线索。
            【剧情推进引擎】
            1. **线索式描写**：不描写房间布局，只描写"违和感"（如：满屋灰尘，唯独茶杯把手是干净的）。所有描写必须是后续推理的伏笔。
            2. **信息差博弈**：描写重点放在"我预判了你的预判"。环境是博弈的棋盘，不是风景。
            【拒绝水文-执行标准】
            1. **无效信息剔除**：如果这个花瓶后来没被打破也没藏钥匙，就不要写它。
            2. **高频反转**：每1000字至少推翻一次之前的推论。
            """,
            "男频-稳健苟道": """
            【文风基调】风险评估报告式叙事、被迫害妄想症。
            【剧情推进引擎】
            1. **扫描式观测**：主角眼里的环境="致死率热力图"。不写风景美不美，只写哪里适合埋伏、哪里适合跑路。
            2. **过度准备**：通过描写主角繁琐的准备工作（布阵、试毒）来体现人物性格，这是读者的爽点（看他把简单难度玩成地狱难度）。
            【拒绝水文-执行标准】
            1. **内心戏代替废话**：少写对话，多写主角内心的风险计算过程。
            2. **反套路**：看似要发生大事，最后因为主角太稳而无事发生（反差笑点）。
            """,
            "男频-无敌碾压": """
            【文风基调】极简主义出手、极繁主义侧写。
            【剧情推进引擎】
            1. **他人视角**：战斗过程不要写主角怎么出拳（太简单了），要写反派从"嚣张"到"恐惧"的微表情变化，以及围观群众的"世界观崩塌"。
            2. **战力单位**：用之前的"强者"做垫脚石。描写环境崩坏的程度来量化主角的随手一击。
            【拒绝水文-执行标准】
            1. **跳过过程**：能一招秒的，绝不写三招。
            2. **情绪收割**：重点描写打完后的"舔包"和"众人膜拜"环节。
            """,
            "男频-末世/无限流": """
            【文风基调】分秒必争、利益至上、资源换算。
            【剧情推进引擎】
            1. **价值锚定**：看到任何物体，第一时间转化为"资源/点数/生存率"。看到超市不是写货架多乱，而是写"只剩三罐午餐肉"。
            2. **规则杀人**：环境描写主要为了体现"规则的残酷"（如：踩到红线就会死）。
            【拒绝水文-执行标准】
            1. **零废话**：在这个世界说话浪费体力。所有对话必须包含情报交换或欺诈。
            2. **紧迫感**：时刻悬着一个倒计时（生命值/任务时间）。
            """,
            "男频-系统数据": """
            【文风基调】数值驱动、即时满足、游戏化。
            【剧情推进引擎】
            1. **数据可视化**：不写怪物的长相，直接写血条、等级、弱点提示。环境只是背景贴图，数据才是本体。
            2. **收益前置**：做任何动作前，先暗示可能的收益（任务奖励），驱动读者看下去。
            【拒绝水文-执行标准】
            1. **数字化**：不要写"力量大增"，要写"力量+10"。
            2. **频繁结算**：每解决一个小麻烦，立刻弹窗奖励。
            """,
            "男频-历史权谋": """
            【文风基调】话里有话、利益交换、降维打击。
            【剧情推进引擎】
            1. **解读式叙事**：不写风景，写局势。看到下雨，主角想的是"粮运要受阻，粮价要涨，我有机会了"。
            2. **多层对话**：每一句对话都要拆解出表层意思和深层试探。
            【拒绝水文-执行标准】
            1. **去古风堆砌**：不要堆砌辞藻，重点写人心的贪婪和恐惧。
             2. **现代思维**：用现代人的降维打击（如经济战、科技树）来制造爽点。
             """
        }

        # ==================================================================
        # 📝 少样本写作范例库 - 已迁移到 style_system
        # 保留为 fallback，当风格卡中无示例时使用
        # ==================================================================
        self.FEW_SHOT_SAMPLES = {
            "男频-热血玄幻": """
【📖 写作范例 (请模仿以下语感和节奏)】
---

"跑。"

林默一把拽住苏婉的手腕，声音压得极低。

身后，密林深处传来树叶被碾碎的声音——不是风。有什么东西正以极快的速度穿过灌木，而且体型不小。

苏婉的手在发抖，但她咬着嘴唇没出声。

"三阶妖兽，至少。"林默的目光扫过前方三棵歪脖子树，"我从左边引开，你往右边溪流方向跑。记住——别回头。"

"可是你——"

"我死不了。"

他打断她的话，已经拔出了背后的断刀。刀刃上还残留着昨夜的兽血，在月光下反射出暗红色的光。

妖兽冲出灌木的那一刻，大地微微一颤。

林默不退反进。

断刀斜劈而下——没有花哨的招式，只是一刀，把全身魂力压在刀锋的那一个点上。

轰！

气浪炸开。碎木和泥土泼了苏婉一脸。等她抹掉脸上的土，只看到那只体长近丈的黑鳞蜥倒在地上，脖颈处一道深可见骨的裂口。而林默单膝跪在三步之外，虎口崩裂，血流了一手。

"这就是你的底牌？"他吐出一口血沫，盯着妖兽浑浊的眼睛，咧嘴笑了，"那你够倒霉的。我底牌还没翻呢。"
""",
            "男频-诡秘智斗": """
【📖 写作范例 (请模仿以下语感和节奏)】
---

何宇从进入这间茶室的第一秒起，就感觉到了不对劲。

茶还是热的。桌上三只杯子，两只被动过。一只正放在他面前，茶水刚好到杯沿八分的位置——他习惯的倒法。

但问题在于，他没有约任何人来这里。

他不动声色地坐下，端起茶杯，低头嗅茶香的间隙扫了一眼杯底。没有沉淀，没有异味。茶没问题。那么有问题的就是——这间茶室。

窗外的街景是他熟悉的南街第三巷，但街对面那家铺子的牌匾上，"永和布庄"的"永"字少了一横。

不对。

他三个月前路过的时候，那块匾还是完好的。

"何老板还是那么细心。"声音从屏风后面传来，带着一点沙哑的笑意，"不过这次，您数清楚了吗？桌上的杯子，到底是三只，还是四只？"

何宇猛地低头。

桌上三只杯子。但他进来之前，明明看见四只。

不对——

他霍然起身，后脊一阵发凉。不是杯子少了，是他进来之前，屋里根本就没有杯子。
""",
            "男频-系统数据": """
【📖 写作范例 (请模仿以下语感和节奏)】
---

【叮——检测到宿主完成首次越级击杀】

【战斗结算中...】
一阶灵修越级击杀三阶妖兽赤鬃狼，经验值×5倍
获得经验：1500（+125% 越级加成）
灵石掉落：×32
稀有材料：赤鬃狼王核心碎片 ×1（橙色品质，集齐五枚可激活隐藏武魂）

【新成就解锁：越级猎手】
效果：越级战斗中全属性+8%，持续30分钟

【警告：宿主生命值剩余7%，建议立即使用回复类丹药】

感受着视野左上角刷屏的数据流，秦冥单手撑地，大口喘息。

"差点翻车。"他擦了擦嘴角的血，目光落在物品栏里的【赤鬃狼王核心碎片】上，"不过值了。三阶妖兽的核心，市价至少八百灵石。而且——"

他点开武魂界面，看着碎片合成进度条跳过 1/5。

"再杀四只，就能解锁赤鬃武魂。"秦冥咧嘴一笑，从怀里摸出最后一颗止血丹塞进嘴里，"这买卖，不亏。"
""",
            "男频-历史权谋": """
【📖 写作范例 (请模仿以下语感和节奏)】
---

"陛下，户部今年实征银两，比去年少了三成。"

老尚书说完这句话，大殿里安静了整整十个呼吸。

年轻的皇帝坐在龙椅上，脸上的表情像是在听一件无关紧要的事。但跪在下面的户部尚书知道——这位十九岁的天子，六岁就开始听政了。

"三成。"皇帝终于开口，语气平得像一潭死水，"西北大旱减免两成，东南海寇减免一成。减了三成，实征还比去年少三成？"

"......"

"许大人，你是说，风调雨顺的江南，今年的税，一粒米都没收上来？"

户部尚书的额头已经挨到了冰冷的地砖。他不敢抬头。因为他知道，皇帝看到的奏折和他呈上去的，不是同一本。

李崇明站起身，走到殿中央。他的每一步都踩在老尚书的呼吸节拍上。

"查。"他把一份早已拟好的名单丢到地上，"从苏州织造开始往下查。许大人，朕给你一个月。查不出结果，你儿子在扬州的那六个盐铺——"他顿了一下，"就充公。"
""",
        }

    def _get_style_persona(self, style: str) -> str:
        """获取风格指令：优先从五维风格卡获取，fallback到旧系统"""
        # 优先：五维风格系统
        persona = get_writer_persona(style)
        if persona:
            return persona
        # Fallback：旧 STYLE_CONFIGS
        return self.STYLE_CONFIGS.get(style, self.STYLE_CONFIGS["男频-热血玄幻"])

    def _get_style_few_shot(self, style: str, scene_type: str = "") -> str:
        """获取few-shot示例：优先从风格卡获取，fallback到旧系统"""
        # 优先：五维风格系统
        examples = get_few_shot_examples(style, scene_type)
        if examples:
            return examples
        # Fallback：旧 FEW_SHOT_SAMPLES
        return self.FEW_SHOT_SAMPLES.get(style, "")
    def write_draft(self, outline, chapter_num, book_id, style="男频-热血玄幻", feedback=None, planned_title=None, original_draft=None):
        """
        核心生成方法
        """
        
        # 如果没有传入标题，使用默认格式
        if not planned_title:
            planned_title = f"第{chapter_num}章"
        
        # 1. 获取完整世界观
        world_config = db.get_world_config(book_id)
        hero = db.get_hero_full_status(book_id) or {}
        # 🟢 1. 提取主角核心人设 (无论第几章都需要！)
        hero_name = hero.get('name', '主角')
        hero_identity = hero.get('identity', '普通人')
        hero_appearance = hero.get('appearance', '外貌平平无奇') # <--- 新增
        hero_personality = hero.get('personality', '坚韧')
        hero_speech = hero.get('speech_style', '正常')
        hero_desire = hero.get('core_desire', '生存')

        # 🟢 计算当前位置信息
        position_tracker = self._compute_position_tracker(chapter_num, book_id)

        # 🟢 2. 更新常驻人设 Prompt (必须加在这里，保证全书一致)
        appearance_instruction = ""
        if int(chapter_num) == 1:
            appearance_instruction = f"- **外貌**: {hero_appearance} (🔥本章需通过镜像或他人视角重点描写，建立印象)"
        else:
            # 后续章节：只有在动作需要时才顺带一提，否则闭嘴
            appearance_instruction = f"- **外貌**: {hero_appearance} (⚠️ 仅作为底层设定参考。除非涉及受伤、伪装或特定动作，否则严禁刻意重复描写外貌，防止啰嗦。)"
        #注意
        hero_profile = f"""
        【👤 主角核心人设 (必须时刻保持)】
        - **姓名**: {hero_name}
        - **身份**: {hero_identity} (所有思考逻辑必须基于此身份)
        {appearance_instruction}
        - **性格**: {hero_personality}
        - **说话风格**: {hero_speech}
        - **核心欲望**: {hero_desire}
        - **行为逻辑**: 遇到危机时，请务必体现【{hero_personality}】的特质，严禁OOC。
        """
        # 🟢 修复核心：如果数据库返回的是字符串，强制转为字典
        if isinstance(world_config, str):
            try:
                print(f"⚠️ [Writer] 检测到 world_config 是字符串，正在解析...")
                world_config = json.loads(world_config)
            except Exception as e:
                print(f"❌ [Writer] world_config JSON 解析失败: {e}")
                world_config = {}
        
        # 确保它至少是个空字典，防止后续 .get 报错
        if world_config is None:
            world_config = {}
        # =========================================================
        # 🟢 核心修改：基于大纲的轻量级检索 (替代全量注入)
        # =========================================================
        # 我们不传 full_config，而是传一个“阉割版”的 config 给 AI
        safe_world_config = self._apply_fog_of_war(world_config, int(chapter_num))
        
        # 提取大纲中的关键人物和地点进行按需检索
        outline_str = str(outline)
        active_npcs = db.get_active_npcs(book_id) # 获取当前活跃NPC作为补充上下文
        
        # 2. 获取作家人格 (五维风格系统，含fallback)
        writer_persona = self._get_style_persona(style)
        few_shot = self._get_style_few_shot(style)
        
        # 3. 动态构建 Opening Guide
        opening_guide = ""
        if int(chapter_num) == 1:
            # 🟢 判定开局类型：是穿越/系统文？还是传统土著文？
            # 这里的判断逻辑可以根据 style 关键词，或者让 WorldBuilder 生成一个 is_transmigrator 标记
            is_isekai = any(keyword in style for keyword in ["系统", "穿越", "无限", "末世", "重生", "现代"])
            
            if is_isekai:
                # ==========================================
                # 🅰️ 穿越/重生模式 (强调：认知错位、寻找锚点)
                # ==========================================
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：真实感重构 (穿越/重生视角)】
                主角身份：{hero_identity}。
                
                **🟢 必须执行的心理三阶段**：
                1. **生理排斥**：穿越/重生是有代价的。描写剧烈的眩晕、幻痛或窒息感。第一反应必须是“我在做梦”或“宿醉”，并试图寻找现代社会的锚点（如**下意识摸手机**、找眼镜、看时间）。
                2. **认知崩塌**：当发现环境变成了[{safe_world_config.get('intro', '异世界')[:20]}...]时，展现世界观冲击。不要兴奋，要恐惧、迷茫。
                3. **职业/性格防御**：主角之所以能冷静，是因为发挥了[{hero_identity}]的特质。
                   - 例如：如果是医生，通过分析身体指标来冷静；如果是杀手，通过观察环境退路来冷静；如果是程序员，通过分析逻辑漏洞来冷静。
                   - **核心要求**：用主角原本的【{hero_identity}】思维去解构眼前陌生的世界，强行建立安全感。
                """
            else:
                # ==========================================
                # 🅱️ 土著/原住民模式 (强调：生存危机、情感压抑)
                # ==========================================
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：沉浸式切入 (原住民视角)】
                主角是土著【{hero_identity}】，他对这个世界习以为常，不要大惊小怪。
                
                **🟢 必须执行的开篇逻辑**：
                1. **生活流切入**：从主角最熟悉的一个动作写起（如：擦拭祖传的断剑、在雨中跪着求药、在朝堂上被指责）。
                2. **危机爆发**：平静瞬间被打破。不管是退婚、灭门还是追杀，必须在开篇前 500 字内把主角逼入绝境。
                3. **情感爆发**：重点描写主角的【{hero_personality}】。面对羞辱或绝境，他是隐忍不发？还是暴怒反击？
                **🚫 禁令**：严禁出现“穿越”、“系统”、“地球”等出戏的现代词汇。主角的思维必须完全符合土著逻辑。
                """

        elif int(chapter_num) <= 3:
            opening_guide = "【⚠️ 黄金三章】节奏加倍，每 500 字必须有一个小冲突或悬念。"

        # 4. 动态构建 Feedback
        feedback_instruction = ""
        if feedback:
            print(f"✍️ [Writer] 收到编辑部的退稿意见: {feedback}")
            original_block = ""
            if original_draft:
                draft_snippet = str(original_draft)
                original_block = f"""
            【📄 上一版原文 (请在此基础上修改，而不是从零重写)】
            {draft_snippet}
            """
            feedback_instruction = f"""
            【🚨 强力修正指令 — 精准修改模式】
            上一版被退稿！编辑意见："{feedback}"
            {original_block}
            【⚠️ 修改策略 (重要！不是重写，是修改)】
            1. **保留好内容**：原文中对话自然、动作流畅的部分，只字不动。
            2. **只改问题点**：仅针对编辑意见中指出的具体问题进行修改。
            3. **避免引入新问题**：修改时不要改动人名、设定、已有剧情逻辑。
            4. **保持总字数**：修改后总字数应与原文基本一致。
            
            【🔥 去 AI 味强制指令 (重写时必须执行)】
            1. 替换所有"他感到/他觉得/他意识到"为具体的生理反应或动作
            2. 对话改为口语化：短句、打断、省略主语
            3. 每 300 字内至少出现一句极短句（3-5字）制造节奏变化
            4. 删除任何"在这一刻，他明白了..."的总结句，改用动作或意象
            5. 🚫 环境描写禁令：整章最多2句，禁止形容词堆砌（雄伟/阴森/恐怖等标签词）
            6. 🚫 禁止面部微表情长篇描写（"他的眼中闪过一丝复杂的情绪..."）
            """
        
        # 5. 世界观约束
        # 🟢 注入世界观约束 (注意：这里用的是 safe_world_config)
        intro = safe_world_config.get('intro', '标准网文世界')
        
        # 这里的 power_sys 已经是被“锁级”过的了
        power_sys = safe_world_config.get('power_system', '常规体系') 
        
        # 这里的 villain 已经是被“打码”过的了
        villain_info = safe_world_config.get('villain', {})
        villain_desc = f"当前威胁: {villain_info.get('name', '未知')}"
        
        world_constraints = f"""
        【🌍 世界观严格约束】
        - **当前背景**: {intro}
        - **已知力量**: {power_sys}
        - **当前反派**: {villain_desc}
        - **活跃配角/反派状态**: 
        {active_npcs}
        - **禁令**: 严禁提及任何超出【已知力量】等级的设定，严禁提及任何未登场的高级地图。
        """
        print(f"✍️ [Writer] 启动 | 风格: [{style}]")
        
        # 6. 拆分大纲
        scenes = self._split_outline(outline)
        
        full_chapter = ""
        previous_context = "" 
        
        # 7. 循环生成 (The Loop)
        for i, scene in enumerate(scenes, 1):
            print(f"   -> 正在撰写第 {i}/{len(scenes)} 部分...")
            
            # --- 优化点 A: 动态字数节奏 ---
            length_guide = "1000字左右"
            if i == 1: length_guide = "1000字 (铺垫环境，细致入微)"
            elif i == len(scenes): length_guide = "1200字 (高潮收尾，留有悬念)"
            
            prompt = f"""
            【角色设定】
            你是一名顶级的网络小说大神，目前正在连载一部 **{style}** 风格的作品。
            
            {position_tracker}
            {few_shot}
            {writer_persona}
            {hero_profile}
            {opening_guide}
            {world_constraints}
            {feedback_instruction}

            【章节标题】
            本章标题为：**{planned_title}**。请只写正文内容，**不要在正文中重复标题**。

            【输入数据】
            📌 **全章总纲**：
            {outline}
            
            【重要】这个章节只需要写**1个小场景**，不是完整章节。
            
            【当前任务 (第 {i}/{len(scenes)} 部分)】- 只需完成这部分
            只写这一个小场景：
            >>> {scene} <<>
            
            【⚡ 写作要求 (Anti-AI)】
            1. 动作和对话驱动：用动作/对话推进，避免大段静态心理描写；但主角面临关键选择时，允许1-2句内心权衡（体现代价感）
            2. 环境描写服务于情绪与氛围，单场景不超过2句，禁止与剧情无关的景物堆砌
            3. 微表情精简：对话时"他眯起眼"就够，不要展开
            4. 对话必须有潜台词：角色各有立场和目的，禁止任务式问答

            【格式要求】
            1. **字数限制**：只写 **{length_guide}**，是的就是这么少。
            2. **禁止扩展**：只写当前场景，不要写任何后续内容。
            3. **立即结束**：写完这个动作就停，不准续写。
            """
            
            # --- 优化点 B: 状态自检 (仅最后一段) ---
            is_last_part = (i == len(scenes))
            if is_last_part:
                prompt += """
            
            【重要元数据指令】
            文章结尾请务必进行一次"状态自检"：
            如果本章主角身体状态/装备/境界发生了实质性改变，请在全文最后一行单独输出：>>>STATUS_CHANGED<<<
            否则不要输出该标记。
            """
            
            # 温度设置：女频略高(细腻)，男频略低(逻辑)
            temp = 0.92 if "女频" in style else 0.85
            
            scene_text = self.call(prompt, temperature=temp, json_mode=False)
            
            # 清洗废话（已内置 JSON content 提取）
            scene_text = self._clean_response(scene_text)
            
            # 简单拼接：标题只在开头加，后续段落直接追加
            if i == 1:
                full_chapter = f"{planned_title}\n\n{scene_text}"
            else:
                full_chapter += f"\n\n{scene_text}"
            
            # 更新上下文用于下一个场景的参考（不用于去重！）
            previous_context = scene_text
        
        # 提取 STATUS_CHANGED 标记，但保留在返回文本中供前端检测
        status_changed = False
        if ">>>STATUS_CHANGED<<<" in full_chapter:
            status_changed = True
            print("   -> 检测到状态变化标记")
        
        # 从返回中移除标记，保持正文干净
        full_chapter = re.sub(r'\n*>>>STATUS_CHANGED<<<', '', full_chapter, flags=re.IGNORECASE).strip()
        
        return {"draft": full_chapter, "status_changed": status_changed}

    async def awrite_draft(self, outline, chapter_num, book_id, style="男频-热血玄幻", feedback=None, planned_title=None, original_draft=None):
        """异步版 write_draft：DB 查询并行 + 分镜 LLM 调用异步"""
        if not planned_title:
            planned_title = f"第{chapter_num}章"
        
        # ===== 异步并行：4个DB查询 =====
        world_config, hero, active_npcs, book_plan = await asyncio.gather(
            asyncio.to_thread(db.get_world_config, book_id),
            asyncio.to_thread(db.get_hero_full_status, book_id),
            asyncio.to_thread(db.get_active_npcs, book_id),
            asyncio.to_thread(db.get_book_plan, book_id),
        )
        hero = hero or {}

        hero_name = hero.get('name', '主角')
        hero_identity = hero.get('identity', '普通人')
        hero_appearance = hero.get('appearance', '外貌平平无奇')
        hero_personality = hero.get('personality', '坚韧')
        hero_speech = hero.get('speech_style', '正常')
        hero_desire = hero.get('core_desire', '生存')

        # 🟢 计算当前位置信息
        position_tracker = self._compute_position_tracker(chapter_num, book_id)
        
        appearance_instruction = ""
        if int(chapter_num) == 1:
            appearance_instruction = f"- **外貌**: {hero_appearance} (🔥本章需通过镜像或他人视角重点描写，建立印象)"
        else:
            appearance_instruction = f"- **外貌**: {hero_appearance} (⚠️ 仅作为底层设定参考。)"
        
        hero_profile = f"""
        【👤 主角核心人设 (必须时刻保持)】
        - **姓名**: {hero_name}
        - **身份**: {hero_identity} (所有思考逻辑必须基于此身份)
        {appearance_instruction}
        - **性格**: {hero_personality}
        - **说话风格**: {hero_speech}
        - **核心欲望**: {hero_desire}
        - **行为逻辑**: 遇到危机时，请务必体现【{hero_personality}】的特质，严禁OOC。
        """
        
        if isinstance(world_config, str):
            try:
                world_config = json.loads(world_config)
            except json.JSONDecodeError as e:
                logger.warning(f"[Writer] world_config JSON 解析失败，回退到空字典: {e}")
                world_config = {}
        if world_config is None:
            world_config = {}
        
        safe_world_config = self._apply_fog_of_war(world_config, int(chapter_num))
        writer_persona = self._get_style_persona(style)
        few_shot = self._get_style_few_shot(style)
        
        opening_guide = ""
        if int(chapter_num) == 1:
            is_isekai = any(keyword in style for keyword in ["系统", "穿越", "无限", "末世", "重生", "现代"])
            if is_isekai:
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：真实感重构 (穿越/重生视角)】
                主角身份：{hero_identity}。
                **🟢 必须执行的心理三阶段**：
                1. **生理排斥**：描写剧烈的眩晕、幻痛或窒息感。
                2. **认知崩塌**：当发现环境变成了异世界时，展现世界观冲击。
                3. **职业/性格防御**：用主角原本的【{hero_identity}】思维去解构眼前陌生的世界，强行建立安全感。
                """
            else:
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：沉浸式切入 (原住民视角)】
                主角是土著【{hero_identity}】，他对这个世界习以为常，不要大惊小怪。
                1. **生活流切入**：从主角最熟悉的一个动作写起。
                2. **危机爆发**：必须在开篇前 500 字内把主角逼入绝境。
                3. **情感爆发**：重点描写主角的【{hero_personality}】。
                **🚫 禁令**：严禁出现"穿越"、"系统"、"地球"等出戏的现代词汇。
                """
        elif int(chapter_num) <= 3:
            opening_guide = "【⚠️ 黄金三章】节奏加倍，每 500 字必须有一个小冲突或悬念。"
        
        feedback_instruction = ""
        if feedback:
            print(f"✍️ [Writer] 收到编辑部的退稿意见: {feedback}")
            feedback_instruction = f"""
            【🚨 强力修正指令】
            上一版被退稿！编辑意见："{feedback}"
            请针对性修改，不要犯同样的错误。
            
            【🔥 去 AI 味强制指令 (重写时必须执行)】
            1. 替换所有"他感到/他觉得/他意识到"为具体的生理反应或动作
            2. 对话改为口语化：短句、打断、方言词、省略主语
            3. 每 300 字内至少出现一句极短句（3-5字）制造节奏变化
            4. 删除任何类似"在这一刻，他明白了..."的总结句，改用动作或意象暗指
            5. 至少添加一处五感细节（嗅觉/触觉优先，视觉最不重要）
            """
        
        intro = safe_world_config.get('intro', '标准网文世界')
        power_sys = safe_world_config.get('power_system', '常规体系')
        villain_info = safe_world_config.get('villain', {})
        villain_desc = f"当前威胁: {villain_info.get('name', '未知')}"
        
        world_constraints = f"""
        【🌍 世界观严格约束】
        - **当前背景**: {intro}
        - **已知力量**: {power_sys}
        - **当前反派**: {villain_desc}
        - **活跃配角/反派状态**: 
        {active_npcs}
        - **禁令**: 严禁提及任何超出【已知力量】等级的设定，严禁提及任何未登场的高级地图。
        """
        print(f"✍️ [Writer] 启动 (异步) | 风格: [{style}]")

        scenes = self._split_outline(outline)
        temp = 0.92 if "女频" in style else 0.85

        # 🪝 提取章末钩子（Suspense Engine：大纲驱动结尾）
        chapter_hook = self._extract_chapter_hook(outline)

        # ===== 核心优化：分镜异步并行生成 =====
        # 构建所有 prompt
        prompts = []
        for i, scene in enumerate(scenes, 1):
            length_guide = "1000字左右"
            if i == 1: length_guide = "1000字 (铺垫环境，细致入微)"
            elif i == len(scenes): length_guide = "1200字 (高潮收尾，留有悬念)"

            prompt = f"""
            【角色设定】
            你是一名顶级的网络小说大神，目前正在连载一部 **{style}** 风格的作品。

            {writer_persona}
            {hero_profile}
            {opening_guide}
            {world_constraints}
            {feedback_instruction}

            【章节标题】
            本章标题为：**{planned_title}**。请只写正文内容，**不要在正文中重复标题**。

            【输入数据】
            📌 **全章总纲**：
            {outline}

            【重要】这个章节只需要写**1个小场景**，不是完整章节。

            【当前任务 (第 {i}/{len(scenes)} 部分)】- 只需完成这部分
            只写这一个小场景：
            >>> {scene} <<<

            【⚡ 写作要求 (Anti-AI)】
            1. 动作和对话驱动：用动作/对话推进，避免大段静态心理描写；但主角面临关键选择时，允许1-2句内心权衡（体现代价感）
            2. 环境描写服务于情绪与氛围，单场景不超过2句，禁止与剧情无关的景物堆砌
            3. 微表情精简：对话时"他眯起眼"就够，不要展开
            4. 对话必须有潜台词：角色各有立场和目的，禁止"你为什么要这么做？""因为我必须保护大家。"式任务问答

            【格式要求】
            1. **字数限制**：只写 **{length_guide}**，是的就是这么少。
            2. **禁止扩展**：只写当前场景，不要写任何后续内容。
            3. **立即结束**：写完这个动作就停，不准续写。
            """

            is_last_part = (i == len(scenes))
            if is_last_part:
                if chapter_hook:
                    prompt += f"""
            【🪝 章末钩子指令 (必须执行)】
            本章结尾必须落在以下钩子上：{chapter_hook}
            要求：钩子 = 新信息 + 风险/悬念 + 下一步行动方向。严禁"一个神秘黑影出现"式空钩子。
            """
                prompt += """
            【重要元数据指令】
            文章结尾请务必进行一次"状态自检"：
            如果本章主角身体状态/装备/境界发生了实质性改变，请在全文最后一行单独输出：>>>STATUS_CHANGED<<<
            否则不要输出该标记。
            """

            prompts.append(prompt)
        
        # 并行调用所有分镜的 LLM
        print(f"   -> 🚀 并行撰写 {len(prompts)} 个分镜...")
        scene_texts = await asyncio.gather(*[
            self.acall(p, temperature=temp, json_mode=False) for p in prompts
        ])
        
        # 拼接结果
        full_chapter = ""
        for i, scene_text in enumerate(scene_texts, 1):
            scene_text = self._clean_response(scene_text)
            
            if i == 1:
                full_chapter = f"{planned_title}\n\n{scene_text}"
            else:
                full_chapter += f"\n\n{scene_text}"
        
        status_changed = False
        if ">>>STATUS_CHANGED<<<" in full_chapter:
            status_changed = True
            print("   -> 检测到状态变化标记")
        
        full_chapter = re.sub(r'\n*>>>STATUS_CHANGED<<<', '', full_chapter, flags=re.IGNORECASE).strip()
        
        return {"draft": full_chapter, "status_changed": status_changed}

    async def awrite_direct(self, outline, chapter_num, book_id, style="男频-热血玄幻", feedback=None, planned_title=None, original_draft=None):
        """直出模式：根据大纲一次性生成完整章节（异步）"""
        if not planned_title:
            planned_title = f"第{chapter_num}章"

        world_config, hero, active_npcs, book_plan = await asyncio.gather(
            asyncio.to_thread(db.get_world_config, book_id),
            asyncio.to_thread(db.get_hero_full_status, book_id),
            asyncio.to_thread(db.get_active_npcs, book_id),
            asyncio.to_thread(db.get_book_plan, book_id),
        )
        hero = hero or {}

        hero_name = hero.get('name', '主角')
        hero_identity = hero.get('identity', '普通人')
        hero_appearance = hero.get('appearance', '外貌平平无奇')
        hero_personality = hero.get('personality', '坚韧')
        hero_speech = hero.get('speech_style', '正常')
        hero_desire = hero.get('core_desire', '生存')

        position_tracker = self._compute_position_tracker(chapter_num, book_id)

        appearance_instruction = f"- **外貌**: {hero_appearance} (⚠️ 仅作为底层设定参考。)"
        if int(chapter_num) == 1:
            appearance_instruction = f"- **外貌**: {hero_appearance} (🔥本章需通过镜像或他人视角重点描写，建立印象)"

        hero_profile = f"""
        【👤 主角核心人设 (必须时刻保持)】
        - **姓名**: {hero_name}
        - **身份**: {hero_identity} (所有思考逻辑必须基于此身份)
        {appearance_instruction}
        - **性格**: {hero_personality}
        - **说话风格**: {hero_speech}
        - **核心欲望**: {hero_desire}
        - **行为逻辑**: 遇到危机时，请务必体现【{hero_personality}】的特质，严禁OOC。
        """

        if isinstance(world_config, str):
            try:
                world_config = json.loads(world_config)
            except json.JSONDecodeError as e:
                logger.warning(f"[Writer] world_config JSON 解析失败，回退到空字典: {e}")
                world_config = {}
        if world_config is None:
            world_config = {}

        safe_world_config = self._apply_fog_of_war(world_config, int(chapter_num))
        writer_persona = self._get_style_persona(style)
        few_shot = self._get_style_few_shot(style)

        opening_guide = ""
        if int(chapter_num) == 1:
            is_isekai = any(keyword in style for keyword in ["系统", "穿越", "无限", "末世", "重生", "现代"])
            if is_isekai:
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：真实感重构 (穿越/重生视角)】
                主角身份：{hero_identity}。
                1. **生理排斥**：描写剧烈的眩晕、幻痛或窒息感。
                2. **认知崩塌**：当发现环境变成了异世界时，展现世界观冲击。
                3. **职业/性格防御**：用主角原本的【{hero_identity}】思维去解构眼前陌生的世界。
                """
            else:
                opening_guide = f"""
                【⚠️ 第 1 章特化指令：沉浸式切入 (原住民视角)】
                1. **生活流切入**：从主角最熟悉的一个动作写起。
                2. **危机爆发**：必须在开篇前 500 字内把主角逼入绝境。
                3. **情感爆发**：重点描写主角的【{hero_personality}】。
                🚫 严禁：出现现代词汇。
                """
        elif int(chapter_num) <= 3:
            opening_guide = "【⚠️ 黄金三章】节奏加倍，每 500 字必须有一个小冲突或悬念。"

        feedback_instruction = ""
        if feedback:
            original_block = ""
            if original_draft:
                draft_snippet = str(original_draft)
                original_block = f"""
            【📄 上一版原文 (请在此基础上修改)】
            {draft_snippet}
            """
            feedback_instruction = f"""
            【🚨 强力修正指令 — 精准修改模式】
            上一版被退稿！编辑意见："{feedback}"
            {original_block}
            【⚠️ 修改策略 (不是重写，是修改！)】
            1. **保留好内容**：原文中好的部分，只字不动。
            2. **只改问题点**：仅针对编辑意见中指出的具体问题进行修改。
            3. **避免引入新问题**：修改时不要改动人名、设定、已有剧情逻辑。

            【🔥 去 AI 味强制指令 (修改时必须执行)】
            1. 替换所有"他感到/他觉得/他意识到"为具体的生理反应或动作
            2. 对话改为口语化：短句、打断、省略主语
            3. 每 300 字内至少出现一句极短句（3-5字）
            4. 删除"在这一刻，他明白了..."的总结句
            5. 🚫 环境描写最多2句，禁止形容词堆砌
            6. 🚫 禁止面部微表情长篇描写
            """

        intro = safe_world_config.get('intro', '标准网文世界')
        power_sys = safe_world_config.get('power_system', '常规体系')
        villain_info = safe_world_config.get('villain', {})
        villain_desc = f"当前威胁: {villain_info.get('name', '未知')}"

        world_constraints = f"""
        【🌍 世界观严格约束】
        - **当前背景**: {intro}
        - **已知力量**: {power_sys}
        - **当前反派**: {villain_desc}
        - **活跃配角/反派状态**: 
        {active_npcs}
        - **禁令**: 严禁提及任何超出【已知力量】等级的设定，严禁提及任何未登场的高级地图。
        """

        print(f"✍️ [Writer-Direct] 启动 (直出模式) | 风格: [{style}]")
        target_words = 4000

        # 🪝 章末钩子指令（Suspense Engine：大纲驱动结尾）
        chapter_hook = self._extract_chapter_hook(outline)
        hook_instruction = ""
        if chapter_hook:
            hook_instruction = f"""【🪝 章末钩子指令 (必须执行)】
本章结尾必须落在以下钩子上：{chapter_hook}
要求：钩子 = 新信息 + 风险/悬念 + 下一步行动方向。严禁"一个神秘黑影出现"式空钩子。"""

        from app.core.prompt_config import get_prompt
        from app.core.prompt_renderer import render_prompt
        cfg = get_prompt("write_direct")
        prompt = render_prompt(cfg.get("template", ""), {
            "style": style,
            "writer_persona": writer_persona,
            "few_shot": few_shot,
            "hero_profile": hero_profile,
            "opening_guide": opening_guide,
            "world_constraints": world_constraints,
            "feedback_instruction": feedback_instruction,
            "planned_title": planned_title,
            "outline": str(outline),
            "target_words": str(target_words),
            "position_tracker": position_tracker,
            "hook_instruction": hook_instruction,
        })

        temp = 0.92 if "女频" in style else 0.85

        full_chapter = await self._acall_with_stage(prompt, stage_override="write_direct", temperature=temp, json_mode=False)

        # 统一提取 content（_clean_response 已内置所有格式处理）
        full_chapter = self._clean_response(full_chapter)
        full_chapter = f"{planned_title}\n\n{full_chapter}"

        status_changed = False
        if ">>>STATUS_CHANGED<<<" in full_chapter:
            status_changed = True
        full_chapter = re.sub(r'\n*>>>STATUS_CHANGED<<<', '', full_chapter, flags=re.IGNORECASE).strip()

        return {"draft": full_chapter, "status_changed": status_changed}

    @staticmethod
    def _extract_chapter_hook(outline) -> str:
        """从大纲中提取章末钩子（chapter_hook 字段），兼容 dict / JSON 字符串"""
        try:
            data = outline
            if isinstance(outline, str):
                data = parse_llm_json(outline, default=None)
            if isinstance(data, dict):
                hook = data.get("chapter_hook")
                if isinstance(hook, str):
                    return hook.strip()
        except Exception:
            pass
        return ""

    def _split_outline(self, outline):
        """
        辅助函数：拆分大纲
        🟢 修复版：增加类型检查，防止 scenes 列表中混入字符串导致崩溃
        """
        print("   -> 正在解析分镜...")
        
        scenes_data = []
        
        # 1. 尝试解析 JSON
        try:
            if isinstance(outline, dict):
                scenes_data = outline.get("scenes", [])
            elif isinstance(outline, str):
                # 用统一工具清洗并解析
                data = parse_llm_json(outline, default=None)
                if isinstance(data, dict):
                    scenes_data = data.get("scenes", [])
        except Exception as e:
            print(f"⚠️ [Writer] 大纲解析异常，转为文本处理: {e}")
            scenes_data = []

        # =========================================================
        # 🟢 路径 1: 结构化分镜处理 (增加防御逻辑)
        # =========================================================
        if scenes_data and len(scenes_data) > 0:
            formatted_parts = []
            for idx, scene in enumerate(scenes_data, 1):
                
                # 🛡️防御性编程：如果 scene 是字符串，手动包装成字典
                if isinstance(scene, str):
                    scene_dict = {
                        "beat_type": "剧情推进",
                        "location": "未知场景",
                        "stage_render_focus": "无特殊要求",
                        "plot_summary": scene, # 把字符串内容作为剧情
                        "key_info_reveal": "无",
                        "emotion_goal": "平稳",
                        "functional_value": "推进剧情"
                    }
                    scene = scene_dict # 替换为字典
                
                # 现在 scene 肯定是字典了，可以安全使用 .get
                part_text = f"""
                【第 {idx} 节: {scene.get('beat_type', '剧情发展')}】
                ---------------------------------------------------
                📍 场景/环境: {scene.get('location', '未知')} 
                   -> 渲染焦点: {scene.get('stage_render_focus', '无特殊要求')}
                   
                🎬 核心剧情: {scene.get('plot_summary', '无剧情描述')}
                
                🔑 关键信息/伏笔: {scene.get('key_info_reveal', '无')}
                
                🔥 目标情绪: {scene.get('emotion_goal', '平稳')}
                
                ⚡ 功能性价值: {scene.get('functional_value', '推进剧情')}
                ---------------------------------------------------
                """
                formatted_parts.append(part_text.strip())
            
            print(f"   -> ✅ 成功解析出 {len(formatted_parts)} 个结构化分镜")
            return formatted_parts

        # =========================================================
        # 🟡 路径 2: 传统纯文本兜底
        # =========================================================
        print("   -> 大纲非结构化，使用 LLM 辅助拆解...")
        
        # 🟢 修复：检查大纲是否本身就是 JSON (带有 content 字段)
        if isinstance(outline, str):
            outline_data = parse_llm_json(outline, default=None)
            if isinstance(outline_data, dict) and "content" in outline_data:
                outline = outline_data["content"]
                print("   -> 从大纲 JSON 中提取了 content 字段")
        
        splitter_prompt = f"""
        任务：将以下小说大纲拆分为恰好 2 个独立的、连贯的写作分镜。
        
        【大纲】
        {outline}
        
        【要求】
        - 拆分点应该是情节的自然转折点
        - 每个分镜应该有自己的小高潮或悬念
        - 只输出 2 段纯文本，使用 "|||" 作为分隔符
        - 不要输出任何其他说明
        """
        response = self.call(splitter_prompt, json_mode=False)
        
        # 🟢 修复：检查 LLM 返回的是否是 JSON 格式
        response_to_parse = response
        if isinstance(response, str):
            json_data = parse_llm_json(response, default=None)
            if isinstance(json_data, dict):
                # 检查是否有 content 字段
                if "content" in json_data:
                    response_to_parse = json_data["content"]
                    print("   -> 从 LLM 返回中提取了 content 字段")
                elif "scenes" in json_data:
                    # 如果返回的是 scenes 数组，直接返回结构化结果
                    scenes_from_llm = json_data["scenes"]
                    formatted_parts = [f"【场景{i+1}】 {s}" for i, s in enumerate(scenes_from_llm[:2])]
                    print(f"   -> LLM 返回了结构化 scenes: {len(formatted_parts)} 个")
                    return formatted_parts
        
        cleaned = self._clean_response(response_to_parse)
        parts = cleaned.split("|||")
        if len(parts) < 2:
            parts = [p.strip() for p in cleaned.split("\n\n") if len(p.strip()) > 30]
        
        result = [f"【场景{i+1}】 {p.strip()}" for i, p in enumerate(parts[:2])]
        print(f"   -> 拆分结果: {len(result)} 个场景")
        return result

    def _clean_response(self, text):
        """清洗 AI 可能输出的废话 + 统一提取 JSON-wrapped content"""
        if not text: return ""
        
        # 🟢 统一 JSON content 提取：处理各种包裹格式
        import re as _re
        extracted = text
        
        # 格式1: ```json {"content": "..."} ```
        # 格式2: '''json {"chapter_content": "..."} '''  (DeepSeek 特有)
        # 格式3: 纯 {"text": "..."}
        # 支持 content / chapter_content / text / body / draft / output 等字段名
        CONTENT_KEYS = ["content", "chapter_content", "text", "body", "draft", "output", "result"]
        
        try:
            # 清理各种包裹标记（委托给统一工具）
            cleaned = strip_code_fences(text)

            if cleaned.strip().startswith("{"):
                try:
                    data = json.loads(cleaned)
                    if isinstance(data, dict):
                        for key in CONTENT_KEYS:
                            if key in data and isinstance(data[key], str) and len(data[key]) > 20:
                                extracted = data[key]
                                # 递归检查 content 里是否还有嵌套 JSON
                                if extracted.strip().startswith("{"):
                                    try:
                                        inner = json.loads(extracted)
                                        if isinstance(inner, dict):
                                            for k in CONTENT_KEYS:
                                                if k in inner and isinstance(inner[k], str):
                                                    extracted = inner[k]
                                                    break
                                    except json.JSONDecodeError:
                                        # 内层不是合法 JSON，保留外层 extracted 原值
                                        pass
                                break
                except json.JSONDecodeError:
                    # 外层 JSON 解析失败，extracted 保持为原始 text
                    pass
        except Exception as e:
            logger.debug(f"[Writer] _extract_content JSON 提取失败，回退到原文: {e}")
        
        # 清洗常见废话前缀
        patterns = [
            r"^好的[，,。!]*",
            r"^遵命[，,。!]*",
            r"^没问题[，,。!]*",
            r"^Sure[，,。!]*",
            r"^Here is.*?:",
            r"^以下是.*?正文.*?[：:]",
            r"^根据您的要求.*?[：:]",
            r"^###.*",
            r"^# .*\n",
            r"^\n+",
        ]
        for p in patterns:
            extracted = _re.sub(p, "", extracted, flags=_re.IGNORECASE|_re.MULTILINE).strip()
        
        return extracted

    def _apply_fog_of_war(self, config, current_chap):
        """
        🌫️ 战争迷雾过滤器：根据章节进度，动态阉割世界观信息
        """
        if not config: return {}
        
        safe_config = copy.deepcopy(config)

        # =========================================================
        # 1. 基础数据清洗 (递归解析 JSON 字符串)
        # =========================================================
        nested_keys = ['power_system', 'villain', 'locations', 'hero', 'gold_finger', 'book_plan']
        
        for key in nested_keys:
            val = safe_config.get(key)
            if isinstance(val, str):
                try:
                    safe_config[key] = json.loads(val)
                except json.JSONDecodeError as e:
                    logger.debug(f"[Writer] _apply_fog_of_war: 字段 '{key}' JSON 解析失败，回退为空: {e}")
                    safe_config[key] = {} if key != 'locations' else []
            if safe_config.get(key) is None:
                safe_config[key] = {} if key != 'locations' else []

        # =========================================================
        # 2. 计算分卷进度 (Volume Calculation)
        # =========================================================
        book_plan = safe_config.get('book_plan', {})
        volumes = book_plan.get('volumes', [])
        
        # 默认值
        current_vol_obj = None
        vol_idx = 0
        
        # 简单算法：累加章节数来判断当前在第几卷
        acc_chapters = 0
        for idx, vol in enumerate(volumes):
            vol_len = vol.get('estimated_chapters', 30)
            if current_chap <= acc_chapters + vol_len:
                current_vol_obj = vol
                vol_idx = idx
                break
            acc_chapters += vol_len
            
        # 如果超出所有卷，默认算在最后一卷
        if not current_vol_obj and volumes:
            current_vol_obj = volumes[-1]
            vol_idx = len(volumes) - 1

        # =========================================================
        # 3. 🔒 反派锁 (Villain Lock - 双层逻辑)
        # =========================================================
        
        # A. 全局最终 BOSS (Main Villain)
        # 逻辑：只有在最后一卷的后半段，才能看清最终 BOSS 的真面目
        is_final_volume = (vol_idx == len(volumes) - 1)
        
        if not is_final_volume:
            # 非最终卷，最终 BOSS 必须打码
            real_villain = safe_config.get('villain', {})
            safe_config['villain'] = {
                "name": "潜伏在暗处的未知威胁", 
                "identity": "幕后黑手",
                "motivation": "未知",
                "relation_to_hero": "未知"
            }
        
        # B. 本卷 BOSS (Volume Boss) - 🟢 关键新增
        # Writer 必须明确知道这一卷要打谁，否则写不出冲突
        if current_vol_obj:
            vol_boss = current_vol_obj.get('antagonist', {})
            # 我们把本卷 BOSS 的信息注入到 'current_threat' 字段，供 Writer 使用
            safe_config['current_threat'] = {
                "name": vol_boss.get('name', '本卷反派'),
                "identity": vol_boss.get('identity', '当前敌人'),
                "goal": f"阻碍主角完成【{current_vol_obj.get('title', '本卷目标')}】",
                "status": "活跃中"
            }
        else:
             safe_config['current_threat'] = {"name": "路边野怪", "identity": "杂鱼"}

        # =========================================================
        # 4. 🔒 战力锁 (Power Level Lock)
        # =========================================================
        power_sys = safe_config.get('power_system', {})
        if power_sys:
            levels = power_sys.get('levels', [])
            if isinstance(levels, list) and len(levels) > 0:
                # 逻辑：每一卷解锁 1-2 个新等级
                # 例如：第1卷看L1-L3，第2卷看L1-L5
                visible_levels_count = 3 + (vol_idx * 2) 
                limit = min(visible_levels_count, len(levels))
                
                if limit < len(levels):
                    safe_config['power_system']['levels'] = levels[:limit] + [f"??? (需到达第{vol_idx+2}卷解锁)"]
                else:
                    safe_config['power_system']['levels'] = levels

        # =========================================================
        # 5. 🔒 地图锁 (Map Lock)
        # =========================================================
        # 逻辑：Writer 只能看到当前卷及之前的地图，不知道未来的地图
        locs = safe_config.get('locations', [])
        if isinstance(locs, list) and len(locs) > 0:
            # 假设每一卷对应 1 个核心新地图
            map_limit = min(vol_idx + 1, len(locs))
            safe_config['locations'] = locs[:map_limit]

        return safe_config

    def _compute_position_tracker(self, chapter_num, book_id):
        """计算章节位置信息，用于注入到 Writer 提示词中"""
        try:
            bp = db.get_book_plan(book_id)
            if not bp or 'volumes' not in bp:
                return ""
            volumes = bp.get('volumes', [])
            total_chapters = sum(v.get('estimated_chapters', 50) for v in volumes)
            if total_chapters == 0:
                return ""
            
            acc = 0
            vol_idx = 0
            local_chap = chapter_num
            for idx, v in enumerate(volumes):
                vlen = v.get('estimated_chapters', 50)
                if chapter_num <= acc + vlen:
                    vol_idx = idx
                    local_chap = chapter_num - acc
                    break
                acc += vlen
            else:
                vol_idx = len(volumes) - 1 if volumes else 0
                local_chap = chapter_num - sum(v.get('estimated_chapters', 50) for v in volumes[:vol_idx])
            
            vol = volumes[vol_idx]
            vol_title = vol.get('title', f'第{vol_idx+1}卷')
            vol_len = vol.get('estimated_chapters', 50)
            global_pct = min(int(chapter_num / total_chapters * 100), 100)
            local_pct = min(int(local_chap / vol_len * 100), 100)
            
            return f"""【📍 当前位置】
全书第 {chapter_num}/{total_chapters} 章（{global_pct}%）| 第 {vol_idx+1}/{len(volumes)} 卷【{vol_title}】| 本卷第 {local_chap}/{vol_len} 章（{local_pct}%）"""
        except Exception as e:
            return ""

class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__("你是一名极其严苛的网文主编，专门负责审核新手作者的稿件。", stage_key="review")

    def review_draft(self, draft, outline, chapter_num, style):
        # 获取风格一致性检查项
        style_review = get_style_review_prompt(style)
        
        prompt = f"""
        任务：审核第 {chapter_num} 章正文，重点检测 AI 味。给分数 + 具体建议。

        【大纲】
        {str(outline)[:500]}

        【文风要求】{style}

        【正文】
        {str(draft)[:3000]}

        【评分标准】
        1. 逻辑连贯 (30%)：剧情有无矛盾
        2. AI 味检测 (30%)：句首词重复/书面语对话/情绪标签化/描写模板化/无短句爆发
        3. 完成度 (20%)：是否覆盖大纲关键点
        4. 风格一致性 (20%)：是否符合五维风格要求

        【AI 味典型问题（务必逐条检查）】
        - "然而/于是/此刻/只见" 连续使用超过2次 → 扣分
        - 对话用书面语 ("我对你感到失望") → 扣分
        - "他感到XX" 替代了生理反应 → 扣分
        - 环境描写超过2句 → 扣分

        {style_review}

        【返回 JSON 即可】
        {{"score": 75, "ai_flavor_score": 65, "style_score": 80, "comments": "具体问题（引原文句子）", "style_issues": "风格不一致的具体问题", "suggestions": "3-5条去AI改写建议"}}
        """
        raw_response = self.call(prompt, json_mode=True)
        return self._parse_json(raw_response)

    def _parse_json(self, text):
        """Robust JSON parser - 委托给 app.core.json_utils"""
        default = {"score": 70, "suggestions": "Reviewer returned invalid format, default pass."}
        if not text or not isinstance(text, str):
            return {"score": 70, "suggestions": "Empty input, default pass."}

        result = parse_llm_json(text, default=None)
        if result is not None:
            return result

        from app.core.logger import logger
        logger.warning(f"[Reviewer] JSON parse failed (len={len(text)}), raw={text[:200]}...")
        print(f"[Reviewer] JSON parse failed ({len(text)} chars): {text[:200]}")
        return default

    async def areview_draft(self, draft, outline, chapter_num, style):
        """异步版审核"""
        # 获取风格一致性检查项
        style_review = get_style_review_prompt(style)
        
        prompt = f"""
        任务：审核第 {chapter_num} 章正文，重点检测 AI 味。给分数 + 具体建议。

        【大纲】
        {str(outline)[:500]}

        【文风要求】{style}

        【正文】
        {str(draft)[:3000]}

        【评分标准】
        1. 逻辑连贯 (30%)：剧情有无矛盾
        2. AI 味检测 (30%)：是否句首词重复/书面语对话/情绪标签化/描写模板化/无短句爆发
        3. 完成度 (20%)：是否覆盖大纲关键点
        4. 风格一致性 (20%)：是否符合五维风格要求

        【AI 味典型问题（务必逐条检查）】
        - "然而/于是/此刻/只见" 连续使用超过2次 → 扣分
        - 对话用书面语 ("我对你感到失望") → 扣分
        - "他感到XX" 替代了生理反应 → 扣分
        - 环境描写超过2句 → 扣分

        {style_review}

        【返回 JSON 即可】
        {{"score": 75, "ai_flavor_score": 65, "style_score": 80, "comments": "具体问题（引原文句子）", "style_issues": "风格不一致的具体问题", "suggestions": "3-5条去AI改写建议"}}
        """
        raw_response = await self.acall(prompt, json_mode=True)
        return self._parse_json(raw_response)
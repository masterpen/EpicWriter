import json
from app.agents.base import BaseAgent
from app.core.json_utils import parse_llm_json
from app.core.style_system import get_style_constraint

class WorldBuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__("你是一个世界观架构师。你的任务是根据用户的简短描述，设计一套完整、逻辑自洽且极具爽感的网文世界观。")
    def _get_style_constraints(self, style):
        """根据流派返回世界观构建约束（委托给 style_system SSOT）"""
        return get_style_constraint(style)
    def build_world(self, idea, total_chapters=100, style="男频-热血玄幻", book_id=None):
        prefix = f"[{book_id}] " if book_id else ""
        print(f"🌍 [WorldBuilder] {prefix}正在构建世界 | 脑洞: {idea} | 风格: {style}...")
        # 🟢 1. 获取流派专属约束 (核心逻辑)
        style_constraints = self._get_style_constraints(style)
        prompt = f"""
        用户想要写一本这样的小说：
        【核心脑洞】{idea}
        【预估篇幅】{total_chapters} 章
        【目标风格】{style}
        
        {style_constraints}
        
        请设计一个能够支撑起这个篇幅的宏大世界。不仅要设计骨架，更要填充血肉。
        
        【🚨 核心设计要求 (CRITICAL)】
        1. **金手指 (Gold Finger)**: 必须严格遵守【目标风格】的约束。详细设计它的机制、核心爽点以及**限制/代价**。
        2. **力量体系 (Power System)**: 必须定义表现形式（视觉/听觉）、晋升仪式（如何升级）和同级强弱判定标准。
        3. **分卷反派 (Volume Boss)**: 严禁让最终 BOSS 从头跳到尾。**每一卷必须有一个独立的“阶段性反派”**，他在本卷结束时必须被主角击败或解决。
        4. **戏剧引擎 (Dramatic Engine)**: 世界观必须自带冲突发生器，而不只是设定集：
           - 金手指的【限制/代价】必须能制造**道德困境或两难选择**（不只是冷却时间）。
           - 力量体系必须与**人物秘密**挂钩（如：升级会暴露身份/继承死者记忆/引来不可名状的注视）。
           - 最终反派与主角之间必须存在**信息差型羁绊**——读者能先于主角意识到的关联。
        
        【BookPlan 规划要求】
        - **第一卷 (The Hook)**: 必须是“新手村/起源”篇章。目标是获得金手指，解决第一个生存危机。
        - **分卷节奏**: 请根据 {total_chapters} 章的总长度合理切分。如果是 100 章，建议分 3-4 卷。

        【返回格式要求】 (请严格遵守此JSON结构，不要包含Markdown标记)
        {{
            "book_title": "极具吸引力的书名",
            
            "gold_finger": {{
                "name": "金手指名称",
                "type": "SYSTEM / ITEM / MEMORY / BLOODLINE",
                "description": "一句话描述",
                "core_ability": "核心功能 (如: 加点, 抽奖, 模拟未来)",
                "limitations": "使用代价或冷却限制 (必须符合流派设定)",
                "upgrade_route": "简述金手指本身的进化方向"
            }},

            "hero": {{
                "name": "姓名",
                "identity": "开篇身份",
                "appearance": "外貌特征",
                "personality": "性格关键词",
                "core_desire": "核心欲望 (他最想要什么?)",
                "fear": "恐惧之物 (弱点)",
                "speech_style": "说话风格"
            }},
            
            "villain": {{
                "name": "全书最终 BOSS 姓名",
                "identity": "身份 (也就是本书的天花板)",
                "motivation": "最终目的",
                "relation_to_hero": "与主角的深层羁绊"
            }},

            "key_support_roles": [
                {{
                    "name": "配角A",
                    "role_type": "MENTOR / PARTNER / RIVAL",
                    "character_hook": "人物记忆点 (如: 贪财, 洁癖)",
                    "utility": "功能性作用"
                }}
            ],

            "intro": "世界观简介 (200字以内)",
            
            "power_system": {{
                "name": "体系名称",
                "levels": ["L1", "L2", "...", "L9"],
                "visual_effect": "力量释放时的视觉表现 (必须符合流派画风)",
                "promotion_method": "晋升方式",
                "price": "代价 (如果有)"
            }},

            "dramatic_engine": {{
                "ability_paradox": "金手指代价制造的道德困境/两难选择 (如: 吞噬敌人能变强，但会继承其记忆)",
                "secret_hook": "力量体系与主角核心秘密的关联 (如: 升级会在反派眼中亮起标记)",
                "villain_info_gap": "读者能先于主角意识到的反派-主角羁绊 (如: 反派记忆里藏着主角的童年)"
            }},

            "locations": ["新手村", "进阶地图", "核心地图"],

            "book_plan": {{
                "main_story": "全书主线梗概",
                "volumes": [
                    {{
                        "title": "第一卷：卷名",
                        "goal": "本卷剧情主线",
                        "estimated_chapters": 30,
                        "antagonist": {{  <-- 🟢 关键新增：本卷的关底 BOSS
                            "name": "本卷反派姓名",
                            "identity": "身份 (如: 恶霸, 外门长老)",
                            "outcome": "结局 (如: 被主角当众斩杀)"
                        }},
                        "key_events": ["金手指觉醒", "初次冲突", "高潮决战"]
                    }},
                    {{
                        "title": "第二卷：卷名",
                        "goal": "...",
                        "estimated_chapters": 40,
                        "antagonist": {{ "name": "...", "identity": "...", "outcome": "..." }},
                        "key_events": ["..."]
                    }}
                ]
            }}
        }}
        """
        
        
        # 调用 LLM
        response = self.call(prompt, json_mode=True)
        
        # 🟢 增强版 JSON 清洗 (复用 PlannerAgent 的逻辑)
        try:
            # 1. 如果已经是字典，直接返回
            if isinstance(response, dict):
                return response

            # 2. 如果是字符串，用统一工具解析
            if isinstance(response, str):
                result = parse_llm_json(response, default={})
                if result:
                    return result

        except Exception as e:
            print(f"❌ JSON 解析失败: {e}")
            return {}

        return {}

    async def abuild_world_from_constraints(self, constraints: dict, variant: dict,
                                            total_chapters=100, style="男频-热血玄幻",
                                            book_id=None):
        """【Phase 1 新增】基于访谈约束 + 选定方案方向，异步生成完整 Bible"""
        prefix = f"[{book_id}] " if book_id else ""
        print(f"🌍 [WorldBuilder] {prefix}基于约束构建世界 | 风格: {style}...")

        style_constraints = self._get_style_constraints(style)
        constraints_text = json.dumps(constraints, ensure_ascii=False, indent=2) if constraints else "（无）"
        variant_text = json.dumps(variant.get("core_setting", {}), ensure_ascii=False, indent=2) if variant else "（无）"
        variant_seed = variant.get("seed", "") if variant else ""

        prompt = f"""
        用户想要写一本这样的小说：
        【目标风格】{style}
        【预估篇幅】{total_chapters} 章

        【用户访谈得到的创作约束】（必须严格遵守）
        {constraints_text}

        【用户选定的核心设定方向】
        一句话设定: {variant_seed}
        详细设定: {variant_text}

        {style_constraints}

        请设计一个能够支撑起这个篇幅的宏大世界。不仅要设计骨架，更要填充血肉。

        【🚨 核心设计要求 (CRITICAL)】
        1. **金手指 (Gold Finger)**: 必须严格遵守【目标风格】和【用户约束】。详细设计它的机制、核心爽点以及**限制/代价**。
        2. **力量体系 (Power System)**: 必须定义表现形式（视觉/听觉）、晋升仪式（如何升级）和同级强弱判定标准。
        3. **分卷反派 (Volume Boss)**: 严禁让最终 BOSS 从头跳到尾。**每一卷必须有一个独立的"阶段性反派"**，他在本卷结束时必须被主角击败或解决。
        4. **戏剧引擎 (Dramatic Engine)**: 世界观必须自带冲突发生器，而不只是设定集：
           - 金手指的【限制/代价】必须能制造**道德困境或两难选择**。
           - 力量体系必须与**人物秘密**挂钩。
           - 最终反派与主角之间必须存在**信息差型羁绊**。

        【BookPlan 规划要求】
        - **第一卷 (The Hook)**: 必须是"新手村/起源"篇章。目标是获得金手指，解决第一个生存危机。
        - **分卷节奏**: 请根据 {total_chapters} 章的总长度合理切分。如果是 100 章，建议分 3-4 卷。

        【返回格式要求】 (请严格遵守此JSON结构，不要包含Markdown标记)
        {{
            "book_title": "极具吸引力的书名",

            "gold_finger": {{
                "name": "金手指名称",
                "type": "SYSTEM / ITEM / MEMORY / BLOODLINE",
                "description": "一句话描述",
                "core_ability": "核心功能 (如: 加点, 抽奖, 模拟未来)",
                "limitations": "使用代价或冷却限制 (必须符合流派设定)",
                "upgrade_route": "简述金手指本身的进化方向"
            }},

            "hero": {{
                "name": "姓名",
                "identity": "开篇身份",
                "appearance": "外貌特征",
                "personality": "性格关键词",
                "core_desire": "核心欲望 (他最想要什么?)",
                "fear": "恐惧之物 (弱点)",
                "speech_style": "说话风格"
            }},

            "villain": {{
                "name": "全书最终 BOSS 姓名",
                "identity": "身份 (也就是本书的天花板)",
                "motivation": "最终目的",
                "relation_to_hero": "与主角的深层羁绊"
            }},

            "key_support_roles": [
                {{
                    "name": "配角A",
                    "role_type": "MENTOR / PARTNER / RIVAL",
                    "character_hook": "人物记忆点 (如: 贪财, 洁癖)",
                    "utility": "功能性作用"
                }}
            ],

            "intro": "世界观简介 (200字以内)",

            "power_system": {{
                "name": "体系名称",
                "levels": ["L1", "L2", "...", "L9"],
                "visual_effect": "力量释放时的视觉表现 (必须符合流派画风)",
                "promotion_method": "晋升方式",
                "price": "代价 (如果有)"
            }},

            "dramatic_engine": {{
                "ability_paradox": "金手指代价制造的道德困境/两难选择",
                "secret_hook": "力量体系与主角核心秘密的关联",
                "villain_info_gap": "读者能先于主角意识到的反派-主角羁绊"
            }},

            "locations": ["新手村", "进阶地图", "核心地图"],

            "book_plan": {{
                "main_story": "全书主线梗概",
                "volumes": [
                    {{
                        "title": "第一卷：卷名",
                        "goal": "本卷剧情主线",
                        "estimated_chapters": 30,
                        "antagonist": {{
                            "name": "本卷反派姓名",
                            "identity": "身份 (如: 恶霸, 外门长老)",
                            "outcome": "结局 (如: 被主角当众斩杀)"
                        }},
                        "key_events": ["金手指觉醒", "初次冲突", "高潮决战"]
                    }},
                    {{
                        "title": "第二卷：卷名",
                        "goal": "...",
                        "estimated_chapters": 40,
                        "antagonist": {{ "name": "...", "identity": "...", "outcome": "..." }},
                        "key_events": ["..."]
                    }}
                ]
            }}
        }}
        """

        response = await self._acall_with_stage(prompt, stage_override="plan", json_mode=True)

        try:
            if isinstance(response, dict):
                return response
            if isinstance(response, str):
                result = parse_llm_json(response, default={})
                if result:
                    return result
        except Exception as e:
            print(f"❌ JSON 解析失败: {e}")

        raise RuntimeError(
            f"Bible 生成失败：LLM 返回无法解析。原始返回(前200字): {str(response)[:200]}"
        )
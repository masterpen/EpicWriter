import json
import re
import asyncio
from app.agents.base import BaseAgent
from app.core.database import db
from app.core.style_system import get_style_review_prompt


class UnifiedReviewerAgent(BaseAgent):
    """
    合并审核节点：Reviewer + FactChecker + Maintainer
    原本 3 次 LLM 调用 → 1 次调用
    """
    
    def __init__(self):
        super().__init__(
            "你是一个多重角色的审核专家，同时担任：\n"
            "1. 严苛的网文主编（质量审核）\n"
            "2. 严谨的事实核查员（逻辑检查）\n"
            "3. RPG游戏主持人DM（状态管理）",
            stage_key="unified_review"
        )
    
    async def review_and_analyze(
        self, 
        draft: str, 
        outline: dict, 
        chapter_num: int, 
        style: str, 
        book_id: str,
        current_tags_dict: dict = None,
        is_volume_end: bool = False,
        next_vol_title: str = ""
    ) -> dict:
        """
        一次调用完成：
        1. 质量评分 + AI味检测
        2. 事实核查
        3. 状态摘要 + 角色更新
        """
        
        # ===== 异步并行获取 DB 数据 =====
        if current_tags_dict is None:
            current_tags_dict = {}
        
        world_config, hero_state, prev_context = await asyncio.gather(
            asyncio.to_thread(db.get_world_config, book_id),
            asyncio.to_thread(db.get_hero_state, book_id),
            asyncio.to_thread(db.get_volume_context, book_id, chapter_num, count=5) if chapter_num > 1 else asyncio.sleep(0, result="（首章，无历史）"),
        )
        
        # 获取风格审核提示
        style_review = get_style_review_prompt(style)
        
        # 卷收尾指令
        volume_instruction = ""
        if is_volume_end:
            volume_instruction = f"""
            【🚨 特别任务：卷收尾总结】
            本章是本卷的最后一章（第{chapter_num}章）。下一卷标题为【{next_vol_title}】。
            请额外生成一段"卷收尾上下文 (volume_conclusion)"，用于下一卷开篇时帮助 AI 理解前情。
            
            卷收尾总结必须包含：
            1. 本卷核心冲突的最终结果
            2. 主角的关键成长（境界突破、获得关键道具、性格转变）
            3. **未解决的伏笔和悬念**（哪些角色/事件悬而未决？这是最重要的！）
            4. 为下一卷【{next_vol_title}】的自然过渡钩子
            
            请在返回 JSON 中添加 "volume_conclusion" 字段，字数 200 字左右。
            """
        
        prompt = f"""
        任务：完成三项审核任务，返回统一 JSON 结果。

        ============================================
        【任务1：质量评分 (Reviewer)】
        ============================================
        评分标准：
        1. 逻辑连贯 (30%)：剧情有无矛盾
        2. AI味检测 (30%)：句首词重复/书面语对话/情绪标签化/描写模板化/无短句爆发
        3. 完成度 (20%)：是否覆盖大纲关键点
        4. 风格一致性 (20%)：是否符合风格要求

        AI味典型问题（务必逐条检查）：
        - "然而/于是/此刻/只见" 连续使用超过2次 → 扣分
        - 对话用书面语 ("我对你感到失望") → 扣分
        - "他感到XX" 替代了生理反应 → 扣分
        - 环境描写超过2句 → 扣分

        {style_review}

        【大纲】
        {str(outline)[:500]}

        【正文】
        {draft[:3000]}

        ============================================
        【任务2：事实核查 (FactChecker)】
        ============================================
        核查规则 — 严格标准，宁可漏报不可误报：
        1. **仅报硬逻辑矛盾**：主角断臂后双手持刀、已死角色复活、未获得的物品凭空出现。必须引用原文两处明确矛盾的语句才报。
        2. **不报正常发展**：升级、获得新装备新技能、结识新角色，都是正常剧情推进。
        3. **不报叙事选择**：角色采用什么策略、选择哪条路——这些是创作自由，不是逻辑错误。
        4. **不报轻微出入**：数量差1-2个、措辞略有不同，不算冲突。
        5. **不报合理变化**：角色心情变化、策略调整、临时改变计划，不是冲突。
        6. 🚫 **绝对排除以下误报**：
           - "只提供了一种方案/路径" → 叙事选择，非冲突
           - "主角选择了A而非B" → 剧情方向，非冲突
           - 大纲与正文有细节出入 → 以正文为准

        【基础设定库】
        - 主角当前状态：{hero_state}
        - 力量体系：{world_config.get('power_system', '无')}

        【近期剧情 (5章上下文)】
        {prev_context}

        ============================================
        【任务3：状态摘要 (Maintainer)】
        ============================================
        阅读正文，完成：
        1. 撰写150字剧情摘要（包含核心冲突、主角关键行动、结尾悬念）
        2. 提取角色状态变更和新实体

        【已知角色列表】
        {json.dumps(current_tags_dict, ensure_ascii=False)}

        {volume_instruction}

        【新实体捕获规则】
        - 高灵敏度：只要有具体名字且出场，必须提取
        - 排除泛指：忽略没有具体名字的群体或职业
        - 重要度打分：
          5分: 核心金手指、传世神器、关键伏笔信物
          4分: 主角当前阶段的主力武器/强力功法
          3分: 常用工具、重要配角
          2分: 普通消耗品、货币
          1分: 杂物、路人甲

        ============================================
        【返回格式】
        ============================================
        请严格返回以下 JSON 格式：
        {{
            "review": {{
                "score": 75,
                "ai_flavor_score": 65,
                "style_score": 80,
                "comments": "具体问题（引原文句子）",
                "style_issues": "风格不一致的具体问题",
                "suggestions": "3-5条精确修改建议"
            }},
            "fact_check": {{
                "has_conflict": false,
                "conflicts": ["确切的矛盾描述（必须引用原文两句对照）"],
                "penalty_score": 0
            }},
            "maintainer": {{
                "summary": "150字剧情摘要",
                "volume_conclusion": "（仅卷末需要）卷收尾上下文，200字",
                "character_updates": {{
                    "角色名": {{
                        "mental_state": "心理状态",
                        "tags": ["物理/装备特征"]
                    }}
                }},
                "new_entities": [
                    {{
                        "name": "物品或人名",
                        "type": "Item 或 Character",
                        "desc": "简短描述",
                        "owner": "当前持有者",
                        "importance": 1
                    }}
                ]
            }}
        }}

        ⚠️ 如果你不确定是否算冲突 → 返回 has_conflict: false。宁可漏报！
        """
        
        response = await self.acall(prompt, json_mode=True)
        
        # 解析 JSON
        result = self._parse_response(response)
        
        # 计算最终分数（扣除事实核查罚分）
        review_data = result.get("review", {})
        fact_data = result.get("fact_check", {})
        
        score = review_data.get("score", 70)
        penalty = fact_data.get("penalty_score", 0)
        has_conflict = fact_data.get("has_conflict", False)
        
        if has_conflict and penalty > 0:
            score -= penalty
            # 将冲突信息附加到审核意见
            conflicts_desc = " | ".join(fact_data.get("conflicts", []))
            review_data["comments"] = f"【🚨事实逻辑冲突】(扣除{penalty}分): {conflicts_desc}\n【编辑意见】: {review_data.get('comments', '')}"
        
        result["final_score"] = max(score, 0)
        result["review"] = review_data
        
        return result
    
    def _parse_response(self, response: str) -> dict:
        """鲁棒的 JSON 解析"""
        if not response:
            return self._default_result()
        
        # 清理各种包裹格式
        cleaned = response.strip()
        for pattern in [
            r"^```json\s*", r"^```\s*", r"```$",
            r"^'''json\s*", r"^'''\s*", r"'''$",
            r'^"""json\s*', r'^"""\s*', r'"""$'
        ]:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE)
        
        # 中文引号修复
        cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"')
        
        # 尝试直接解析
        try:
            return json.loads(cleaned)
        except:
            pass
        
        # 正则提取第一个 {...}
        try:
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        
        return self._default_result()
    
    def _default_result(self) -> dict:
        """默认结果（解析失败时使用）"""
        return {
            "review": {
                "score": 70,
                "ai_flavor_score": 60,
                "style_score": 70,
                "comments": "JSON解析失败，默认通过",
                "style_issues": "",
                "suggestions": "请人工复核"
            },
            "fact_check": {
                "has_conflict": False,
                "conflicts": [],
                "penalty_score": 0
            },
            "maintainer": {
                "summary": "JSON解析失败，请人工复核",
                "character_updates": {},
                "new_entities": []
            },
            "final_score": 70
        }

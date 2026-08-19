import asyncio
from app.agents.base import BaseAgent
from app.core.json_utils import parse_llm_json

class MaintainerAgent(BaseAgent):
    def __init__(self):
        super().__init__("你是一个跑团/RPG游戏的主持人(DM)。你的任务是管理角色状态卡和世界实体。", stage_key="maintainer")
        
    def analyze_status_change(self, draft, current_tags_dict, is_volume_end=False, next_vol_title="", chapter_num=1, hero_name="主角"):
        print(f"📊 [Maintainer] 正在分析 [{hero_name}] 的状态...")
        
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
        你不仅是数据分析师，更是**负责编纂史册的【记录官】**。
        
        {volume_instruction}
        
        【任务目标】
        阅读以下小说正文，完成核心任务：
        1. 撰写一段**高质量的剧情摘要**（这是下一章生成的重要依据）。
        2. 提取角色的【心理/生理状态】变更和【新事物】。

        【参考：已知的旧角色列表】
        {json.dumps(current_tags_dict, ensure_ascii=False)}
        
        【正文内容】
        {draft[:3500]}
        【分析逻辑】
        1. **状态更新**：更新主角【{hero_name}】的状态标签列表。

        2. **新实体捕获 (高度敏感模式)**：
           - 对比【已知的旧角色列表】，找出文中出现的所有**新名字**。
           - ⚠️ **重要规则**：
             1. **高灵敏度**：只要有具体名字且出场，必须提取。
             2. **排除泛指**：忽略没有具体名字的群体或职业。
             3. **名字去重**：如果文中出现了不在旧列表中的名字，必须提取！
             4. **相似名区分**：只要字不一样，就是两个人。
             5. **低门槛**：只要有具体名字且出场了，都算新角色。
             6. **物品**：文中出现的任何具有具体名称的重要道具、装备或宝物。
        【输出要求】
        请返回 JSON 格式：
        {{
            "summary": "请在此处撰写摘要。要求：包含本章核心冲突、主角的关键行动以及结尾留下的悬念。字数150字左右。",
            "volume_conclusion": "（仅卷末需要）卷收尾上下文，包含未解决伏笔和过渡钩子，200字",
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
                    "owner": "当前持有者名字没有为null",
                    "importance": 1-5
                }}
            ]
        }}
        
        【重要度(importance)打分参考标准】
        - 5分: 核心金手指、传世神器、关键伏笔信物
        - 4分: 主角当前阶段的主力武器/强力功法
        - 3分: 常用工具、重要配角
        - 2分: 普通消耗品、货币
        - 1分: 杂物、路人甲 (默认)
        """
        
        response = self.call(prompt, json_mode=True)

        default = {"summary": "解析错误", "character_updates": {}, "new_entities": []}
        result = parse_llm_json(response, default=default)
        if result is None or result == default:
            print(f"❌ 解析失败: {response}")
        return result

    async def aanalyze_status_change(self, draft, current_tags_dict, is_volume_end=False, next_vol_title="", chapter_num=1, hero_name="主角"):
        """异步版状态分析 — 支持卷收尾总结"""
        print(f"📊 [Maintainer] 正在异步分析 [{hero_name}] 的状态...")
        
        volume_instruction = ""
        if is_volume_end:
            volume_instruction = f"""
            【🚨 特别任务：卷收尾总结】
            本章是本卷的最后一章（第{chapter_num}章）。下一卷标题为【{next_vol_title}】。
            请额外生成一段"卷收尾上下文 (volume_conclusion)"，用于下一卷开篇时帮助 AI 理解前情。
            
            卷收尾总结必须包含：
            1. 本卷核心冲突的最终结果（谁赢了/输了/消失了？）
            2. 主角的关键成长（境界突破、获得关键道具、性格转变）
            3. **未解决的伏笔和悬念**（哪些角色/事件悬而未决？这是最重要的！）
            4. 为下一卷【{next_vol_title}】的自然过渡钩子（主角为什么去下一卷的场景？）

            请在返回 JSON 中添加 "volume_conclusion" 字段，字数 200 字左右。
            """
        
        prompt = f"""
        你不仅是数据分析师，更是**负责编纂史册的【记录官】**。
        
        {volume_instruction}
        
        【任务目标】
        阅读以下小说正文，完成核心任务：
        1. 撰写一段**高质量的剧情摘要**。
        2. 提取角色的【心理/生理状态】变更和【新事物】。

        【参考：已知的旧角色列表】
        {json.dumps(current_tags_dict, ensure_ascii=False)}
        
        【正文内容】
        {draft[:3500]}
        
        【输出要求】
        请返回 JSON 格式：
        {{
            "summary": "摘要，150字左右",
            "volume_conclusion": "（仅卷末需要）卷收尾上下文，包含未解决伏笔和过渡钩子，200字",
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
                    "importance": 1-5
                }}
            ]
        }}
        """
        
        response = await self.acall(prompt, json_mode=True)

        default = {"summary": "解析错误", "character_updates": {}, "new_entities": []}
        result = parse_llm_json(response, default=default)
        if result is None or result == default:
            print(f"❌ 解析失败: {response}")
        return result
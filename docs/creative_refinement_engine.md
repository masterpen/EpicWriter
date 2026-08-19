# Creative Refinement Engine 工程化设计文档

> 状态：设计稿 v2 / 待评审
> 范围：把"一次生成 World Bible"重构为"多轮迭代式创作精炼引擎"
> v2 变更：双闸门→三道闸门；单 Reviewer→Support+Adversarial 双 Reviewer；单方案打分→多方案竞争；绝对分数→状态标识+confidence；新增用户偏好模型与 Reader Simulation 独立维度

---

## 一、设计目标与原则

### 1.1 要解决的根本问题

当前系统假设"用户能提供高质量 Story Bible"，但实际用户只有模糊创意。
`HomePage` 一个 textarea + 一个按钮 → `WorldBuilderAgent.build_world()` 一次 LLM 调用 → 直接入库 Canonical，
中间没有任何质量闸门、没有用户参与、没有迭代。

### 1.2 核心原则

| 原则 | 含义 |
|---|---|
| **选择题优先，填空题兜底** | AI 把复杂创作决策拆成选择题；但每题必须保留"我自己描述"自由输入选项 |
| **三道闸门** | ① 代码硬约束验证 → ② AI 证据式多视角评审 → ③ 用户四选项确认。不追求单一分数 |
| **多方案竞争** | 生成 A/B/C 三套核心设定互相攻击，用户比较选择而非相信 AI 绝对判断 |
| **证据优于分数** | AI 不说"这个设定很好"，而说"为什么认为可行 + 哪里有风险"，附带 confidence |
| **Patch 式修改** | 不全量重写，逐条 Issue → 采用/修改/跳过，避免修 A 破坏 B |
| **Canonical 三重定义** | 通过结构验证 + 经过多视角评审 + 得到作者明确认可的创作事实 |
| **检索式加载** | 写章节时按场景取 Bible 子图，不全量塞 prompt |

### 1.3 AI 的能力边界（设计哲学）

> **AI 可以证明"它为什么认为这个东西可用"，但不能证明"这个东西一定是好作品"。**

因此系统不设 `quality_score > 80 → auto_canonical` 规则。AI 负责可用性判断 + 风险提示，作者负责意图对齐判断，代码负责自洽性验证。"是否好作品"交给作者选择 + 后续真实阅读反馈。

---

## 二、现状分析

### 2.1 当前数据流

```
HomePage (textarea: idea)
   ↓ POST /api/books/genesis
WorldBuilderAgent.build_world()  ← 单次 LLM，json_mode=True
   ↓ world_data (dict)
db.init_book_world(book_id, world_data)
   ↓ 事务化写入 Neo4j
   :Book → :WorldConfig (intro, power_system, power_name)
         → :BookPlan (main_story, volumes, current_volume)
         → :Location, :Character (hero/villain/support)
   ↓ 直接成为 Canonical（无版本、无评审）
```

### 2.2 当前 DB Schema（Neo4j 节点）

| 节点 | 关键字段 | 说明 |
|---|---|---|
| `:Book` | book_id, title, user_id, style, created_at | 无 version 字段 |
| `:WorldConfig` | intro, power_system(JSON str), power_name | 无 status 字段 |
| `:BookPlan` | main_story, volumes(JSON str), current_volume | current_volume 是 mutable 状态字段 |
| `:Character` | name, role(hero/villain/support), ... | 无 arc/motivation 结构化字段 |
| `:Location` | book_id, name | 无层级关系 |

### 2.3 缺口清单

- ❌ 无 Interviewer（用户直接填 idea）
- ❌ 无硬约束验证（时间线/年龄/关系闭环等可程序化矛盾未检查）
- ❌ 无 Critic（生成后无评审）
- ❌ 无 Support/Adversarial 双视角评审
- ❌ 无多方案竞争（单方案打分）
- ❌ 无 Patch Revision（改设定只能全量重写）
- ❌ 无版本管理（无 version/status: draft/canonical）
- ❌ 无 confidence 不确定性标识
- ❌ 无用户偏好模型
- ❌ 无 Reader Simulation 独立维度
- ❌ 无 Retriever（Writer 把 world_config 全量塞 prompt）
- ❌ 无冻结机制（写作中可被偷偷改世界观）

---

## 三、目标架构：四层模型

```
┌─────────────────────────────────────────────────────┐
│ ① Creative Layer（创作精炼层）                       │
│   Creative Interviewer → Multi-Draft Builder         │
│   → 三道闸门: 硬约束验证 / 双视角评审 / 用户确认     │
│   → Patch Revision → Canonical                       │
│   输入：模糊创意  输出：Canonical Bible              │
└──────────────────────────┬──────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────┐
│ ② Story Foundation（故事基建层）                     │
│   Canonical Bible / Character / Plot                 │
│   Version Graph / Retrieval Index / Author Profile   │
└──────────────────────────┬──────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────┐
│ ③ Narrative Engine（叙事引擎层）                     │
│   Planner → Writer → Reviewer → ReaderSim           │
│   （现有 LangGraph workflow，基本保留）              │
└──────────────────────────┬──────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────┐
│ ④ Quality & Memory（质量与记忆层）                   │
│   UnifiedReviewer / Maintainer / ReaderState         │
│   Chapter Archive / Entity Graph / Beta Reader       │
└─────────────────────────────────────────────────────┘
```

---

## 四、核心数据模型

### 4.1 新增/修改的 Neo4j 节点

#### `:BibleVersion`（新增）— 版本化 Story Bible

```cypher
(:Book)-[:HAS_BIBLE_VERSION]->(:BibleVersion {
    book_id: string,
    version: string,           // "v0.1", "v0.2", "v1.0"
    status: string,            // "draft" | "reviewing" | "canonical" | "deprecated"
    created_at: datetime,
    frozen_at: datetime,       // canonical 时写入
    parent_version: string,    // 上一版本号，形成版本链
    bible_data: string,        // 完整 Bible JSON
    structural_check: string,  // 硬约束验证结果 JSON (pass/fail + violations)
    support_review: string,    // Support Reviewer 证据 JSON
    adversarial_review: string, // Adversarial Reviewer 风险 JSON
    final_evaluation: string,  // Final Evaluator 综合 JSON (含 confidence)
    patch_log: string,         // 已应用的 Patch 列表 JSON
    author_alignment: string   // "unknown" | "aligned" | "misaligned" (由用户行为推断)
})
```

**版本状态机**：
```
draft → structural_check_failed → draft            [代码验证不过，直接回炉]
      → structural_check_passed → reviewing        [进入双视角评审]
reviewing → evaluated → (confidence 高) awaiting_user   [可快速确认]
                         → (confidence 低) awaiting_user_focus [要求重点审查]
awaiting_user → (采用) canonical                    [冻结]
              → (局部修改) draft + patch            [回炉带 patch]
              → (换方案) draft                      [回炉换 seed]
              → (不采用) deprecated                 [废弃]
canonical → (用户提议修改) reviewing                 [解冻走变更流程]
旧 canonical → 新 canonical 后 → deprecated         [归档]
```

#### `:BibleVariant`（新增）— 多方案竞争的备选方案

```cypher
(:BibleVersion)-[:HAS_VARIANT]->(:BibleVariant {
    variant_id: string,
    book_id: string,
    parent_version: string,    // 所属 draft 版本
    label: string,             // "A" | "B" | "C"
    seed: string,              // 核心设定一句话
    variant_data: string,      // 该方案 Bible JSON
    cross_attack: string,      // 被其他方案攻击的弱点 JSON
    self_defense: string,      // 对攻击的辩护 JSON
    scores: string,            // 多维度评估 JSON（含 confidence）
    user_decision: string      // "pending" | "chosen" | "rejected" | "merged"
})
```

#### `:InterviewSession`（新增）— 访谈会话

```cypher
(:Book)-[:HAS_INTERVIEW]->(:InterviewSession {
    session_id: string,
    book_id: string,
    status: string,            // "active" | "completed" | "abandoned"
    started_at: datetime,
    completed_at: datetime,
    collected_constraints: string,  // 已收集的结构化约束 JSON
    question_history: string,       // 已问问题 + 用户回答 JSON
    current_topic: string
})
```

#### `:BiblePatch`（新增）— 单条修改提议

```cypher
(:BibleVersion)-[:HAS_PATCH]->(:BiblePatch {
    patch_id: string,
    book_id: string,
    version: string,
    source: string,            // "structural" | "support" | "adversarial" | "user" | "variant_merge"
    issue_id: string,
    category: string,          // completeness/coherence/originality/writability/longevity/structure
    severity: string,          // "high" | "medium" | "low"
    description: string,
    suggested_change: string,  // 结构化 JSON diff
    target_field: string,
    decision: string,          // "pending" | "accepted" | "modified" | "skipped"
    user_modified_content: string
})
```

#### `:AuthorProfile`（新增）— 用户偏好模型

```cypher
(:User)-[:HAS_AUTHOR_PROFILE]->(:AuthorProfile {
    user_id: string,
    updated_at: datetime,
    likes: string,             // 倾向的母题/风格 JSON（如 ["复杂阴谋","灰度角色","慢揭示","反套路"]）
    dislikes: string,          // 拒绝的母题 JSON（如 ["模板升级","单纯打脸","无脑爽点"]）
    decision_history: string,  // 历次方案选择记录 JSON（用于持续学习）
    sample_size: int           // 样本数（<20 时标记为"偏好未成熟"）
})
```

### 4.2 现有节点的向后兼容

- `:WorldConfig` / `:BookPlan` / `:Character` / `:Location` **保留不动**
- Canonical 冻结时，把 `:BibleVersion.bible_data` 同步投影到这些节点
- 写作时 Writer 仍从这些节点读，无需改动 ③ 层代码

---

## 五、Creative Interviewer 访谈层

### 5.1 Agent 定义

```python
# app/agents/creative_interviewer.py（新增）
class CreativeInterviewerAgent(BaseAgent):
    stage_key = "interview"

    async def astart_session(self, raw_idea: str) -> InterviewQuestion:
        """启动访谈，返回第一个问题"""

    async def anext_question(self, session_id: str, answer: InterviewAnswer) -> InterviewQuestion | None:
        """根据用户回答，返回下一个问题或 None（访谈完成）"""

    async def abuild_constraints(self, session_id: str) -> dict:
        """访谈结束后，把收集到的答案结构化为创作约束 dict"""
```

### 5.2 问题结构

```typescript
interface InterviewQuestion {
    question_id: string;
    topic: string;
    question: string;
    options: InterviewOption[];
    allow_free_input: true; // 🟢 硬约束：永远允许自由输入
    rationale: string;
}

interface InterviewOption {
    label: string;
    value: string;
    implication: string;
    potential_score?: number; // 1-5 商业/爽文潜力预估
}
// 最后一个 option 永远是：
// { label: "我自己描述", value: "__free_input__" }
```

### 5.3 访谈状态机

```
START → topic_routing(根据已收集约束 + AuthorProfile 决定下一个主题)
   ↓
generate_question(LLM 生成问题 + 3 个选项 + 1 个自由输入)
   ↓
user_answer(选择 / 自由输入 / 跳过)
   ↓
update_constraints(把答案写入 collected_constraints)
   ↓ 同时记录到 :AuthorProfile.decision_history（为偏好建模积累样本）
check_completion(覆盖度 ≥ 阈值？)
   ↓ 否 → 回到 topic_routing
   ↓ 是 → build_constraints → 访谈结束
```

**主题清单**（按优先级）：
1. 核心爽点类型（升级/逆袭/装逼/复仇/探索）
2. 主角开局处境
3. 金手指本质
4. 金手指限制（代价——制造道德困境）
5. 世界规则核心
6. 最终反派与主角的羁绊（信息差型）
7. 第一卷核心冲突
8. 长篇升级空间

**AuthorProfile 注入**：当 `sample_size ≥ 20` 时，访谈问题会主动避开用户 dislike 的母题，并在选项 implication 中标注"与你历史偏好匹配度"。

---

## 六、多方案竞争机制（新增）

### 6.1 为什么不用单方案打分

单方案打分让用户被迫相信 AI 的绝对判断（"87 分就是好"）。多方案竞争让用户在**比较**中判断，AI 只负责给出每个方案的证据和风险，不结论"哪个最好"。

### 6.2 Multi-Draft Builder

```python
# app/agents/multi_draft_builder.py（新增）
class MultiDraftBuilderAgent(BaseAgent):
    stage_key = "multi_draft"

    async def agenerate_variants(self, constraints: dict, n: int = 3) -> list[BibleVariant]:
        """
        基于 constraints 生成 n 套核心设定（A/B/C），每套在关键母题上做差异化。
        例如 A=复仇流、B=悬疑流、C=反转流。
        """

    async def across_attack(self, variants: list[BibleVariant]) -> list[BibleVariant]:
        """
        让每套方案互相攻击：A 攻击 B/C 的弱点，B 攻击 A/C，C 攻击 A/B。
        每套方案同时被攻击 + 自我辩护。
        """
```

### 6.3 竞争流程

```
constraints
   ↓
agenerate_variants → A / B / C 三套核心设定
   ↓
across_attack → 每套得到 cross_attack（弱点）+ self_defense（辩护）
   ↓
final_evaluate → 每套得到多维度评估（含 confidence）
   ↓
展示给用户比较：
   ┌─────────────────────────────────────┐
   │ 方案 A: 主角被家族废掉              │
   │ 商业可读性: 高   创新性: 中         │
   │ 长线空间: 中     独特性: ⚠️ 偏低    │
   │ 弱点: "天赋被废→崛起"属高频母题     │
   │ 辩护: 本作加入"代价是继承死者记忆"  │
   │ 与你历史偏好匹配度: 78%             │
   ├─────────────────────────────────────┤
   │ 方案 B: 主角自己封印力量            │
   │ ...                                 │
   ├─────────────────────────────────────┤
   │ 方案 C: 整个世界认为主角已死        │
   │ ...                                 │
   └─────────────────────────────────────┘
   ↓
用户决策（四选项）：
   [✅ 采用 A]  [🔀 融合 A+B]  [🔄 全部重新生成]  [✏️ 自由调整]
```

### 6.4 方案融合

用户选"融合 A+B"时：
- 提取 A 和 B 的核心设定
- 让 LLM 做一次**定向融合**（只融合，不重写其他部分）
- 融合后作为新 draft 进入三道闸门

---

## 七、三道闸门（核心）

```
Draft (来自 multi_draft 单方案选定 / 融合 / freeform 生成)
   ↓
① 硬约束验证（代码，无 LLM）
   ↓ pass
② AI 多视角评审（Support + Adversarial + Final Evaluator）
   ↓
③ 用户确认（四选项，非简单"通过"）
   ↓
Canonical
```

### 7.1 第一层：硬约束验证（Structural Validator）

**完全不用 LLM**，纯代码验证。检查可程序化发现的矛盾。

```python
# app/core/bible_validator.py（新增）
class BibleValidator:
    def validate(self, bible_data: dict) -> StructuralCheckResult:
        checks = [
            self._check_timeline,        # 时间线一致性
            self._check_ages,            # 年龄与事件时间不冲突
            self._check_relation_closure, # 人物关系闭环（A是B师父，B不能同时是A师父）
            self._check_power_continuum, # 力量体系无断层（L1→L3 缺 L2）
            self._check_locations_exist, # 事件引用的地点在 locations 列表中
            self._check_required_fields, # 关键设定字段无缺失
            self._check_volume_chapters, # 分卷章数之和 ≈ total_chapters
        ]
        violations = []
        for check in checks:
            violations.extend(check(bible_data))
        return StructuralCheckResult(passed=len(violations)==0, violations=violations)
```

**示例检查**：
```
角色A: 25岁
事件X: 角色A 20岁时发生
事件X距今: 8年
→ 25 - 8 = 17 ≠ 20  ❌ 时间线冲突
```

```
力量体系 levels: [L1, L2, L4, L5]
→ L3 缺失  ❌ 力量断层
```

**失败处理**：硬约束失败不进入 AI 评审，直接生成对应 Patch 回炉。这类问题交给 AI 是浪费 token 且不可靠。

### 7.2 第二层：AI 多视角评审（Support + Adversarial + Final Evaluator）

#### 7.2.1 Support Reviewer（寻找"哪里成立"）

```python
# app/agents/bible_reviewers.py（新增）
class SupportReviewerAgent(BaseAgent):
    stage_key = "bible_support"
    async def areview(self, bible_data: dict, constraints: dict) -> SupportReview:
        """
        寻找设定中成立、有潜力、可写的部分。
        输出证据（evidence）而非"好/坏"判断。
        """
```

输出结构：
```json
{
  "strengths": [
    {
      "field": "dramatic_engine.ability_paradox",
      "evidence": "吞噬敌人继承记忆制造了明确的道德困境，可支撑长期剧情",
      "impact": "high"
    }
  ],
  "writability_evidence": [
    "金手指机制清晰，前5章可直接围绕首次吞噬展开"
  ]
}
```

#### 7.2.2 Adversarial Reviewer（专门找"为什么可能很差"）

```python
class AdversarialReviewerAgent(BaseAgent):
    stage_key = "bible_adversarial"
    async def areview(self, bible_data: dict, constraints: dict) -> AdversarialReview:
        """
        专门寻找设定的弱点、套路化、长线风险。
        不输出"好/坏"，只输出 risks + 反例。
        """
```

输出结构：
```json
{
  "risks": [
    {
      "field": "hero.backstory",
      "risk": "天赋被废→重新崛起 属高频网文母题，当前版本未证明其独特性",
      "severity": "high",
      "counter_example": "若无额外机制，读者可能难以区分本作与同类作品"
    }
  ],
  "originality_challenges": [
    "当前金手指'加点'机制与 X 作品高度雷同"
  ],
  "long_term_risks": [
    "第一卷矛盾解决后，缺乏更大的升级空间"
  ]
}
```

#### 7.2.3 Final Evaluator（综合 + confidence）

```python
class FinalEvaluatorAgent(BaseAgent):
    stage_key = "bible_evaluate"
    async def aevaluate(self, bible_data: dict, support: SupportReview, adversarial: AdversarialReview) -> FinalEvaluation:
        """
        综合 Support + Adversarial，输出状态标识 + confidence。
        不输出"质量分 87"这种伪精确数字。
        """
```

输出结构：
```typescript
interface FinalEvaluation {
    criteria: {
        structural_validity:    Status; // ✅ pass / ⚠️ warn / ❌ fail
        consistency:            Status;
        conflict_potential:     Status;
        long_term_scalability:  Status;
        originality:            Status;
        author_alignment:       "unknown" | "aligned" | "misaligned";
    };
    confidence: number;        // 0-1，AI 对自身判断的置信度
    conclusion: string;        // "当前版本可进入作者审阅" / "建议重点修改 originality"
    recommended_action: "quick_confirm" | "focus_review" | "revise" | "major_rework";
}
```

**confidence 的作用**（关键）：
```
状态全 ✅ + confidence ≥ 0.7 → quick_confirm（用户可快速确认）
状态全 ✅ + confidence < 0.7 → focus_review（要求用户重点审查，AI 不替用户拍板）
状态有 ⚠️                   → revise（建议修改，生成 Patch）
状态有 ❌                   → major_rework（重大重做，可能换方案）
```

### 7.3 第三层：用户确认（四选项，非简单"通过"）

```text
┌──────────────────────────────────────────────────┐
│ Story Bible · v0.2 · 待作者确认                  │
├──────────────────────────────────────────────────┤
│ 结构验证: ✅ 通过                                 │
│ 一致性:   ✅ 通过                                 │
│ 冲突潜力: ✅ 通过                                 │
│ 长线空间: ⚠️ 第一卷后升级空间偏弱                 │
│ 独特性:   ⚠️ "天赋被废"母题较常见                 │
│ 作者对齐: ❓ 偏好样本不足，无法判断               │
│                                                  │
│ AI 结论: "当前版本可进入作者审阅"                 │
│ Confidence: 0.62（建议重点审查独特性）            │
│                                                  │
│ Support 证据: ...                                │
│ Adversarial 风险: ...                            │
├──────────────────────────────────────────────────┤
│ [✅ 采用并冻结]                                   │
│ [✏️ 局部修改后采用]（触发 Patch 流程）            │
│ [🔄 换一个方案]（回 multi_draft 重选）            │
│ [❌ 不采用]（废弃，重新访谈或自由输入）           │
└──────────────────────────────────────────────────┘
```

**为什么不能简单"通过"**：用户会机械点击。四选项强制用户做真实判断，尤其"换一个方案"覆盖了 AI 无法感知的"这不是我想写的"情况。

### 7.4 状态标识替代绝对分数

不用 `Quality Score = 87`，用：

```
┌──────────────────────────┐
│ Structural Validity      │ ✅
│ Consistency              │ ✅
│ Conflict Potential       │ ✅
│ Long-term Scalability    │ ⚠️
│ Originality              │ ⚠️
│ Author Alignment         │ ❓
└──────────────────────────┘
```

AI 结论是**行为建议**（"可进入作者审阅"），而非**质量宣判**（"87 分，好作品"）。

---

## 八、Patch Revision 流程

### 8.1 Patch 来源

- 硬约束验证失败 → 自动生成 structural Patch
- Adversarial Reviewer 发现风险 → 生成建议 Patch
- 用户选"局部修改" → 用户自定义 Patch
- 多方案融合 → variant_merge Patch

### 8.2 Patch 流程

```
收集所有 pending Patch
   ↓
逐条展示给用户：
   [采用] [修改后采用] [跳过] [查看增强方案]
   ↓
用户决策 → 写入 :BiblePatch(decision=...)
   ↓
BibleReviser 应用所有 accepted/modified 的 Patch → Bible v(n+1)
   ↓
回到三道闸门（最多 N 轮，默认 3 轮）
   ↓
通过三道闸门 → Canonical
```

### 8.3 BibleReviserAgent

```python
# app/agents/bible_reviser.py（新增）
class BibleReviserAgent(BaseAgent):
    stage_key = "bible_revise"

    async def aapply_patches(self, bible_data: dict, patches: list[BiblePatch]) -> dict:
        """
        只改 Patch 涉及字段，其余原样保留（Patch 式，非全量重写）。
        应用后触发局部 consistency_check（只检查改动字段是否与现有字段冲突）。
        """
```

**实现要点**：
- 不调用 LLM 全量重写 Bible
- 对 accepted patch：按 `target_field` 路径直接写入
- 对 enhancement_alternatives：用户选定后作为新 patch 应用
- 应用后局部 consistency_check（一次轻量 LLM 调用，只检查改动字段）

---

## 九、用户偏好模型（AuthorProfile）

### 9.1 数据来源

每次用户在以下场景的选择都记录到 `:AuthorProfile.decision_history`：
- 访谈中选了哪个选项 / 跳过了哪个主题
- 多方案竞争中选了 A/B/C/融合
- 用户确认时选了采用/局部修改/换方案/不采用
- Patch 决策中采用 vs 跳过的比例

### 9.2 偏好推断

```python
# app/core/author_profile.py（新增）
class AuthorProfileManager:
    def update_profile(self, user_id: str, decision: DecisionEvent):
        """记录决策事件，累积样本"""

    def infer_preferences(self, user_id: str) -> Preferences:
        """
        当 sample_size ≥ 20 时，从历史决策推断 likes/dislikes。
        < 20 时标记"偏好未成熟"，不注入访谈。
        """

    def inject_into_interview(self, user_id: str) -> dict | None:
        """把偏好注入访谈 prompt，让 AI 避开 dislikes，匹配 likes"""
```

### 9.3 Author Alignment 判断

在 Final Evaluator 的 `author_alignment` 字段：
- `unknown`：sample_size < 20，无法判断
- `aligned`：当前 Bible 的母题与用户 likes 匹配度高
- `misaligned`：当前 Bible 触发了用户 dislikes

**注意**：misaligned 不阻止 Canonical，但会高亮提示用户"这与你的历史偏好不符，确认要写这个方向吗？"

---

## 十、Reader Simulation 独立维度

### 10.1 为什么独立

"作者喜欢" ≠ "读者可能喜欢"。作者可能想写反套路小众作品，但商业上需要知道读者接受度。两个维度分开评估，不互相覆盖。

### 10.2 Beta Reader Agent

```python
# app/agents/beta_reader.py（新增）
class BetaReaderAgent(BaseAgent):
    stage_key = "beta_reader"

    async def asimulate_readers(self, bible_data: dict) -> ReaderFeedback:
        """
        模拟多类读者（爽文党/剧情党/考据党/女主党）对 Bible 的反应。
        输出每类读者的追读意愿 + 担忧点。
        """
```

输出：
```json
{
  "reader_segments": [
    {"segment": "爽文党", "read_willingness": 4.2, "worry": "前期压抑期过长"},
    {"segment": "剧情党", "read_willingness": 4.8, "worry": "无明显担忧"},
    {"segment": "考据党", "read_willingness": 3.5, "worry": "力量体系有断层"}
  ],
  "overall_market_potential": "medium"
}
```

**与 AuthorProfile 的关系**：Beta Reader 评估"读者可能喜欢什么"，AuthorProfile 评估"作者喜欢什么"。两者都不结论"好作品"，只提供证据供用户决策。

---

## 十一、Canonical 冻结与版本管理

### 11.1 Canonical 的定义（重构）

> **Canonical = 通过结构验证 + 经过多视角评审 + 得到作者明确认可的创作事实。**

不是"AI 认为好的东西"，不是"分数大于阈值的东西"。

### 11.2 冻结流程

```
Bible v0.3 (通过三道闸门 + 用户采用)
   ↓
freeze_bible(book_id, version)
   ↓
1. :BibleVersion.status = "canonical", frozen_at = now()
2. 把 bible_data 投影到 :WorldConfig / :BookPlan / :Character / :Location
3. 旧 canonical 版本（若有）status = "deprecated"
4. 建立 :BibleVersion 版本链（parent_version）
5. 触发 Retriever 索引构建
6. 记录本次决策到 :AuthorProfile（持续学习）
```

### 11.3 Canonical 后的变更流程（解冻）

```
用户/Writer 发现需要改设定
   ↓
提议变更（描述要改什么、为什么）
   ↓
ImpactAnalyzer 分析影响范围（哪些已写章节受影响？哪些角色/剧情冲突？）
   ↓
用户确认是否接受影响
   ↓ 接受
基于当前 canonical 创建新 draft（复制 + 应用变更）
   ↓
走三道闸门
   ↓
新版本冻结，旧版本 deprecated
```

### 11.4 防止 Writer 偷偷改世界观

- Writer prompt 只注入 Canonical Bible 的**检索子图**（见第十二节）
- Writer 无写权限到 `:BibleVersion` / `:WorldConfig` / `:Character` 定义节点
- Writer 只能写 `:Chapter` / `:Entity`（章节内新实体，需 Maintainer 审核后才入图）
- 若 Writer 输出与 Canonical 冲突，Reviewer 标记为 `canon_violation` 触发重写

---

## 十二、Retriever 检索式动态加载

### 12.1 BibleRetriever

```python
# app/core/bible_retriever.py（新增）
class BibleRetriever:
    def retrieve_for_scene(self, book_id: str, scene_context: dict) -> dict:
        """
        根据当前场景需求，从 Canonical Bible 取相关子图。
        """
```

### 12.2 检索策略

| Bible 部分 | 全量加载 | 按需检索 |
|---|---|---|
| 世界观 intro（200字） | ✅ | - |
| 力量体系总览 | ✅ | - |
| 主角当前等级细节 | - | ✅ 当前等级 + 下一级 |
| 全部 NPC | - | ✅ 场景涉及 + 最近出场 |
| 全部地点 | - | ✅ 当前场景地点 |
| 全部卷规划 | - | ✅ 当前卷 + 下一卷摘要 |
| 分卷反派 | - | ✅ 当前卷反派 + 全局反派（按进度模糊化） |
| 金手指规则 | ✅ 核心机制 | ✅ 当前等级可用能力 |

**预估 token 节省**：100 章小说后期，全量约 8k-12k tokens，检索后约 2k-3k tokens。

---

## 十三、API 契约

### 13.1 访谈相关

```
POST   /api/books/interview/start
       body: { raw_idea: string, style: string }
       resp: { session_id: string, book_id: string, first_question: InterviewQuestion }

POST   /api/books/interview/{session_id}/answer
       body: { question_id: string, answer: { option_value?: string, free_input?: string } }
       resp: { next_question: InterviewQuestion | null, progress: number }

POST   /api/books/interview/{session_id}/complete
       resp: { constraints: dict, suggested_next: "generate_draft" }

POST   /api/books/interview/{session_id}/skip
       body: { reason?: string }
       resp: { next_question: InterviewQuestion | null }
```

### 13.2 多方案竞争

```
POST   /api/books/{book_id}/bible/variants/generate
       body: { constraints: dict, n?: int }
       resp: { variants: [BibleVariant with cross_attack + scores] }

POST   /api/books/{book_id}/bible/variants/decide
       body: { decision: "choose" | "merge" | "regenerate" | "freeform", chosen?: "A"|"B"|"C", merge?: ["A","B"], freeform_data?: dict }
       resp: { draft_version: string, next: "triple_gate" }
```

### 13.3 三道闸门 + Bible 迭代

```
POST   /api/books/{book_id}/bible/{version}/validate       # 闸门① 硬约束验证
       resp: { structural_check: StructuralCheckResult }

POST   /api/books/{book_id}/bible/{version}/review         # 闸门② 双视角评审
       resp: { support, adversarial, final_evaluation }

POST   /api/books/{book_id}/bible/{version}/patches/decide # 闸门③ + Patch
       body: { patches: [{ patch_id, decision, user_modified_content? }], confirm_action: "adopt"|"modify"|"switch"|"reject" }
       resp: { new_version: string | canonical_version: string | abandoned: true }

GET    /api/books/{book_id}/bible/versions
GET    /api/books/{book_id}/bible/{version}

POST   /api/books/{book_id}/bible/{version}/freeze
POST   /api/books/{book_id}/bible/canonical/change
       body: { description: string, target_field: string }
       resp: { impact_analysis: dict, proposed_version: string }

GET    /api/users/me/author-profile                         # 偏好模型
POST   /api/books/{book_id}/bible/{version}/beta-read       # Reader Simulation
```

### 13.4 向后兼容

- `POST /api/books/genesis` **保留**，内部改为：`interview(freeform) → multi_draft(n=1) → 三道闸门(auto-adopt) → freeze`
- `GET /api/books/{book_id}/world` 仍返回投影后的 WorldConfig
- `GET /api/books/{book_id}/plan` 同上

---

## 十四、前端 UI 设计

### 14.1 CreativeInterviewPage（访谈）

```
┌─────────────────────────────────────────┐
│  创作访谈 · 把你的想法变成可写的故事      │
├─────────────────────────────────────────┤
│  进度: ▓▓▓▓▓░░░░ 5/8 主题               │
│  📌 主题: 主角开局处境                   │
│  Q: 主角为什么惨？                       │
│  理由: 这决定了第一卷的核心情绪基调       │
│  ┌─────────────────────────────────┐    │
│  │ A. 家族被灭    复仇流 ★★★★       │    │
│  │ B. 天赋被废    逆袭流 ★★★★★      │    │
│  │ C. 被宗门驱逐  打脸流 ★★★         │    │
│  │ D. 我自己描述                    │    │
│  │ [_____________________________] │    │
│  └─────────────────────────────────┘    │
│  [跳过此题]          [够了，开始生成]    │
└─────────────────────────────────────────┘
```

### 14.2 VariantComparePage（多方案竞争）

```
┌──────────────────────────────────────────────────┐
│  选择核心设定方向 · 三套方案比较                  │
├──────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐             │
│ │ 方案 A  │ │ 方案 B  │ │ 方案 C  │             │
│ │ 被家族废│ │自封力量 │ │世界认为 │             │
│ │         │ │         │ │主角已死 │             │
│ │商业:高  │ │商业:高  │ │商业:中  │             │
│ │创新:中⚠│ │创新:较高│ │创新:高  │             │
│ │长线:中  │ │长线:高  │ │长线:高  │             │
│ │偏好匹配 │ │偏好匹配 │ │偏好匹配 │             │
│ │  78%    │ │  85%    │ │  62%    │             │
│ ├─────────┤ ├─────────┤ ├─────────┤             │
│ │弱点:    │ │弱点:    │ │弱点:    │             │
│ │高频母题 │ │前期压抑 │ │开头复杂 │             │
│ │辩护:... │ │辩护:... │ │辩护:... │             │
│ └─────────┘ └─────────┘ └─────────┘             │
├──────────────────────────────────────────────────┤
│ [✅ 采用 A] [🔀 融合 A+B] [🔄 重新生成] [✏️ 自由]│
└──────────────────────────────────────────────────┘
```

### 14.3 TripleGateReviewPage（三道闸门）

```
┌──────────────────────────────────────────────────┐
│ Story Bible · v0.2 · 待作者确认                  │
├──────────────────────────────────────────────────┤
│ ① 结构验证                                        │
│    Structural Validity ✅                        │
│    Consistency ✅                                │
│    Power Continuum ✅                            │
├──────────────────────────────────────────────────┤
│ ② AI 多视角评审                                   │
│    Support 证据: ...（展开）                      │
│    Adversarial 风险: ...（展开）                  │
│                                                  │
│    Conflict Potential ✅                         │
│    Long-term Scalability ⚠️ 第一卷后偏弱         │
│    Originality ⚠️ "天赋被废"母题较常见           │
│    Author Alignment ❓ 偏好样本不足               │
│    Confidence: 0.62                              │
│    AI 结论: "当前版本可进入作者审阅"              │
├──────────────────────────────────────────────────┤
│ ③ 用户确认                                        │
│    [✅ 采用并冻结]                                │
│    [✏️ 局部修改后采用]（触发 Patch 流程）         │
│    [🔄 换一个方案]（回 multi_draft 重选）         │
│    [❌ 不采用]（废弃，重新访谈或自由输入）        │
├──────────────────────────────────────────────────┤
│ 📖 Beta Reader 预览（可选）                       │
│    爽文党: 4.2/5  剧情党: 4.8/5  考据党: 3.5/5  │
└──────────────────────────────────────────────────┘
```

### 14.4 HomePage 改造

保留现有表单作为"快速模式"，新增入口：

```
[⚡ 快速创世纪]  [🎯 创作访谈（推荐）]
   ↓ 老流程         ↓ 新流程（访谈→多方案→三道闸门）
   genesis API      跳转 CreativeInterviewPage
```

---

## 十五、分阶段落地路线图

### Phase 1：访谈层 + 多方案竞争（MVP）

**目标**：用户从"填空"变成"做选择 + 比较方案"

**工作项**：
1. 新增 `app/agents/creative_interviewer.py`
2. 新增 `app/agents/multi_draft_builder.py`
3. 新增 `interview` / `multi_draft` prompt stage
4. 新增 `:InterviewSession` / `:BibleVariant` 节点 + DB 方法
5. 新增访谈 + 多方案 API 端点
6. 新增前端 `CreativeInterviewPage` + `VariantComparePage`
7. HomePage 加"创作访谈"入口

### Phase 2：三道闸门（质量保障核心）

**目标**：代码验证 + 双视角评审 + 用户四选项确认

**工作项**：
1. 新增 `app/core/bible_validator.py`（硬约束，无 LLM）
2. 新增 `app/agents/bible_reviewers.py`（Support + Adversarial + FinalEvaluator）
3. 新增 `app/agents/bible_reviser.py`（Patch 应用）
4. 新增对应 prompt stage
5. 新增 `:BibleVersion` / `:BiblePatch` 节点 + DB 方法
6. 新增三道闸门 API 端点
7. 新增前端 `TripleGateReviewPage`

### Phase 3：Canonical 冻结 + 版本管理

**目标**：版本化 + 冻结 + 变更流程

**工作项**：
1. `freeze_bible` 实现 + 投影到现有节点
2. 版本链管理
3. Canonical 变更流程 + ImpactAnalyzer
4. 前端版本历史 UI

### Phase 4：AuthorProfile + Beta Reader

**目标**：个性化偏好 + 读者维度独立评估

**工作项**：
1. 新增 `:AuthorProfile` 节点 + `AuthorProfileManager`
2. 访谈/评审注入偏好
3. 新增 `app/agents/beta_reader.py`
4. 前端展示偏好匹配度 + Beta Reader 预览

### Phase 5：Retriever 检索加载

**目标**：Writer 按场景取 Bible 子图

**工作项**：
1. 新增 `app/core/bible_retriever.py`
2. 改造 Writer prompt 构建
3. 索引构建（freeze 时触发）

### Phase 6：扩展到 Character / Plot / Outline

**目标**：Generate→Critique→Refine 模式推广

---

## 十六、风险与决策点

| 风险 | 影响 | 缓解 |
|---|---|---|
| 访谈轮次过多用户烦 | 流失率 | 默认 8 题上限 + 随时"够了开始生成" + 跳过 |
| 硬约束验证误报 | 阻断正常流程 | 误报时允许用户标记"忽略"并记录 |
| Adversarial Reviewer 过度挑刺 | 用户疲劳 | severity 分级，只对 high 强制展示 |
| 多方案生成成本高（3 倍 LLM） | 成本/延迟 | 并行生成 + 跨攻击用轻量模型 |
| AuthorProfile 样本不足时误导 | 偏好注入反效果 | sample_size < 20 时不注入 |
| Canonical 变更影响已写章节 | 剧情矛盾 | ImpactAnalyzer 必须列出受影响章节 |
| Beta Reader 评估偏差 | 误导商业判断 | 仅作参考维度，不参与 Canonical 闸门 |

### 待用户确认的决策点

1. **多方案数量**：默认 A/B/C 3 套，是否合适？（成本 3 倍 LLM）
2. **硬约束验证规则清单**：除了时间线/年龄/关系闭环/力量断层/地点存在/必填字段，还要加什么？
3. **confidence 阈值**：quick_confirm 阈值 0.7 是否合理？
4. **最大迭代轮数**：三道闸门最多 3 轮，够不够？
5. **AuthorProfile 注入时机**：sample_size ≥ 20 才注入，阈值是否合适？
6. **Canonical 变更权限**：写作过程中完全禁止，还是允许但有影响分析？
7. **Beta Reader 读者分群**：默认爽文党/剧情党/考据党/女主党 4 类，是否调整？

---

## 附录：文件改动清单（按 Phase）

### Phase 1 新增/修改
```
新增:
  app/agents/creative_interviewer.py
  app/agents/multi_draft_builder.py
  src/pages/CreativeInterviewPage.tsx
  src/pages/VariantComparePage.tsx
修改:
  app/core/prompt_config.py          (+interview/multi_draft stage)
  app/core/database.py               (+InterviewSession/BibleVariant 方法)
  app/agents/world_builder.py        (接受 constraints)
  api/routers/books.py               (+interview/variants 端点)
  src/lib/api.ts
  src/pages/HomePage.tsx
```

### Phase 2 新增/修改
```
新增:
  app/core/bible_validator.py
  app/agents/bible_reviewers.py
  app/agents/bible_reviser.py
  src/pages/TripleGateReviewPage.tsx
修改:
  app/core/prompt_config.py          (+bible_support/adversarial/evaluate/revise stage)
  app/core/database.py               (+BibleVersion/BiblePatch 方法)
  api/routers/bible.py               (新建)
  src/lib/api.ts
```

### Phase 3-5 新增/修改
```
新增:
  app/core/bible_retriever.py
  app/core/author_profile.py
  app/agents/impact_analyzer.py
  app/agents/beta_reader.py
修改:
  app/core/database.py               (+freeze/version/AuthorProfile 方法)
  app/agents/core.py (Writer)        (prompt 改用 Retriever)
  api/routers/bible.py
  api/routers/users.py               (+author-profile 端点)
```

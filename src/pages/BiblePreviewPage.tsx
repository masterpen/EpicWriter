import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Navigation } from '@/components/ui/Navigation';
import {
  CheckCircle2, AlertTriangle, ArrowRight, ArrowLeft,
  BookOpen, Sparkles, ShieldCheck, Eye, ChevronDown, ChevronUp, Hammer
} from 'lucide-react';

interface DraftData {
  book_title?: string;
  intro?: string;
  gold_finger?: { name?: string; type?: string; description?: string; core_ability?: string; limitations?: string; upgrade_route?: string };
  hero?: { name?: string; identity?: string; appearance?: string; personality?: string; core_desire?: string; fear?: string; speech_style?: string };
  villain?: { name?: string; identity?: string; motivation?: string; relation_to_hero?: string };
  key_support_roles?: { name?: string; role_type?: string; character_hook?: string; utility?: string }[];
  power_system?: { name?: string; levels?: string[]; visual_effect?: string; promotion_method?: string; price?: string };
  dramatic_engine?: { ability_paradox?: string; secret_hook?: string; villain_info_gap?: string };
  locations?: string[];
  book_plan?: { main_story?: string; volumes?: { title?: string; goal?: string; estimated_chapters?: number; antagonist?: { name?: string; identity?: string; outcome?: string }; key_events?: string[] }[] };
}

function renderSection(title: string, content: string | undefined) {
  if (!content) return null;
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">{title}</h4>
      <p className="text-sm text-gray-700 leading-relaxed">{content}</p>
    </div>
  );
}

export default function BiblePreviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state || {}) as { sessionId?: string; draft?: DraftData; title?: string };
  const sessionId = state.sessionId || '';

  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  const [showAll, setShowAll] = useState(true);

  const draft = state.draft || {};

  const structuralChecks = [
    { label: '书名', ok: !!draft.book_title },
    { label: '世界观简介', ok: !!draft.intro },
    { label: '金手指机制', ok: !!draft.gold_finger?.name },
    { label: '主角设定', ok: !!draft.hero?.name },
    { label: '反派设定', ok: !!draft.villain?.name },
    { label: '力量体系', ok: !!draft.power_system?.name && (draft.power_system?.levels?.length || 0) > 0 },
    { label: '分卷规划', ok: !!draft.book_plan?.volumes?.length },
    { label: '地点清单', ok: (draft.locations?.length || 0) > 0 },
  ];
  const passedChecks = structuralChecks.filter(c => c.ok).length;
  const allPassed = passedChecks === structuralChecks.length;

  const confirm = async () => {
    if (!sessionId) return;
    setConfirming(true);
    setConfirmError('');
    try {
      const resp = await api.confirmBible(sessionId);
      if (resp?.book_id) {
        setTimeout(() => navigate(`/editor/${resp.book_id}`), 800);
      }
    } catch (err: any) {
      setConfirmError(err.message || '创建书籍失败');
      setConfirming(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-rose-50">
      <Navigation />

      <div className="container mx-auto px-4 sm:px-6 py-8 pb-32 max-w-4xl">
        {/* Header */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-100 border border-amber-200 mb-6">
            <Eye className="w-4 h-4 text-amber-600" />
            <span className="text-sm text-amber-700 font-medium">Bible 预览 · 作者审阅</span>
          </div>
          <h1 className="text-4xl font-bold mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-amber-600 to-rose-600 bg-clip-text text-transparent">{draft.book_title || 'Story Bible'}</span>
          </h1>
          <p className="text-gray-600 max-w-xl mx-auto">
            这是基于你的访谈约束和选定方向生成的完整设定。请仔细审阅，确认后才会创建书籍
          </p>
        </div>

        {/* 结构验证摘要 */}
        <Card padding="lg" className="mb-6 animate-fade-in-scale">
          <div className="flex items-center justify-between mb-4">
            <h2 className="flex items-center gap-2 font-semibold text-gray-900">
              <ShieldCheck className="w-5 h-5 text-green-600" />
              结构完整性检查
            </h2>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              allPassed ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
            }`}>
              {passedChecks}/{structuralChecks.length} 通过
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {structuralChecks.map(check => (
              <div key={check.label} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50">
                {check.ok
                  ? <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                  : <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />}
                <span className="text-xs text-gray-600">{check.label}</span>
              </div>
            ))}
          </div>
          {!allPassed && (
            <p className="text-xs text-amber-600 mt-3">
              提示：部分字段为空。可以在确认创建后回到编辑器补充，或在访谈中补充更多细节。
            </p>
          )}
        </Card>

        {/* 内容切换 */}
        <div className="flex items-center gap-2 mb-4">
          <Button size="sm" variant={showAll ? 'primary' : 'outline'} onClick={() => setShowAll(true)}>
            <BookOpen className="w-4 h-4" />
            全部内容
          </Button>
          <Button size="sm" variant={showAll ? 'outline' : 'primary'} onClick={() => setShowAll(false)}>
            <Eye className="w-4 h-4" />
            仅关键设定
          </Button>
        </div>

        {/* Bible 内容 */}
        <div className="space-y-6 animate-fade-in">
          {/* 核心设定 */}
          <Card padding="lg">
            <h3 className="flex items-center gap-2 font-semibold text-gray-900 mb-4">
              <Sparkles className="w-5 h-5 text-amber-500" />
              核心设定
            </h3>
            <div className="space-y-4">
              {renderSection('世界观简介', draft.intro)}
              {draft.gold_finger && (
                <div className="rounded-xl bg-amber-50/60 border border-amber-100 p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                    金手指 · {draft.gold_finger.name} ({draft.gold_finger.type})
                  </h4>
                  {renderSection('描述', draft.gold_finger.description)}
                  {renderSection('核心能力', draft.gold_finger.core_ability)}
                  {renderSection('限制与代价', draft.gold_finger.limitations)}
                  {renderSection('进化路线', draft.gold_finger.upgrade_route)}
                </div>
              )}
              {draft.hero && (
                <div className="rounded-xl bg-sky-50/60 border border-sky-100 p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-sky-700 uppercase tracking-wide">主角 · {draft.hero.name}</h4>
                  {renderSection('身份', draft.hero.identity)}
                  {renderSection('性格', draft.hero.personality)}
                  {renderSection('核心欲望', draft.hero.core_desire)}
                  {renderSection('恐惧', draft.hero.fear)}
                </div>
              )}
              {draft.villain && (
                <div className="rounded-xl bg-rose-50/60 border border-rose-100 p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-rose-700 uppercase tracking-wide">最终反派 · {draft.villain.name}</h4>
                  {renderSection('身份', draft.villain.identity)}
                  {renderSection('动机', draft.villain.motivation)}
                  {renderSection('与主角的羁绊', draft.villain.relation_to_hero)}
                </div>
              )}
              {draft.power_system && (
                <div className="rounded-xl bg-violet-50/60 border border-violet-100 p-4 space-y-3">
                  <h4 className="text-xs font-semibold text-violet-700 uppercase tracking-wide">
                    力量体系 · {draft.power_system.name}
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {(draft.power_system.levels || []).map((lv, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 text-xs">{lv}</span>
                    ))}
                  </div>
                  {renderSection('表现效果', draft.power_system.visual_effect)}
                  {renderSection('晋升方式', draft.power_system.promotion_method)}
                  {renderSection('代价', draft.power_system.price)}
                </div>
              )}
            </div>
          </Card>

          {/* 戏剧引擎 */}
          {showAll && (draft.dramatic_engine) && (
            <Card padding="lg">
              <h3 className="flex items-center gap-2 font-semibold text-gray-900 mb-4">
                <Hammer className="w-5 h-5 text-purple-500" />
                戏剧引擎
              </h3>
              <div className="space-y-3">
                {renderSection('能力悖论（道德困境）', draft.dramatic_engine?.ability_paradox)}
                {renderSection('秘密钩子', draft.dramatic_engine?.secret_hook)}
                {renderSection('反派信息差', draft.dramatic_engine?.villain_info_gap)}
              </div>
            </Card>
          )}

          {/* 配角 */}
          {showAll && (draft.key_support_roles?.length || 0) > 0 && (
            <Card padding="lg">
              <h3 className="flex items-center gap-2 font-semibold text-gray-900 mb-4">
                <BookOpen className="w-5 h-5 text-teal-500" />
                关键配角
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {draft.key_support_roles!.map((role, i) => (
                  <div key={i} className="rounded-xl bg-gray-50 p-4 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">{role.name}</span>
                      <span className="px-1.5 py-0.5 rounded-full bg-teal-100 text-teal-700 text-xs">{role.role_type}</span>
                    </div>
                    {role.character_hook && <p className="text-xs text-gray-500">记忆点：{role.character_hook}</p>}
                    {role.utility && <p className="text-xs text-gray-500">作用：{role.utility}</p>}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 地点 */}
          {showAll && (draft.locations?.length || 0) > 0 && (
            <Card padding="lg">
              <h3 className="flex items-center gap-2 font-semibold text-gray-900 mb-3">
                <ChevronUp className="w-5 h-5 text-blue-500" />
                地点清单
              </h3>
              <div className="flex flex-wrap gap-2">
                {draft.locations!.map((loc, i) => (
                  <span key={i} className="px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-sm">{loc}</span>
                ))}
              </div>
            </Card>
          )}

          {/* 分卷规划 */}
          {draft.book_plan && (
            <Card padding="lg">
              <h3 className="flex items-center gap-2 font-semibold text-gray-900 mb-2">
                <ChevronDown className="w-5 h-5 text-orange-500" />
                分卷规划
              </h3>
              {renderSection('主线梗概', draft.book_plan.main_story)}
              <div className="space-y-4 mt-4">
                {(draft.book_plan.volumes || []).map((vol, i) => (
                  <div key={i} className="rounded-xl border border-gray-200 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-900 text-sm">{vol.title}</span>
                      <span className="text-xs text-gray-400">约 {vol.estimated_chapters || '?'} 章</span>
                    </div>
                    {vol.goal && <p className="text-sm text-gray-600">{vol.goal}</p>}
                    {vol.antagonist && (
                      <p className="text-xs text-rose-600">
                        本卷反派：{vol.antagonist.name}（{vol.antagonist.identity}）→ {vol.antagonist.outcome}
                      </p>
                    )}
                    {(vol.key_events?.length || 0) > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {vol.key_events!.map((ev, j) => (
                          <span key={j} className="px-2 py-0.5 rounded-full bg-orange-50 text-orange-700 text-xs">{ev}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* 确认区 */}
        <Card padding="lg" className="mt-6 animate-fade-in">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <Button variant="outline" onClick={() => navigate('/interview/variants', { state: { sessionId } })}>
              <ArrowLeft className="w-4 h-4" />
              返回重新选择方案
            </Button>
            <Button size="lg" glow loading={confirming} onClick={confirm}>
              <CheckCircle2 className="w-5 h-5" />
              确认创建书籍
              <ArrowRight className="w-5 h-5" />
            </Button>
          </div>
          {confirmError && <p className="text-sm text-red-500 mt-3 text-center">{confirmError}</p>}
          <p className="text-xs text-gray-400 mt-4 text-center">
            确认后将创建书籍并进入编辑器。后续可通过「提议修改」流程调整设定（Phase 3 上线）。
          </p>
        </Card>
      </div>
    </div>
  );
}

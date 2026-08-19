import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Navigation } from '@/components/ui/Navigation';
import {
  Sparkles, Loader2, RefreshCw, CheckCircle2, GitMerge,
  ArrowRight, TrendingUp, AlertTriangle, Layers, MessageCircleQuestion
} from 'lucide-react';

interface Variant {
  label: string;
  seed: string;
  core_setting: Record<string, string>;
  strengths: string[];
  risks: string[];
}

export default function VariantComparePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state || {}) as {
    sessionId?: string;
    constraints?: Record<string, string>;
    rawIdea?: string;
    style?: string;
  };

  const sessionId = state.sessionId || '';
  const [variants, setVariants] = useState<Variant[]>([]);
  const [loading, setLoading] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [error, setError] = useState('');
  const [chapterCount, setChapterCount] = useState('100');
  const [selected, setSelected] = useState<string | null>(null);
  const [merged, setMerged] = useState<string[]>([]);

  const generateVariants = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError('');
    try {
      const constraints = state.constraints || {};
      const resp = await api.generateVariants(sessionId, constraints, state.style || '男频-热血玄幻', 3);
      setVariants(resp.variants || []);
    } catch (err: any) {
      setError(err.message || '方案生成失败，请检查模型配置');
    } finally {
      setLoading(false);
    }
  };

  const decide = async (decision: string, chosen?: string) => {
    setDeciding(true);
    try {
      const resp = await api.decideVariant(
        sessionId,
        decision,
        chosen,
        decision === 'merge' ? merged : undefined,
        parseInt(chapterCount) || 100
      );
      if (resp?.session_id && resp?.draft) {
        setTimeout(() => navigate('/interview/bible-preview', {
          state: { sessionId: resp.session_id, draft: resp.draft, title: resp.title },
        }), 800);
      } else {
        setDeciding(false);
      }
    } catch (err: any) {
      setError(err.message || 'Bible 生成失败');
      setDeciding(false);
    }
  };

  const toggleMerge = (label: string) => {
    setSelected(null);
    setMerged(prev =>
      prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]
    );
  };

  useEffect(() => {
    if (sessionId) generateVariants();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-purple-50 to-indigo-50">
      <Navigation />

      <div className="container mx-auto px-4 sm:px-6 py-8 pb-32 max-w-6xl">
        {/* Header */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-100 border border-violet-200 mb-6">
            <Layers className="w-4 h-4 text-violet-600" />
            <span className="text-sm text-violet-700 font-medium">多方案竞争 · Variant Compare</span>
          </div>
          <h1 className="text-4xl font-bold mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">选择核心设定方向</span>
          </h1>
          <p className="text-gray-600 max-w-xl mx-auto mb-4">
            三套方案基于同一批约束生成，各有不同的创作方向。比较后选择最符合你想法的那个
          </p>
          {state.rawIdea && (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 border border-gray-200 text-sm text-gray-600">
              <MessageCircleQuestion className="w-4 h-4 text-violet-500" />
              「{state.rawIdea.slice(0, 30)}{state.rawIdea.length > 30 ? '...' : ''}」
            </div>
          )}
        </div>

        {/* Loading */}
        {loading && !variants.length ? (
          <div className="flex flex-col items-center justify-center py-24 animate-fade-in">
            <Loader2 className="w-12 h-12 animate-spin text-violet-500" />
            <p className="text-gray-500 mt-4">AI 正在生成三套差异化方案...</p>
          </div>
        ) : error && !variants.length ? (
          <Card padding="lg" className="text-center py-16 animate-fade-in-scale">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-red-50 flex items-center justify-center">
              <AlertTriangle className="w-8 h-8 text-red-500" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">方案生成失败</h3>
            <p className="text-gray-500 mb-6">{error}</p>
            <Button variant="outline" onClick={generateVariants} disabled={loading}>
              <RefreshCw className="w-4 h-4" />
              重新生成
            </Button>
          </Card>
        ) : variants.length > 0 ? (
          <>
            {/* Variant Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10 animate-fade-in-scale">
              {variants.map(variant => {
                const isSelected = selected === variant.label;
                const isMerged = merged.includes(variant.label);
                const isActive = isSelected || isMerged;
                return (
                  <Card
                    key={variant.label}
                    hover
                    className={`relative transition-all duration-300 ${
                      isActive ? 'ring-2 ring-violet-500 shadow-xl shadow-violet-500/20' : ''
                    }`}
                  >
                    {/* Variant Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-white ${
                        variant.label === 'A' ? 'bg-gradient-to-br from-rose-500 to-orange-500' :
                        variant.label === 'B' ? 'bg-gradient-to-br from-violet-500 to-purple-500' :
                        'bg-gradient-to-br from-sky-500 to-blue-500'
                      }`}>
                        {variant.label}
                      </div>
                      {isActive && (
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          isSelected ? 'bg-violet-100 text-violet-700' : 'bg-amber-100 text-amber-700'
                        }`}>
                          {isSelected ? '已选定' : '已勾选融合'}
                        </span>
                      )}
                    </div>

                    <p className="text-sm text-gray-700 font-medium mb-4 leading-relaxed min-h-16">
                      {variant.seed}
                    </p>

                    {/* 核心设定摘要 */}
                    <div className="space-y-2 mb-4 text-xs">
                      {Object.entries(variant.core_setting || {}).slice(0, 3).map(([k, v]) => (
                        <div key={k} className="flex gap-2">
                          <span className="text-gray-400 whitespace-nowrap w-14 shrink-0">{k}:</span>
                          <span className="text-gray-600">{v}</span>
                        </div>
                      ))}
                    </div>

                    {/* 优势 / 风险 */}
                    <div className="space-y-3 mb-5">
                      <div>
                        <div className="flex items-center gap-1 text-xs text-green-600 font-semibold mb-1.5">
                          <TrendingUp className="w-3.5 h-3.5" />
                          潜在优势
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {(variant.strengths || []).slice(0, 3).map((s, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-xs">
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-1 text-xs text-amber-600 font-semibold mb-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          明显风险
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {(variant.risks || []).slice(0, 3).map((r, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 text-xs">
                              {r}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        className="flex-1"
                        variant={isSelected ? 'primary' : 'outline'}
                        onClick={() => { setSelected(variant.label); setMerged([]); }}
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        采用方案 {variant.label}
                      </Button>
                      <Button
                        size="sm"
                        variant={isMerged ? 'gradient' : 'ghost'}
                        onClick={() => toggleMerge(variant.label)}
                      >
                        <GitMerge className="w-4 h-4" />
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>

            {/* 决策区 */}
            <Card padding="lg" className="animate-fade-in">
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-6">
                <div>
                  <label className="block text-sm text-gray-700 mb-1.5 font-medium">预期篇幅（章）</label>
                  <input
                    type="number"
                    value={chapterCount}
                    onChange={e => setChapterCount(e.target.value)}
                    min="20"
                    max="500"
                    className="w-36 px-3 py-2 rounded-xl border-2 border-gray-200 focus:border-violet-500 focus:outline-none transition-colors"
                  />
                </div>
                <div className="flex-1" />
                <div className="flex gap-2">
                  <Button variant="outline" onClick={generateVariants} disabled={loading}>
                    <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    重新生成
                  </Button>
                  <Button
                    size="lg"
                    glow
                    disabled={!selected && merged.length < 2}
                    loading={deciding}
                    onClick={() => {
                      if (selected) decide('choose', selected);
                      else if (merged.length >= 2) decide('merge');
                    }}
                  >
                    <Sparkles className="w-5 h-5" />
                    {selected
                      ? `确认采用方案 ${selected}`
                      : merged.length >= 2
                        ? `融合 ${merged.join('+')} 生成书籍`
                        : '请选择一个方案'}
                    <ArrowRight className="w-5 h-5" />
                  </Button>
                </div>
              </div>
              <p className="text-xs text-gray-400">
                提示：融合模式至少勾选 2 个方案（点击卡片上的融合按钮）。选定后将以该方向生成完整世界观并创建书籍。
              </p>
            </Card>
          </>
        ) : null}
      </div>
    </div>
  );
}

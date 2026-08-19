import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Navigation } from '@/components/ui/Navigation';
import { 
  MessageCircleQuestion, Sparkles, ArrowRight, Loader2, 
  ChevronRight, CheckCircle2, PenLine, SkipForward, Wand2
} from 'lucide-react';

interface InterviewOption {
  label: string;
  value: string;
  implication?: string;
  potential_score?: number | null;
}

interface InterviewQuestion {
  question_id: string;
  topic: string;
  question: string;
  rationale?: string;
  options: InterviewOption[];
}

export default function CreativeInterviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state || {}) as { rawIdea?: string; style?: string };

  const [rawIdea, setRawIdea] = useState(state.rawIdea || '');
  const [style, setStyle] = useState(state.style || '男频-热血玄幻');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<InterviewQuestion | null>(null);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [freeInput, setFreeInput] = useState('');
  const [history, setHistory] = useState<{ q: string; a: string }[]>([]);
  const [completed, setCompleted] = useState(false);

  const startInterview = async () => {
    if (!rawIdea.trim()) return;
    setLoading(true);
    try {
      const resp = await api.startInterview(rawIdea.trim(), style);
      setSessionId(resp.session_id);
      setQuestion(resp.question);
      setProgress(resp.progress);
    } catch (err) {
      alert('访谈启动失败，请检查模型配置');
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async (optionValue: string, freeText = '') => {
    if (!sessionId || !question) return;
    setLoading(true);
    const answer = freeText ? { free_input: freeText } : { option_value: optionValue };
    try {
      const resp = await api.answerInterview(sessionId, question.question_id, answer);
      setHistory(prev => [...prev, {
        q: question.question,
        a: freeText || question.options.find(o => o.value === optionValue)?.label || optionValue,
      }]);
      setFreeInput('');
      if (resp.completed || !resp.question) {
        setCompleted(true);
        setQuestion(null);
      } else {
        setQuestion(resp.question);
        setProgress(resp.progress);
      }
    } catch (err) {
      alert('提交失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const skipQuestion = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const resp = await api.skipInterview(sessionId);
      setHistory(prev => [...prev, { q: question?.question || '跳过', a: '⏭️ 跳过' }]);
      if (resp.completed || !resp.question) {
        setCompleted(true);
        setQuestion(null);
      } else {
        setQuestion(resp.question);
        setProgress(resp.progress);
      }
    } catch (err) {
      alert('操作失败');
    } finally {
      setLoading(false);
    }
  };

  const finishEarly = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const resp = await api.completeInterview(sessionId);
      navigate('/interview/variants', {
        state: {
          sessionId,
          constraints: resp.constraints,
          rawIdea: resp.raw_idea,
          style: resp.style,
        },
      });
    } catch (err) {
      alert('结束访谈失败');
    } finally {
      setLoading(false);
    }
  };

  const goToVariants = async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const resp = await api.completeInterview(sessionId);
      navigate('/interview/variants', {
        state: {
          sessionId,
          constraints: resp.constraints,
          rawIdea: resp.raw_idea,
          style: resp.style,
        },
      });
    } catch (err) {
      alert('获取访谈结果失败');
      setLoading(false);
    }
  };

  const progressPercent = Math.round(progress * 100);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-purple-50 to-fuchsia-50">
      <Navigation />

      <div className="container mx-auto px-4 sm:px-6 py-8 pb-32 max-w-3xl">
        {/* Header */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-100 border border-purple-200 mb-6">
            <MessageCircleQuestion className="w-4 h-4 text-purple-600" />
            <span className="text-sm text-purple-700 font-medium">创作访谈 · Creative Interview</span>
          </div>
          <h1 className="text-4xl font-bold mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-purple-600 to-fuchsia-600 bg-clip-text text-transparent">把你的想法变成可写的故事</span>
          </h1>
          <p className="text-gray-600 max-w-xl mx-auto">
            你只需要做选择，AI 帮你把模糊创意一步步提炼成结构化设定
          </p>
        </div>

        {!sessionId ? (
          /* Step 0: 输入创意 */
          <Card padding="lg" className="animate-fade-in-scale">
            <div className="space-y-6">
              <div>
                <label className="block text-sm text-gray-700 mb-2 font-medium">你的创作想法</label>
                <textarea
                  value={rawIdea}
                  onChange={e => setRawIdea(e.target.value)}
                  placeholder="例如：一个被废掉的天才重新崛起的玄幻故事..."
                  rows={4}
                  className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-purple-500 focus:outline-none transition-colors resize-none"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-700 mb-2 font-medium">目标风格</label>
                <select
                  value={style}
                  onChange={e => setStyle(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-purple-500 focus:outline-none transition-colors bg-white"
                >
                  <option value="男频-热血玄幻">⚔️ 热血玄幻</option>
                  <option value="男频-系统数据">📊 系统数据</option>
                  <option value="男频-诡秘智斗">🔮 诡秘智斗</option>
                  <option value="男频-稳健苟道">🛡️ 稳健苟道</option>
                  <option value="男频-无敌碾压">👑 无敌碾压</option>
                  <option value="男频-末世/无限流">☢️ 末世废土</option>
                  <option value="女频-古言权谋">🌸 古言权谋</option>
                  <option value="女频-现言救赎">💝 现言救赎</option>
                </select>
              </div>
              <Button size="lg" glow className="w-full" onClick={startInterview} disabled={!rawIdea.trim() || loading}>
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Wand2 className="w-5 h-5" />}
                开始访谈
              </Button>
            </div>
          </Card>
        ) : completed ? (
          /* Step 2: 访谈完成 */
          <Card padding="lg" className="text-center py-16 animate-fade-in-scale">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-purple-100 to-fuchsia-100 flex items-center justify-center">
              <CheckCircle2 className="w-10 h-10 text-purple-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">访谈完成！</h2>
            <p className="text-gray-500 mb-8">已收集 {history.length} 个创作约束，接下来为你生成多套核心设定方案</p>
            <div className="max-h-40 overflow-y-auto mb-8 text-left space-y-1.5 px-6">
              {history.map((h, i) => (
                <div key={i} className="text-sm">
                  <span className="text-gray-400 mr-2">{i + 1}.</span>
                  <span className="text-gray-600">{h.q}</span>
                  <span className="text-purple-600 font-medium ml-2">→ {h.a}</span>
                </div>
              ))}
            </div>
            <Button size="lg" glow onClick={goToVariants}>
              <Sparkles className="w-5 h-5" />
              生成方案
              <ChevronRight className="w-4 h-4" />
            </Button>
          </Card>
        ) : (
          /* Step 1: 答题中 */
          <Card padding="lg" className="animate-fade-in">
            {/* Progress */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-500 font-medium">
                  {history.length > 0 && (
                    <span className="inline-flex items-center gap-1 mr-3 text-purple-600">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      已答 {history.length} 题
                    </span>
                  )}
                  覆盖度 {progressPercent}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-fuchsia-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.max(progressPercent, 4)}%` }}
                />
              </div>
            </div>

            {/* 已回答摘要 */}
            {history.length > 0 && (
              <div className="mb-6 max-h-24 overflow-y-auto space-y-1 bg-purple-50/50 rounded-xl p-3">
                {history.slice(-3).map((h, i) => (
                  <div key={i} className="text-xs">
                    <span className="text-gray-400 mr-2">✓</span>
                    <span className="text-gray-500">{h.q.slice(0, 30)}...</span>
                    <span className="text-purple-600 font-medium ml-2">→ {h.a.slice(0, 20)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Question */}
            {question && (
              <div className="space-y-6">
                <div className="bg-gradient-to-r from-purple-50 to-fuchsia-50 rounded-2xl p-6 border border-purple-100">
                  <div className="text-xs text-purple-500 font-semibold mb-2 tracking-wide">
                    📌 主题：{question.topic}
                  </div>
                  <h2 className="text-xl font-bold text-gray-900 mb-2">{question.question}</h2>
                  {question.rationale && (
                    <p className="text-sm text-gray-500">{question.rationale}</p>
                  )}
                </div>

                <div className="space-y-3">
                  {question.options.filter(opt => opt.value !== '__free_input__').map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => submitAnswer(opt.value)}
                      disabled={loading}
                      className="w-full flex items-start gap-3 px-5 py-4 rounded-xl border-2 border-gray-200 hover:border-purple-500 hover:bg-purple-50 transition-all group text-left"
                    >
                      <span className="mt-0.5">
                        <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-purple-500 transition-colors" />
                      </span>
                      <span className="flex-1">
                        <span className="block text-sm font-medium text-gray-900">{opt.label}</span>
                        {opt.implication && (
                          <span className="block text-xs text-gray-500 mt-1">{opt.implication}</span>
                        )}
                      </span>
                      {typeof opt.potential_score === 'number' && (
                        <span className="text-xs text-amber-600 font-medium whitespace-nowrap">
                          {'★'.repeat(Math.max(1, Math.min(5, opt.potential_score)))}
                        </span>
                      )}
                    </button>
                  ))}
                </div>

                {/* 自由输入区（替代 D 选项，避免重复） */}
                <div className="rounded-xl border-2 border-dashed border-purple-300 bg-purple-50/40 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <PenLine className="w-4 h-4 text-purple-500" />
                    <span className="text-sm font-medium text-purple-700">自己的想法（可选）</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={freeInput}
                      onChange={e => setFreeInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && freeInput.trim()) submitAnswer('', freeInput);
                      }}
                      placeholder="用自己的话描述..."
                      className="flex-1 px-4 py-2.5 rounded-xl border-2 border-purple-200 focus:border-purple-500 focus:outline-none transition-colors"
                    />
                    <Button size="sm" glow onClick={() => submitAnswer('', freeInput)} disabled={!freeInput.trim() || loading}>
                      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                      提交
                    </Button>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <Button variant="ghost" size="sm" onClick={skipQuestion} disabled={loading}>
                    <SkipForward className="w-4 h-4" />
                    跳过此题
                  </Button>
                  <Button variant="outline" size="sm" onClick={finishEarly} disabled={loading}>
                    <Sparkles className="w-4 h-4" />
                    够了，开始生成方案
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

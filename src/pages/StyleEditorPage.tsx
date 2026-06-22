import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Navigation } from '@/components/ui/Navigation';
import { Plus, Trash2, Loader2, RefreshCw, Save, ArrowLeft, BookOpen } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface StyleExample {
  scene_type: string;
  content: string;
  source: string;
}

interface StyleCard {
  name: string;
  author: string;
  perspective_distance: string;
  rhythm_density: string;
  sensory_preference: string[];
  dialogue_strategy: string;
  whitespace_threshold: string;
  style_instructions: string;
  review_checklist: string[];
  examples: StyleExample[];
  legacy_persona: string;
}

const PERSPECTIVE_OPTIONS = [
  { value: 'tight', label: '紧贴主角感官' },
  { value: 'occasional_omniscient', label: '偶尔上帝视角' },
  { value: 'multi_pov', label: '频繁切换视角' },
];

const RHYTHM_OPTIONS = [
  { value: 'high', label: '高密度 (一段多信息)' },
  { value: 'low', label: '低密度 (一件事写透)' },
];

const SENSORY_OPTIONS = [
  { value: 'visual', label: '视觉' },
  { value: 'auditory', label: '听觉' },
  { value: 'tactile', label: '触觉' },
  { value: 'olfactory', label: '嗅觉' },
  { value: 'gustatory', label: '味觉' },
];

const DIALOGUE_OPTIONS = [
  { value: 'bare', label: '纯对话极简' },
  { value: 'action_tagged', label: '配动作/微表情' },
  { value: 'inner_reaction', label: '跟内心反应' },
];

const WHITESPACE_OPTIONS = [
  { value: 'high', label: '高留白 (不写心理)' },
  { value: 'medium', label: '中留白 (偶尔独白)' },
  { value: 'low', label: '低留白 (大段心理)' },
];

const SCENE_TYPE_OPTIONS = [
  { value: 'climax', label: '高潮/战斗' },
  { value: 'dialogue', label: '对话密集' },
  { value: 'daily', label: '日常/过渡' },
];

const emptyCard: StyleCard = {
  name: '',
  author: '',
  perspective_distance: 'tight',
  rhythm_density: 'high',
  sensory_preference: ['visual'],
  dialogue_strategy: 'action_tagged',
  whitespace_threshold: 'medium',
  style_instructions: '',
  review_checklist: [],
  examples: [],
  legacy_persona: '',
};

export default function StyleEditorPage() {
  const navigate = useNavigate();
  const [cards, setCards] = useState<string[]>([]);
  const [selectedCard, setSelectedCard] = useState<string | null>(null);
  const [form, setForm] = useState<StyleCard>({ ...emptyCard });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [migrating, setMigrating] = useState(false);

  // 新示例表单
  const [newExample, setNewExample] = useState({ scene_type: 'climax', content: '', source: '' });

  useEffect(() => { loadCards(); }, []);

  const loadCards = async () => {
    setLoading(true);
    try {
      const list = await api.getStyleCards();
      setCards(list);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const selectCard = async (name: string) => {
    try {
      const card = await api.getStyleCard(name);
      setForm(card);
      setSelectedCard(name);
    } catch (e) { console.error(e); }
  };

  const createNew = () => {
    setForm({ ...emptyCard });
    setSelectedCard(null);
  };

  const saveCard = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await api.createStyleCard(form);
      await loadCards();
      setSelectedCard(form.name);
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const deleteCard = async (name: string) => {
    if (!confirm(`确定删除风格卡 "${name}"？`)) return;
    try {
      await api.deleteStyleCard(name);
      if (selectedCard === name) createNew();
      await loadCards();
    } catch (e) { console.error(e); }
  };

  const regenerate = async () => {
    if (!selectedCard) return;
    try {
      const result = await api.regenerateStyleInstructions(selectedCard);
      setForm(prev => ({
        ...prev,
        style_instructions: result.style_instructions,
        review_checklist: result.review_checklist,
      }));
    } catch (e) { console.error(e); }
  };

  const migrateLegacy = async () => {
    setMigrating(true);
    try {
      await api.migrateLegacyStyles();
      await loadCards();
    } catch (e) { console.error(e); }
    setMigrating(false);
  };

  const addExample = () => {
    if (!newExample.content.trim()) return;
    setForm(prev => ({
      ...prev,
      examples: [...prev.examples, { ...newExample }],
    }));
    setNewExample({ scene_type: 'climax', content: '', source: '' });
  };

  const removeExample = (index: number) => {
    setForm(prev => ({
      ...prev,
      examples: prev.examples.filter((_, i) => i !== index),
    }));
  };

  const toggleSensory = (value: string) => {
    setForm(prev => {
      const current = prev.sensory_preference;
      if (current.includes(value)) {
        return { ...prev, sensory_preference: current.filter(s => s !== value) };
      }
      return { ...prev, sensory_preference: [...current, value] };
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <h1 className="text-2xl font-bold text-gray-900">五维风格系统</h1>
          </div>
          <Button variant="secondary" size="sm" onClick={migrateLegacy} disabled={migrating}>
            {migrating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            <span className="ml-1">迁移旧风格</span>
          </Button>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {/* 左侧：风格卡列表 */}
          <div className="col-span-3">
            <Card className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-700">风格卡列表</h3>
                <button onClick={createNew} className="text-blue-500 hover:text-blue-700">
                  <Plus className="w-4 h-4" />
                </button>
              </div>
              {loading ? (
                <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
              ) : (
                <div className="space-y-1">
                  {cards.map(name => (
                    <div
                      key={name}
                      className={`flex items-center justify-between px-3 py-2 rounded cursor-pointer text-sm ${
                        selectedCard === name ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100 text-gray-600'
                      }`}
                      onClick={() => selectCard(name)}
                    >
                      <span className="truncate">{name}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteCard(name); }}
                        className="text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                  {cards.length === 0 && (
                    <p className="text-xs text-gray-400 text-center py-4">暂无风格卡，点击"迁移旧风格"导入预设</p>
                  )}
                </div>
              )}
            </Card>
          </div>

          {/* 右侧：编辑区 */}
          <div className="col-span-9 space-y-4">
            {/* 基本信息 */}
            <Card className="p-5">
              <h3 className="font-medium text-gray-800 mb-4">基本信息</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">风格名称</label>
                  <input
                    className="w-full px-3 py-2 border rounded text-sm"
                    value={form.name}
                    onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="如：男频-热血玄幻"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">作者/来源</label>
                  <input
                    className="w-full px-3 py-2 border rounded text-sm"
                    value={form.author}
                    onChange={e => setForm(prev => ({ ...prev, author: e.target.value }))}
                    placeholder="如：自定义 / 某作者名"
                  />
                </div>
              </div>
            </Card>

            {/* 五维度设置 */}
            <Card className="p-5">
              <h3 className="font-medium text-gray-800 mb-4">五维度设置</h3>
              <div className="space-y-4">
                {/* 视角距离 */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">1. 视角距离</label>
                  <div className="flex gap-2">
                    {PERSPECTIVE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        className={`px-3 py-1.5 rounded text-xs border ${
                          form.perspective_distance === opt.value
                            ? 'bg-blue-500 text-white border-blue-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                        }`}
                        onClick={() => setForm(prev => ({ ...prev, perspective_distance: opt.value }))}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 节奏密度 */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">2. 节奏密度</label>
                  <div className="flex gap-2">
                    {RHYTHM_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        className={`px-3 py-1.5 rounded text-xs border ${
                          form.rhythm_density === opt.value
                            ? 'bg-blue-500 text-white border-blue-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                        }`}
                        onClick={() => setForm(prev => ({ ...prev, rhythm_density: opt.value }))}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 感官偏向 */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">3. 感官偏向 (按优先级点选，先点的优先级高)</label>
                  <div className="flex gap-2">
                    {SENSORY_OPTIONS.map(opt => {
                      const idx = form.sensory_preference.indexOf(opt.value);
                      return (
                        <button
                          key={opt.value}
                          className={`px-3 py-1.5 rounded text-xs border ${
                            idx >= 0
                              ? 'bg-blue-500 text-white border-blue-500'
                              : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                          }`}
                          onClick={() => toggleSensory(opt.value)}
                        >
                          {idx >= 0 && <span className="mr-1">{idx + 1}.</span>}
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 对话策略 */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">4. 对话策略</label>
                  <div className="flex gap-2">
                    {DIALOGUE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        className={`px-3 py-1.5 rounded text-xs border ${
                          form.dialogue_strategy === opt.value
                            ? 'bg-blue-500 text-white border-blue-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                        }`}
                        onClick={() => setForm(prev => ({ ...prev, dialogue_strategy: opt.value }))}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 留白阈值 */}
                <div>
                  <label className="block text-xs text-gray-500 mb-2">5. 留白阈值</label>
                  <div className="flex gap-2">
                    {WHITESPACE_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        className={`px-3 py-1.5 rounded text-xs border ${
                          form.whitespace_threshold === opt.value
                            ? 'bg-blue-500 text-white border-blue-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                        }`}
                        onClick={() => setForm(prev => ({ ...prev, whitespace_threshold: opt.value }))}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {/* 生成的风格指令 */}
            <Card className="p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-800">风格指令 (自动生成/可手动覆盖)</h3>
                {selectedCard && (
                  <Button variant="ghost" size="sm" onClick={regenerate}>
                    <RefreshCw className="w-3 h-3 mr-1" /> 重新生成
                  </Button>
                )}
              </div>
              <textarea
                className="w-full px-3 py-2 border rounded text-sm font-mono h-32 resize-y"
                value={form.style_instructions}
                onChange={e => setForm(prev => ({ ...prev, style_instructions: e.target.value }))}
                placeholder="保存时将根据五维度自动生成，也可手动编写覆盖"
              />
            </Card>

            {/* 风格校验清单 */}
            <Card className="p-5">
              <h3 className="font-medium text-gray-800 mb-3">风格校验清单 (Review Agent 使用)</h3>
              <div className="space-y-1">
                {form.review_checklist.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm text-gray-600">
                    <span className="text-green-500">&#10003;</span>
                    <span className="flex-1">{item}</span>
                    <button
                      className="text-gray-400 hover:text-red-500"
                      onClick={() => setForm(prev => ({
                        ...prev,
                        review_checklist: prev.review_checklist.filter((_, idx) => idx !== i),
                      }))}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {form.review_checklist.length === 0 && (
                  <p className="text-xs text-gray-400">保存时将根据五维度自动生成</p>
                )}
              </div>
            </Card>

            {/* Few-shot 示例库 */}
            <Card className="p-5">
              <h3 className="font-medium text-gray-800 mb-3">
                <BookOpen className="w-4 h-4 inline mr-1" />
                写作范例库 (Few-shot Examples)
              </h3>
              <p className="text-xs text-gray-500 mb-3">
                添加目标风格的原文片段，按场景类型分类。写作时会自动匹配当前场景类型注入。
              </p>

              {/* 已有示例 */}
              <div className="space-y-3 mb-4">
                {form.examples.map((ex, i) => (
                  <div key={i} className="border rounded p-3 bg-gray-50">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-blue-600">
                        [{SCENE_TYPE_OPTIONS.find(o => o.value === ex.scene_type)?.label || ex.scene_type}]
                        {ex.source && <span className="text-gray-400 ml-2">- {ex.source}</span>}
                      </span>
                      <button onClick={() => removeExample(i)} className="text-gray-400 hover:text-red-500">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                    <p className="text-xs text-gray-600 whitespace-pre-wrap line-clamp-4">{ex.content}</p>
                  </div>
                ))}
              </div>

              {/* 添加新示例 */}
              <div className="border-t pt-3 space-y-2">
                <div className="flex gap-2">
                  <select
                    className="px-2 py-1 border rounded text-xs"
                    value={newExample.scene_type}
                    onChange={e => setNewExample(prev => ({ ...prev, scene_type: e.target.value }))}
                  >
                    {SCENE_TYPE_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                  <input
                    className="flex-1 px-2 py-1 border rounded text-xs"
                    placeholder="来源说明 (可选)"
                    value={newExample.source}
                    onChange={e => setNewExample(prev => ({ ...prev, source: e.target.value }))}
                  />
                </div>
                <textarea
                  className="w-full px-3 py-2 border rounded text-xs font-mono h-24 resize-y"
                  placeholder="粘贴原文片段..."
                  value={newExample.content}
                  onChange={e => setNewExample(prev => ({ ...prev, content: e.target.value }))}
                />
                <Button variant="secondary" size="sm" onClick={addExample}>
                  <Plus className="w-3 h-3 mr-1" /> 添加示例
                </Button>
              </div>
            </Card>

            {/* 保存按钮 */}
            <div className="flex justify-end">
              <Button onClick={saveCard} disabled={saving || !form.name.trim()}>
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Save className="w-4 h-4 mr-1" />}
                保存风格卡
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { ChevronLeft, Save, RotateCcw, Code2, MessageSquare, Eye, EyeOff } from 'lucide-react';

interface PromptStage {
  key: string;
  label: string;
  description: string;
  variables: string[];
}

interface PromptData {
  system_default: string;
  system_override: string | null;
  template_default: string;
  template_override: string | null;
}

export default function PromptEditorPage() {
  const navigate = useNavigate();
  const [stagesMeta, setStagesMeta] = useState<PromptStage[]>([]);
  const [allPrompts, setAllPrompts] = useState<Record<string, PromptData>>({});
  const [activeStage, setActiveStage] = useState<string>('');
  const [editSystem, setEditSystem] = useState<string>('');
  const [editTemplate, setEditTemplate] = useState<string>('');
  const [showDiff, setShowDiff] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [metaData, promptsData] = await Promise.all([
        api.getPromptMeta(),
        api.getAllPrompts(),
      ]);
      setStagesMeta(metaData.stages || []);
      setAllPrompts(promptsData);
      if (metaData.stages?.length > 0 && !activeStage) {
        setActiveStage(metaData.stages[0].key);
      }
    } catch (e) {
      console.error('Failed to load prompts', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!activeStage || !allPrompts[activeStage]) return;
    const data = allPrompts[activeStage];
    setEditSystem(data.system_override ?? data.system_default);
    setEditTemplate(data.template_override ?? data.template_default);
  }, [activeStage, allPrompts]);

  const currentStageMeta = stagesMeta.find(s => s.key === activeStage);
  const currentData = allPrompts[activeStage];
  const hasOverride = currentData?.system_override != null || currentData?.template_override != null;
  const isSystemOverride = editSystem !== currentData?.system_default;
  const isTemplateOverride = editTemplate !== currentData?.template_default;

  const handleSave = async () => {
    if (!activeStage) return;
    setSaving(true);
    try {
      await api.updatePrompt(
        activeStage,
        isSystemOverride ? editSystem : undefined,
        isTemplateOverride ? editTemplate : undefined,
      );
      await loadData();
    } catch (e) {
      console.error('Save failed', e);
      alert('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!activeStage) return;
    try {
      await api.resetPrompt(activeStage);
      await loadData();
    } catch (e) {
      console.error('Reset failed', e);
    }
  };

  const handleResetToDefault = () => {
    if (currentData) {
      setEditSystem(currentData.system_default);
      setEditTemplate(currentData.template_default);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="flex items-center gap-2 py-2 px-4 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
            >
              <ChevronLeft className="w-4 h-4" />
              返回
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Prompt 模板编辑器</h1>
              <p className="text-xs text-gray-500 mt-0.5">自定义各阶段 System Prompt 和 Template, 保留默认兜底</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {hasOverride && (
              <Button variant="ghost" size="sm" onClick={handleReset} className="text-red-500 hover:text-red-600">
                <RotateCcw className="w-4 h-4 mr-1" />
                恢复默认
              </Button>
            )}
            <Button size="sm" onClick={handleSave} disabled={saving} glow>
              <Save className="w-4 h-4 mr-1" />
              {saving ? '保存中...' : '保存修改'}
            </Button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="mx-auto px-6 overflow-x-auto">
          <div className="flex gap-1 pb-2">
            {stagesMeta.map(stage => {
              const isOverride = allPrompts[stage.key]?.system_override != null || allPrompts[stage.key]?.template_override != null;
              return (
                <button
                  key={stage.key}
                  onClick={() => setActiveStage(stage.key)}
                  className={`whitespace-nowrap px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                    activeStage === stage.key
                      ? 'bg-blue-100 text-blue-700 border border-blue-200'
                      : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {stage.label}
                  {isOverride && <span className="w-2 h-2 rounded-full bg-orange-500" title="已自定义" />}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-gray-400">
            <div className="w-8 h-8 border-4 border-blue-300 border-t-blue-600 rounded-full animate-spin mr-3" />
            加载中...
          </div>
        ) : !activeStage || !currentData ? (
          <div className="text-center py-20 text-gray-400">选择一个阶段开始编辑</div>
        ) : (
          <div className="space-y-6">
            {/* Stage info */}
            <Card padding="md" className="bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-100">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-gray-900 text-lg">{currentStageMeta?.label}</h3>
                  <p className="text-sm text-gray-600 mt-1">{currentStageMeta?.description}</p>
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    <span className="text-xs text-gray-400 font-medium">可用变量: </span>
                    {currentStageMeta?.variables.map(v => (
                      <code key={v} className="px-1.5 py-0.5 text-xs bg-white border border-gray-200 rounded text-blue-600 font-mono">
                        {`{${v}}`}
                      </code>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {hasOverride && (
                    <span className="px-2.5 py-1 bg-orange-100 text-orange-700 text-xs rounded-full border border-orange-200 font-medium">
                      已自定义
                    </span>
                  )}
                  <button
                    onClick={() => setShowDiff(!showDiff)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600"
                  >
                    {showDiff ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showDiff ? '隐藏对比' : '显示默认'}
                  </button>
                  {!showDiff && (isSystemOverride || isTemplateOverride) && (
                    <button
                      onClick={handleResetToDefault}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600"
                    >
                      <RotateCcw className="w-3 h-3" />
                      恢复默认
                    </button>
                  )}
                </div>
              </div>
            </Card>

            {/* System Prompt */}
            <Card padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <MessageSquare className="w-5 h-5 text-blue-500" />
                <h3 className="font-bold text-gray-900">系统角色设定 (System Prompt)</h3>
                {isSystemOverride && (
                  <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full">已自定义</span>
                )}
              </div>

              <div className={showDiff ? 'grid grid-cols-2 gap-4' : ''}>
                <div>
                  <textarea
                    value={editSystem}
                    onChange={e => setEditSystem(e.target.value)}
                    rows={4}
                    className="w-full p-4 border-2 border-blue-200 rounded-xl focus:border-blue-500 focus:outline-none text-gray-700 text-sm resize-y min-h-[100px]"
                  />
                </div>

                {showDiff && isSystemOverride && (
                  <div className="relative">
                    <textarea
                      value={currentData.system_default}
                      readOnly
                      rows={4}
                      className="w-full p-4 border-2 border-gray-200 rounded-xl bg-gray-50 text-gray-500 text-sm resize-none min-h-[100px] cursor-default"
                    />
                    <span className="absolute top-2 right-2 px-2 py-0.5 text-xs bg-gray-200 text-gray-500 rounded font-medium">
                      Default
                    </span>
                  </div>
                )}
              </div>
            </Card>

            {/* Template Prompt */}
            <Card padding="lg">
              <div className="flex items-center gap-2 mb-4">
                <Code2 className="w-5 h-5 text-indigo-500" />
                <h3 className="font-bold text-gray-900">任务模板 (Template)</h3>
                {isTemplateOverride && (
                  <span className="text-xs px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full">已自定义</span>
                )}
              </div>

              <p className="text-xs text-gray-400 mb-3">
                使用 {'{variable}'} 语法引用上方变量。修改后保存即覆盖默认值，删除恢复按钮可还原默认。
              </p>

              <div className={showDiff ? 'grid grid-cols-2 gap-4' : ''}>
                <div>
                  <textarea
                    value={editTemplate}
                    onChange={e => setEditTemplate(e.target.value)}
                    rows={20}
                    className="w-full p-4 border-2 border-indigo-200 rounded-xl focus:border-indigo-500 focus:outline-none text-gray-700 text-sm font-mono resize-y min-h-[400px] leading-relaxed"
                  />
                </div>

                {showDiff && isTemplateOverride && (
                  <div className="relative">
                    <textarea
                      value={currentData.template_default}
                      readOnly
                      rows={20}
                      className="w-full p-4 border-2 border-gray-200 rounded-xl bg-gray-50 text-gray-500 text-sm font-mono resize-none min-h-[400px] cursor-default leading-relaxed"
                    />
                    <span className="absolute top-2 right-2 px-2 py-0.5 text-xs bg-gray-200 text-gray-500 rounded font-medium">
                      Default
                    </span>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
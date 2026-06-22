import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEditor } from './EditorContext';
import { api } from '@/lib/api';
import { Button } from '../ui/Button';
import { ChevronLeft, Globe, BookOpen, Settings, User, Trash2, Loader2, Play, Bot, Check, RefreshCw, FileCode } from 'lucide-react';

const STYLE_OPTIONS = [
  { value: "男频-热血玄幻", label: "⚔️ 热血玄幻" },
  { value: "男频-系统数据", label: "📊 系统数据" },
  { value: "男频-诡秘智斗", label: "🔮 诡秘智斗" },
  { value: "男频-稳健苟道", label: "🛡️ 稳健苟道" },
  { value: "男频-无敌碾压", label: "👑 无敌碾压" },
  { value: "男频-末世废土", label: "☢️ 末世废土" },
  { value: "男频-历史权谋", label: "🏛️ 历史权谋" },
  { value: "女频-古言权谋", label: "🌸 古言权谋" },
  { value: "女频-现言救赎", label: "💝 现言救赎" }
];

interface ProviderModel {
  provider: string;
  providerName: string;
  providerIcon: string;
  enabled: boolean;
  models: Array<{
    model_name: string;
    display_name: string;
    is_default: boolean;
  }>;
  current_model: string;
}

interface ActiveLLM {
  provider: string;
  model: string;
}

function Expander({ title, icon: Icon, children, defaultOpen = false }: { title: string, icon: any, children: React.ReactNode, defaultOpen?: boolean }) {
  return (
    <details className="group border-b border-gray-100 last:border-0" open={defaultOpen}>
      <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors font-medium text-gray-800 list-none">
        <Icon className="w-4 h-4 text-blue-500" />
        <span className="flex-1">{title}</span>
        <span className="text-gray-400 group-open:rotate-180 transition-transform">▼</span>
      </summary>
      <div className="px-4 pb-4 pt-1 text-sm text-gray-600">
        {children}
      </div>
    </details>
  );
}

export function Sidebar({ bookId }: { bookId: string }) {
  const navigate = useNavigate();
  const { 
    worldConfig, bookPlan, heroStatus, nextChap,
    writerStyle, setWriterStyle, refreshData, setThreadId,
    setActiveSection, setCurrentOutline, setFinalDraft, setBrainstormIdeas,
    setCurrentModel, generateMode
  } = useEditor();

  const [intro, setIntro] = useState(worldConfig?.intro || '');
  const [powerSystem, setPowerSystem] = useState(
    typeof worldConfig?.power_system === 'object' 
      ? JSON.stringify(worldConfig.power_system, null, 2) 
      : String(worldConfig?.power_system || '')
  );
  const [isUpdating, setIsUpdating] = useState(false);
  
  // 自定义风格卡
  const [customStyles, setCustomStyles] = useState<string[]>([]);

  // 模型切换相关状态
  const [providerModels, setProviderModels] = useState<ProviderModel[]>([]);
  const [activeLLM, setActiveLLM] = useState<ActiveLLM>({ provider: '', model: '' });
  const [switchingModel, setSwitchingModel] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(true);

  // 从配置加载所有提供商及其模型
  const loadProviderModels = useCallback(async () => {
    try {
      const data = await api.getLLMProviders();
      const providers: ProviderModel[] = (data.providers || []).map((p: any) => ({
        provider: p.provider,
        providerName: p.name,
        providerIcon: p.icon,
        enabled: p.enabled,
        models: p.models || [],
        current_model: p.current_model || '',
      }));
      setProviderModels(providers);
      setActiveLLM(data.active || { provider: '', model: '' });
      
      // 同步当前模型到 context
      if (data.active?.model) {
        setCurrentModel(data.active.model);
      }
    } catch (e) {
      console.error('Failed to load provider models', e);
    } finally {
      setModelsLoading(false);
    }
  }, [setCurrentModel]);

  useEffect(() => {
    loadProviderModels();
  }, [loadProviderModels]);

  // 加载自定义风格卡列表
  useEffect(() => {
    api.getStyleCards().then(setCustomStyles).catch(() => {});
  }, []);

  const handleSwitchModel = async (provider: string, modelName: string) => {
    if (switchingModel) return;
    setSwitchingModel(true);
    try {
      await api.switchLLMProvider(provider, modelName);
      setCurrentModel(modelName);
      setActiveLLM({ provider, model: modelName });
      // 刷新提供商列表以更新 current_model
      await loadProviderModels();
    } catch (err) {
      console.error('切换模型失败:', err);
      alert('切换模型失败，请检查该提供商是否已配置 API Key');
    } finally {
      setSwitchingModel(false);
    }
  };

  const handleUpdateWorld = async () => {
    setIsUpdating(true);
    try {
      await api.updateWorldConfig(bookId, intro, powerSystem);
      await refreshData();
    } catch (e) {
      alert('更新失败');
    } finally {
      setIsUpdating(false);
    }
  };

  const [batchCount, setBatchCount] = useState(1);
  const [autoArchive, setAutoArchive] = useState(true);
  const [isBatching, setIsBatching] = useState(false);

  const handleBatchProduce = async () => {
    if (isBatching) return;
    setIsBatching(true);
    
    try {
      for (let i = 0; i < batchCount; i++) {
        const resp = await api.generateContent({
          book_id: bookId,
          chapter_num: nextChap + i,
          user_intent: "剧情继续发展，保持连贯性",
          style: writerStyle,
          is_batch_mode: true,
          thread_id: crypto.randomUUID(),
          generate_mode: generateMode,
        });

        if (!resp.draft) throw new Error("Batch generation failed");

        if (autoArchive) {
          const analysis = await api.analyzeDraft(bookId, resp.draft);
          
          let parsed = analysis;
          if (typeof analysis === 'string') {
            try {
              const clean = analysis.replace(/^```json\s*/m, '').replace(/```$/m, '');
              parsed = JSON.parse(clean.match(/\{[\s\S]*\}/)?.[0] || '{}');
            } catch(e) {
              parsed = { summary: "", character_updates: {}, new_entities: [] };
            }
          }

          const rawUpdates = parsed.character_updates || {};
          const safeUpdates: any[] = [];
          if (typeof rawUpdates === 'object' && !Array.isArray(rawUpdates)) {
            Object.entries(rawUpdates).forEach(([name, data]: [string, any]) => {
              if (typeof data === 'object' && !Array.isArray(data)) {
                safeUpdates.push({ name, mental_state: data.mental_state || data.state || '状态更新', physical_tags: data.tags || [] });
              } else if (Array.isArray(data)) {
                safeUpdates.push({ name, mental_state: '状态更新', physical_tags: data });
              }
            });
          }

          const detectedEntities = parsed.new_entities || [];
          const newEnts = detectedEntities.filter((e: any) => e.name).map((e: any) => ({
            name: e.name, type: e.type || 'Item', desc: e.desc || '', owner: e.owner || '', importance: e.importance || 1
          }));

          let chapTitle = resp.outline?.chapter_title || `第 ${nextChap + i} 章`;
          if (!chapTitle.includes('第')) chapTitle = `第 ${nextChap + i} 章：${chapTitle}`;
          
          await api.archiveChapter(bookId, {
            chapter_num: nextChap + i,
            title: chapTitle,
            content: resp.draft,
            summary: parsed.summary || "",
            character_updates: safeUpdates,
            new_entities: newEnts
          });
        } else {
          setFinalDraft(resp.draft);
          setActiveSection('draft');
          break;
        }
      }
      
      if (autoArchive) {
        alert(`批量生成完成！共 ${batchCount} 章。`);
        resetSession();
        refreshData();
      }
    } catch (e) {
      console.error(e);
      alert('批量生成中断');
    } finally {
      setIsBatching(false);
    }
  };

  const handleAdvanceVolume = async (v_idx: number) => {
    try {
      await api.updateBookPlanField(bookId, "current_volume", v_idx + 2);
      await refreshData();
    } catch (e) {
      alert('切换失败');
    }
  };

  const resetSession = () => {
    setThreadId(crypto.randomUUID());
    setFinalDraft('');
    setCurrentOutline(null);
    setBrainstormIdeas([]);
    setActiveSection('create');
  };

  // Progress logic
  let progress = 0;
  let localNum = 1;
  let estLen = 50;
  let v_idx = 0;
  let volumes: any[] = [];
  
  if (bookPlan) {
    v_idx = (bookPlan.current_volume || 1) - 1;
    volumes = bookPlan.volumes || [];
    if (v_idx >= 0 && v_idx < volumes.length) {
      const currVol = volumes[v_idx];
      estLen = currVol.estimated_chapters || 50;
      let startOffset = 0;
      for (let i = 0; i < v_idx; i++) {
        startOffset += volumes[i].estimated_chapters || 50;
      }
      localNum = Math.max(1, nextChap - startOffset);
      progress = Math.min(localNum / estLen, 1.0);
    }
  }

  // 当前激活的提供商信息
  const activeProviderInfo = providerModels.find(p => p.provider === activeLLM.provider);
  const enabledProviders = providerModels.filter(p => p.enabled);

  return (
    <div className="flex-1 overflow-y-auto flex flex-col bg-white">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 sticky top-0 bg-white/90 backdrop-blur z-10 flex flex-col gap-3">
        <button 
          onClick={() => navigate('/')}
          className="flex items-center justify-center gap-2 py-2 px-4 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          返回书架
        </button>
        
        {/* 当前模型状态指示器 */}
        {activeProviderInfo && activeLLM.model && (
          <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg border border-blue-100">
            <span className="text-sm">{activeProviderInfo.providerIcon}</span>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-blue-600 font-medium">{activeProviderInfo.providerName}</div>
              <div className="text-xs text-blue-800 font-mono truncate">{activeLLM.model}</div>
            </div>
            <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="已连接" />
          </div>
        )}
      </div>

      <div className="flex-1 divide-y divide-gray-100">
        {/* World Wiki */}
        <Expander title="世界维基" icon={Globe}>
          {worldConfig ? (
            <div className="space-y-3">
              <textarea 
                className="w-full text-xs p-2 border rounded-md resize-y" 
                rows={4} 
                value={intro || worldConfig.intro} 
                onChange={(e) => setIntro(e.target.value)} 
                placeholder="世界简介"
              />
              <textarea 
                className="w-full text-xs p-2 border rounded-md resize-y font-mono" 
                rows={3} 
                value={powerSystem || JSON.stringify(worldConfig.power_system || {})} 
                onChange={(e) => setPowerSystem(e.target.value)} 
                placeholder="力量体系 (JSON/文本)"
              />
              <Button size="sm" className="w-full" onClick={handleUpdateWorld} disabled={isUpdating}>
                {isUpdating ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : '💾 更新设定'}
              </Button>
            </div>
          ) : (
             <span className="text-gray-400">暂无世界设定</span>
          )}
        </Expander>

        {/* Book Plan & Progress */}
        <Expander title="全书总纲 & 进度" icon={BookOpen} defaultOpen>
          {bookPlan ? (
            <div className="space-y-4">
              <div className="p-3 bg-blue-50 rounded-lg text-blue-800 text-xs border border-blue-100">
                <span className="font-semibold block mb-1">主线梗概:</span>
                {bookPlan.main_story}
              </div>
              
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-gray-500">
                  <span>第 {v_idx + 1} 卷 / 共 {volumes.length} 卷</span>
                  <span>{localNum} / {estLen} 章</span>
                </div>
                <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full ${progress > 0.9 ? 'bg-red-500' : progress < 0.1 ? 'bg-blue-500' : 'bg-green-500'}`}
                    style={{ width: `${progress * 100}%` }}
                  />
                </div>
                {v_idx >= 0 && v_idx < volumes.length && (
                  <div className="text-xs">
                    <span className="font-medium text-gray-800 block mb-1">{volumes[v_idx].title}</span>
                    <span className="text-gray-600 block">🎯 目标: {volumes[v_idx].goal}</span>
                  </div>
                )}
                
                {(progress > 0.8 || localNum > estLen) && (v_idx + 1 < volumes.length) && (
                  <Button 
                    size="sm" variant="secondary" className="w-full mt-2 text-xs"
                    onClick={() => handleAdvanceVolume(v_idx)}
                  >
                    ⏭️ 强制进入下一卷: {volumes[v_idx + 1].title}
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <span className="text-gray-400">暂无大纲数据</span>
          )}
        </Expander>

        {/* LLM Provider & Model - 重构版 */}
        <Expander title="AI 模型选择" icon={Bot} defaultOpen>
          <div className="space-y-3">
            {modelsLoading ? (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Loader2 className="w-3 h-3 animate-spin" />
                加载模型列表...
              </div>
            ) : enabledProviders.length === 0 ? (
              <div className="text-center py-2">
                <p className="text-xs text-gray-400 mb-2">尚未配置任何提供商</p>
                <Button variant="outline" size="sm" onClick={() => navigate('/settings')} className="w-full">
                  前往配置
                </Button>
              </div>
            ) : (
              <>
                {/* 按提供商分组的模型列表 */}
                {enabledProviders.map(provider => (
                  <div key={provider.provider} className="border border-gray-200 rounded-lg overflow-hidden">
                    {/* 提供商标题 */}
                    <div className="bg-gray-50 px-3 py-2 flex items-center gap-2 border-b border-gray-100">
                      <span>{provider.providerIcon}</span>
                      <span className="text-xs font-medium text-gray-700">{provider.providerName}</span>
                      {activeLLM.provider === provider.provider && (
                        <span className="ml-auto text-xs text-green-600 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                          活跃
                        </span>
                      )}
                    </div>
                    {/* 模型列表 */}
                    <div className="p-1.5 space-y-0.5">
                      {provider.models.map(m => {
                        const isActive = activeLLM.provider === provider.provider && activeLLM.model === m.model_name;
                        return (
                          <button
                            key={m.model_name}
                            onClick={() => {
                              if (!isActive && !switchingModel) {
                                handleSwitchModel(provider.provider, m.model_name);
                              }
                            }}
                            disabled={switchingModel}
                            className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-all ${
                              isActive
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : 'hover:bg-gray-50 text-gray-600 border border-transparent'
                            } ${switchingModel ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                          >
                            {isActive ? (
                              <Check className="w-3 h-3 text-blue-500 flex-shrink-0" />
                            ) : (
                              <span className="w-3 h-3 rounded-full border border-gray-300 flex-shrink-0" />
                            )}
                            <span className="font-medium">{m.display_name}</span>
                            <span className="text-gray-400 font-mono text-[10px]">{m.model_name}</span>
                            {switchingModel && !isActive && (
                              <Loader2 className="w-3 h-3 animate-spin ml-auto" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}

                {/* 刷新按钮 */}
                <button
                  onClick={loadProviderModels}
                  className="w-full flex items-center justify-center gap-1 py-1.5 text-xs text-gray-400 hover:text-blue-500 transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                  刷新模型列表
                </button>
              </>
            )}
            
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate('/settings')}
              className="w-full"
            >
              ⚙️ 配置新提供商/模型
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate('/prompts')}
              className="w-full"
            >
              <FileCode className="w-3 h-3 mr-1" />
              Prompt 模板编辑器
            </Button>
          </div>
        </Expander>

        {/* Writer Style */}
        <Expander title="AI 作家风格调校" icon={Settings} defaultOpen>
          <div className="space-y-3">
            <select 
              value={writerStyle}
              onChange={(e) => setWriterStyle(e.target.value)}
              className="w-full p-2 text-sm border border-gray-200 rounded-lg bg-white"
            >
              <optgroup label="预设风格">
                {STYLE_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </optgroup>
              <optgroup label="自定义风格卡">
                {customStyles.map(name => (
                  <option key={`custom-${name}`} value={name}>{`🎨 ${name}`}</option>
                ))}
              </optgroup>
            </select>
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  try {
                    await api.updateBookStyle(bookId, writerStyle);
                    alert('✅ 风格已永久保存到书籍');
                  } catch (e) { alert('保存失败'); }
                }}
                className="flex-1 px-3 py-1.5 text-xs bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                💾 永久修改
              </button>
              <button
                onClick={() => alert('当前风格仅对本次生成有效，不会修改书籍的默认风格')}
                className="flex-1 px-3 py-1.5 text-xs bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200"
              >
                ⚡ 仅当前
              </button>
            </div>
          </div>
        </Expander>

        {/* Hero Status */}
        <Expander title="主角实时状态" icon={User} defaultOpen>
          {heroStatus ? (
            <div className="space-y-3">
              <div>
                <span className="font-bold text-gray-900 block">{heroStatus.name || '未知'}</span>
                <span className="text-xs text-gray-500">身份: {heroStatus.identity || '无'}</span>
              </div>
              
              <div className="p-2 bg-indigo-50 border border-indigo-100 rounded-lg">
                <span className="text-xs font-semibold text-indigo-800 block mb-1">🧠 心理状态:</span>
                <span className="text-sm text-indigo-900">{heroStatus.mental_state || '平静'}</span>
              </div>

              <div>
                <span className="text-xs font-semibold text-gray-700 block mb-1">🏥 身体/装备状态:</span>
                <div className="flex flex-col gap-1">
                  {(heroStatus.physical_tags || []).filter((t:string) => t.trim()).length > 0 ? (
                    heroStatus.physical_tags.map((tag: string, i: number) => (
                      <span key={i} className="text-xs px-2 py-1 bg-red-50 text-red-600 border border-red-100 rounded-md">
                        🚑 {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-green-600">✅ 状态完美 (无负面标签)</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <span className="text-xs text-gray-400">数据同步中...</span>
          )}
        </Expander>

        {/* Batch Production */}
        <Expander title="流水线批量生产" icon={Play}>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-600 block mb-1">连续生成章数</label>
              <input 
                type="number" 
                value={batchCount} 
                onChange={e => setBatchCount(Number(e.target.value))} 
                min={1} max={10} 
                className="w-full p-2 border rounded-md text-sm" 
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-600">
              <input 
                type="checkbox" 
                checked={autoArchive} 
                onChange={e => setAutoArchive(e.target.checked)} 
              />
              启用自动归档 (跳过人工审核)
            </label>
            <Button size="sm" variant="primary" className="w-full" onClick={handleBatchProduce} disabled={isBatching}>
              {isBatching ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Play className="w-4 h-4 mr-1" />}
              {isBatching ? '正在生产中...' : '🔥 启动引擎'}
            </Button>
          </div>
        </Expander>
      </div>

      {/* Footer Actions */}
      <div className="p-4 border-t border-gray-200 bg-gray-50">
        <Button variant="ghost" className="w-full text-red-500 hover:text-red-600 hover:bg-red-50" onClick={resetSession}>
          <Trash2 className="w-4 h-4 mr-2" />
          清空上下文缓存
        </Button>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { useEditor } from './EditorContext';
import { api } from '@/lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Loader2, CheckCircle2, Zap, Brain, X } from 'lucide-react';

export function SceneC({ bookId }: { bookId: string }) {
  const {
    finalDraft, setFinalDraft, currentOutline, nextChap,
    setThreadId, setCurrentOutline, setBrainstormIdeas,
    setActiveSection, isLoading, setIsLoading, refreshData,
    statusChanged, setStatusChanged
  } = useEditor();

  const [showAnalysis, setShowAnalysis] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Parse title from outline or draft
  let plannedTitle = `第 ${nextChap} 章`;
  if (currentOutline) {
    if (typeof currentOutline === 'object' && currentOutline.chapter_title) {
      plannedTitle = currentOutline.chapter_title;
    } else if (typeof currentOutline === 'string') {
      try {
        const clean = currentOutline.replace(/^```json\s*/m, '').replace(/```$/m, '');
        const parsed = JSON.parse(clean.match(/\{[\s\S]*\}/)?.[0] || '{}');
        if (parsed.chapter_title) plannedTitle = parsed.chapter_title;
      } catch (e) { }
    }
  } else if (finalDraft) {
    // 尝试从正文中提取标题（第一行）
    const firstLine = finalDraft.split('\n')[0].trim();
    if (firstLine && firstLine.length > 0 && firstLine.length < 50) {
      plannedTitle = firstLine;
    }
  }
  if (!plannedTitle.includes('第') && !plannedTitle.includes('Chapter')) {
    plannedTitle = `第 ${nextChap} 章：${plannedTitle}`;
  }

  const [finalTitleInput, setFinalTitleInput] = useState(plannedTitle);

  // States for Deep Archive form
  const [editedSummary, setEditedSummary] = useState('');
  const [editedCharsData, setEditedCharsData] = useState<Record<string, any>>({});
  const [editedEntities, setEditedEntities] = useState<any[]>([]);

  const handleQuickArchive = async () => {
    setIsLoading(true);
    try {
      const summaryStr = typeof currentOutline === 'object' ? JSON.stringify(currentOutline) : String(currentOutline);
      await api.archiveChapter(bookId, {
        chapter_num: nextChap,
        title: plannedTitle,
        content: finalDraft,
        summary: summaryStr,
        character_updates: [],
        new_entities: []
      });
      await finishArchive();
    } catch (err) {
      console.error(err);
      alert('快速归档失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeepArchiveClick = async () => {
    setShowAnalysis(true);
    setIsAnalyzing(true);
    try {
      const rawResult = await api.analyzeDraft(bookId, finalDraft);
      
      let parsed = rawResult;
      if (typeof rawResult === 'string') {
        try {
          const clean = rawResult.replace(/^```json\s*/m, '').replace(/```$/m, '');
          parsed = JSON.parse(clean.match(/\{[\s\S]*\}/)?.[0] || '{}');
        } catch (e) {
          parsed = { summary: "", character_updates: {}, new_entities: [] };
        }
      }

      setEditedSummary(parsed.summary || "");

      // Normalize Character Updates
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
      } else if (Array.isArray(rawUpdates)) {
        rawUpdates.forEach(item => {
          if (typeof item === 'object') safeUpdates.push(item);
        });
      }

      const initialCharsData: Record<string, any> = {};
      safeUpdates.forEach(c => {
        initialCharsData[c.name] = { state: c.mental_state, tags: c.physical_tags };
      });
      setEditedCharsData(initialCharsData);

      // Normalize Entities
      const detectedEntities = parsed.new_entities || [];
      setEditedEntities(detectedEntities.map((e: any) => ({
        save: true,
        name: e.name,
        type: e.type || 'Item',
        desc: e.desc || '',
        owner: e.owner || '',
        importance: e.importance || 1
      })));

    } catch (err) {
      console.error(err);
      alert('分析失败');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDeepArchiveSubmit = async () => {
    setIsLoading(true);
    try {
      const charUpdatesList = Object.entries(editedCharsData).map(([name, data]) => ({
        name,
        mental_state: data.state,
        physical_tags: data.tags
      }));

      const entsToSave = editedEntities.filter(e => e.save && e.name).map(e => ({
        name: e.name, type: e.type, desc: e.desc, owner: e.owner, importance: e.importance
      }));

      await api.archiveChapter(bookId, {
        chapter_num: nextChap,
        title: finalTitleInput,
        content: finalDraft,
        summary: editedSummary,
        character_updates: charUpdatesList,
        new_entities: entsToSave
      });

      await finishArchive();
    } catch (err) {
      console.error(err);
      alert('深度归档失败');
    } finally {
      setIsLoading(false);
    }
  };

  const finishArchive = async () => {
    setThreadId(crypto.randomUUID());
    setFinalDraft('');
    setStatusChanged(false);
    setCurrentOutline(null);
    setBrainstormIdeas([]);
    setShowAnalysis(false);
    setActiveSection('create');
    await refreshData(); // Refresh sidebar data
  };

  return (
    <div className="max-w-4xl mx-auto w-full p-8 animate-fade-in pb-32">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 border border-blue-200 mb-4">
          <CheckCircle2 className="w-4 h-4 text-blue-600" />
          <span className="text-sm text-blue-700 font-medium">第三步：最终成稿与归档</span>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 mb-2">✅ 最终成稿</h2>
      </div>

      {/* 状态变化提示 */}
      {statusChanged && (
        <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-3">
          <div className="w-8 h-8 bg-amber-100 rounded-full flex items-center justify-center">
            <Zap className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <div className="font-medium text-amber-800">检测到状态变化</div>
            <div className="text-sm text-amber-600">主角在本章中发生了实质性改变，建议使用深度归档</div>
          </div>
        </div>
      )}

      <Card padding="lg" className="mb-8 border-t-4 border-t-blue-500">
        <textarea
          value={finalDraft}
          onChange={e => setFinalDraft(e.target.value)}
          className="w-full p-4 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[600px] text-gray-800 leading-loose"
          placeholder="正文内容..."
        />
      </Card>

      {!showAnalysis ? (
        <div className="space-y-6 animate-fade-in-scale">
          <h3 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            💾 章节归档操作
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Button
              size="lg"
              variant="secondary"
              className="w-full flex-col h-auto py-4 items-start gap-1"
              onClick={handleQuickArchive}
              disabled={isLoading}
            >
              <div className="flex items-center gap-2 font-semibold text-gray-900">
                <Zap className="w-5 h-5 text-yellow-500" />
                快速归档 (仅存正文)
              </div>
              <span className="text-xs text-gray-500 font-normal pl-7">适合日常更新，跳过 AI 分析阶段</span>
            </Button>
            
            <Button
              size="lg"
              variant="primary"
              className="w-full flex-col h-auto py-4 items-start gap-1 bg-gradient-to-r from-blue-600 to-indigo-600 border-none shadow-lg shadow-blue-500/20"
              onClick={handleDeepArchiveClick}
              disabled={isLoading}
            >
              <div className="flex items-center gap-2 font-semibold text-white">
                <Brain className="w-5 h-5 text-blue-200" />
                深度归档 (AI分析状态)
              </div>
              <span className="text-xs text-blue-100 font-normal pl-7">自动提取人物状态变更与新出场物品</span>
            </Button>
          </div>
        </div>
      ) : (
        <Card padding="lg" className="mt-8 animate-fade-in bg-white border-2 border-indigo-100 shadow-xl shadow-indigo-100/50">
          <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-100">
            <h3 className="text-xl font-bold text-indigo-900 flex items-center gap-2">
              <Brain className="w-6 h-6 text-indigo-600" />
              全局状态审计
            </h3>
            <Button variant="ghost" size="sm" onClick={() => setShowAnalysis(false)}>
              <X className="w-4 h-4 mr-1" /> 取消
            </Button>
          </div>

          {isAnalyzing ? (
            <div className="py-12 flex flex-col items-center justify-center text-indigo-600">
              <Loader2 className="w-8 h-8 animate-spin mb-4" />
              <p className="font-medium">Maintainer 正在扫描全员状态与新实体...</p>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Title & Summary */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">章节标题</label>
                  <input
                    type="text"
                    value={finalTitleInput}
                    onChange={e => setFinalTitleInput(e.target.value)}
                    className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">本章摘要 (AI 提取)</label>
                  <textarea
                    value={editedSummary}
                    onChange={e => setEditedSummary(e.target.value)}
                    rows={3}
                    className="w-full p-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              {/* Character Updates */}
              <div>
                <h4 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-4 bg-indigo-500 rounded-full"></span>
                  👥 角色状态变更
                </h4>
                {Object.keys(editedCharsData).length === 0 ? (
                  <p className="text-sm text-gray-500 p-4 bg-gray-50 rounded-lg">未检测到显著的角色状态变更。</p>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    {Object.entries(editedCharsData).map(([name, data]) => (
                      <div key={name} className="p-4 border border-indigo-100 bg-indigo-50/30 rounded-xl space-y-3">
                        <div className="font-bold text-indigo-900">{name}</div>
                        <div>
                          <label className="text-xs text-gray-500 block mb-1">心理/阶段状态</label>
                          <input
                            type="text"
                            value={data.state}
                            onChange={e => setEditedCharsData({ ...editedCharsData, [name]: { ...data, state: e.target.value } })}
                            className="w-full p-2 text-sm border border-gray-200 rounded-md"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-gray-500 block mb-1">特征标签 (逗号分隔)</label>
                          <input
                            type="text"
                            value={Array.isArray(data.tags) ? data.tags.join(',') : data.tags}
                            onChange={e => {
                              const arr = e.target.value.split(',').map(s => s.trim()).filter(s => s);
                              setEditedCharsData({ ...editedCharsData, [name]: { ...data, tags: arr } });
                            }}
                            className="w-full p-2 text-sm border border-gray-200 rounded-md"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* New Entities */}
              <div>
                <h4 className="text-sm font-bold text-gray-900 mb-3 flex items-center gap-2">
                  <span className="w-1.5 h-4 bg-purple-500 rounded-full"></span>
                  ✨ 新实体注册
                </h4>
                {editedEntities.length === 0 ? (
                  <p className="text-sm text-gray-500 p-4 bg-gray-50 rounded-lg">未检测到新实体（法宝、地点、势力等）。</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-gray-200">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="p-3 w-16 text-center">入库</th>
                          <th className="p-3">名称</th>
                          <th className="p-3">类型</th>
                          <th className="p-3">描述</th>
                          <th className="p-3">归属</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {editedEntities.map((e, idx) => (
                          <tr key={idx} className="hover:bg-gray-50/50">
                            <td className="p-3 text-center">
                              <input
                                type="checkbox"
                                checked={e.save}
                                onChange={ev => {
                                  const newEnts = [...editedEntities];
                                  newEnts[idx].save = ev.target.checked;
                                  setEditedEntities(newEnts);
                                }}
                                className="rounded text-indigo-600 focus:ring-indigo-500"
                              />
                            </td>
                            <td className="p-3">
                              <input value={e.name} onChange={ev => { const n = [...editedEntities]; n[idx].name = ev.target.value; setEditedEntities(n); }} className="w-full p-1 border rounded" />
                            </td>
                            <td className="p-3">
                              <input value={e.type} onChange={ev => { const n = [...editedEntities]; n[idx].type = ev.target.value; setEditedEntities(n); }} className="w-full p-1 border rounded" />
                            </td>
                            <td className="p-3">
                              <input value={e.desc} onChange={ev => { const n = [...editedEntities]; n[idx].desc = ev.target.value; setEditedEntities(n); }} className="w-full p-1 border rounded" />
                            </td>
                            <td className="p-3">
                              <input value={e.owner} onChange={ev => { const n = [...editedEntities]; n[idx].owner = ev.target.value; setEditedEntities(n); }} className="w-full p-1 border rounded" />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Submit */}
              <div className="pt-6 border-t border-gray-100 flex justify-end">
                <Button size="lg" onClick={handleDeepArchiveSubmit} disabled={isLoading} className="bg-indigo-600 hover:bg-indigo-700 text-white w-full sm:w-auto">
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <CheckCircle2 className="w-5 h-5 mr-2" />}
                  确认全员更新并归档
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

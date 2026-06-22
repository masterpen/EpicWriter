import { useState, useEffect } from 'react';
import { useEditor } from './EditorContext';
import { api } from '@/lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Sparkles, Loader2, Edit3, X, Check, Eye } from 'lucide-react';

export function SceneB({ bookId: _bookId }: { bookId: string }) {
  const {
    currentOutline, setCurrentOutline, threadId, writerStyle,
    nextChap, setActiveSection, setFinalDraft, setStatusChanged, isLoading, setIsLoading
  } = useEditor();

  const [plannedTitle, setPlannedTitle] = useState('');
  const [editedOutlineText, setEditedOutlineText] = useState('');
  const [pacingNote, setPacingNote] = useState('');
  const [showDebug, setShowDebug] = useState(false);

  useEffect(() => {
    if (currentOutline) {
      let title = `第 ${nextChap} 章`;
      let text = '';
      let note = '';

      if (typeof currentOutline === 'object' && !Array.isArray(currentOutline)) {
        title = currentOutline.chapter_title || title;
        const scenes = currentOutline.scenes || [];
        text = Array.isArray(scenes) ? scenes.map(s => typeof s === 'string' ? s : s.plot_summary || JSON.stringify(s)).join('\n\n') : String(scenes);
        note = currentOutline.pacing_note || '';
      } else if (Array.isArray(currentOutline)) {
        text = currentOutline.map(s => typeof s === 'string' ? s : s.plot_summary || JSON.stringify(s)).join('\n\n');
      } else if (typeof currentOutline === 'string') {
        try {
          const cleanText = currentOutline.replace(/^```json\s*/m, '').replace(/```$/m, '');
          const match = cleanText.match(/\{[\s\S]*\}/);
          if (match) {
            const parsed = JSON.parse(match[0]);
            title = parsed.chapter_title || title;
            const scenes = parsed.scenes || [];
            text = Array.isArray(scenes) ? scenes.join('\n\n') : String(scenes);
            note = parsed.pacing_note || '';
          } else {
            text = currentOutline;
          }
        } catch (e) {
          text = currentOutline;
        }
      }

      setPlannedTitle(title);
      setEditedOutlineText(text);
      setPacingNote(note);
    }
  }, [currentOutline, nextChap]);

  const handleApprove = async () => {
    setIsLoading(true);
    try {
      const finalScenesList = editedOutlineText
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0);

      const resp = await api.approveOutline(
        threadId,
        plannedTitle,
        finalScenesList,
        writerStyle
      );

      if (resp?.draft) {
        setFinalDraft(resp.draft);
        setStatusChanged(resp.status_changed || false);
        setCurrentOutline(null);
        setActiveSection('draft');
      } else {
        alert("后端请求失败，未返回正文。");
      }
    } catch (err) {
      console.error(err);
      alert('Writer 运行出错');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMockGenerate = () => {
    const mockText = `# ${plannedTitle} (模拟)
    
这是一个测试生成的正文段落。如果看到这句话，说明状态流转逻辑已经通了。

当前文风设置：${writerStyle}`;
    setFinalDraft(mockText);
    setCurrentOutline(null);
    setActiveSection('draft');
  };

  const handleReject = () => {
    setCurrentOutline(null);
    setActiveSection('create');
  };

  return (
    <div className="max-w-4xl mx-auto w-full p-8 animate-fade-in pb-32">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 border border-blue-200 mb-4">
          <Edit3 className="w-4 h-4 text-blue-600" />
          <span className="text-sm text-blue-700 font-medium">第二步：大纲审核 (第 {nextChap} 章)</span>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 mb-2">{plannedTitle}</h2>
      </div>

      {pacingNote && (
        <div className="mb-6 p-4 bg-indigo-50 border border-indigo-100 rounded-xl flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-indigo-500 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-sm font-semibold text-indigo-900 mb-1">AI 节奏提示</h4>
            <p className="text-sm text-indigo-800">{pacingNote}</p>
          </div>
        </div>
      )}

      <Card padding="lg" className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900">编辑大纲 (每行一个场景)</h3>
          <Button variant="ghost" size="sm" onClick={() => setShowDebug(!showDebug)}>
            <Eye className="w-4 h-4 mr-1" /> Debug
          </Button>
        </div>

        {showDebug && (
          <pre className="mb-4 p-4 bg-gray-900 text-green-400 rounded-lg text-xs overflow-x-auto max-h-48">
            {JSON.stringify(currentOutline, null, 2)}
          </pre>
        )}

        <textarea
          value={editedOutlineText}
          onChange={e => setEditedOutlineText(e.target.value)}
          className="w-full p-4 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[300px] text-gray-700 leading-relaxed"
          placeholder="请输入场景描述..."
        />
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Button
          size="lg"
          variant="primary"
          className="w-full"
          onClick={handleApprove}
          disabled={isLoading}
        >
          {isLoading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <Check className="w-5 h-5 mr-2" />}
          批准并生成正文
        </Button>
        <Button
          size="lg"
          variant="secondary"
          className="w-full"
          onClick={handleMockGenerate}
          disabled={isLoading}
        >
          🧪 模拟生成
        </Button>
        <Button
          size="lg"
          variant="ghost"
          className="w-full text-red-600 hover:bg-red-50 hover:text-red-700 border border-red-200"
          onClick={handleReject}
          disabled={isLoading}
        >
          <X className="w-5 h-5 mr-2" />
          驳回 / 重新规划
        </Button>
      </div>
    </div>
  );
}

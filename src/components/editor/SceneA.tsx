import { useEffect } from 'react';
import { useEditor } from './EditorContext';
import { api } from '@/lib/api';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { Sparkles, Zap, Hash, ChevronRight, Loader2, Lightbulb, GitBranch, Layers } from 'lucide-react';

const QUICK_PROMPTS = [
  '主角获得新能力，开始反击',
  '反派出现，主角被逼入绝境',
  '重要盟友加入，队伍壮大',
  '感情线发展，人物关系升温',
  '揭秘世界观，展开宏大背景'
];

export function SceneA({ bookId }: { bookId: string }) {
  const {
    heroStatus, worldConfig, nextChap, userIntent, setUserIntent,
    brainstormIdeas, setBrainstormIdeas, isLoading, setIsLoading,
    setCurrentOutline, setActiveSection, threadId, writerStyle, currentModel,
    generateMode, setGenerateMode
  } = useEditor();

  useEffect(() => {
    if (!userIntent) {
      const heroName = heroStatus?.name || '主角';
      const defaultIntent = `【当前主角：${heroName}】\n请输入本章模糊意图。例如：${heroName}到达了新地图，遇到突发状况...`;
      setUserIntent(defaultIntent);
    }
  }, [heroStatus, userIntent, setUserIntent]);

  const handleBrainstorm = async (isAuto: boolean) => {
    setIsLoading(true);
    try {
      const intent = isAuto
        ? "【指令】用户未提供具体意图。请完全基于《全书总纲》的当前分卷目标，以及上一章的结尾，自动推演剧情的后续发展。"
        : userIntent;
        
      const ideas = await api.generateBrainstormingOptions(intent, nextChap, bookId);
      setBrainstormIdeas(Array.isArray(ideas) ? ideas : []);
    } catch (err) {
      console.error(err);
      alert('构思失败，请检查服务是否运行。');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectIdea = async (idea: any) => {
    setIsLoading(true);
    try {
      const finalIntent = `【用户原始意图】\n${userIntent}\n\n【选定剧情走向 (方案${idea.option || 'X'})】\n标题：${idea.title}\n剧情：${idea.desc}`;
      
      const resp = await api.generateContent({
        book_id: bookId,
        chapter_num: nextChap,
        user_intent: finalIntent,
        style: writerStyle,
        is_batch_mode: false,
        thread_id: threadId,
        generate_mode: generateMode
      });
      
      if (resp.outline) {
        setCurrentOutline(resp.outline);
        setBrainstormIdeas([]);
        setActiveSection('outline');
      } else {
        alert("未返回大纲数据");
      }
    } catch (err) {
      console.error(err);
      alert('生成大纲失败');
    } finally {
      setIsLoading(false);
    }
  };

  const disableInput = brainstormIdeas.length > 0;

  return (
    <div className="max-w-4xl mx-auto w-full p-8 animate-fade-in pb-32">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 border border-blue-200 mb-4">
          <Lightbulb className="w-4 h-4 text-blue-600" />
          <span className="text-sm text-blue-700 font-medium">第一步：编剧室 (Idea & Plan)</span>
        </div>
        <h2 className="text-3xl font-bold text-gray-900 mb-2">输入本章意图</h2>
        {currentModel && (
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-gray-100 text-gray-600 text-xs mb-4">
            <span className="font-medium">当前模型:</span>
            <span>{currentModel}</span>
          </div>
        )}
        {worldConfig?.intro && (
          <p className="text-gray-600 text-sm max-w-2xl mx-auto">
            🌍 世界基调：{worldConfig.intro.slice(0, 50)}...
          </p>
        )}
      </div>

      <div className="space-y-3 mb-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 font-medium flex items-center gap-2">
            <Hash className="w-4 h-4" /> 快速选择
          </p>
          {/* Generate mode toggle */}
          <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg p-1">
            <button
              onClick={() => setGenerateMode('scenes')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                generateMode === 'scenes' ? 'bg-blue-100 text-blue-700' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              <GitBranch className="w-3.5 h-3.5" />
              分镜生成
            </button>
            <button
              onClick={() => setGenerateMode('direct')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                generateMode === 'direct' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              直出一章
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {QUICK_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              disabled={disableInput}
              onClick={() => setUserIntent(prompt)}
              className="px-4 py-2 rounded-full text-sm bg-white border border-gray-200 text-gray-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all duration-300 disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <Card className="relative overflow-hidden mb-8" padding="lg">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500" />
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm text-gray-700 mb-2 font-medium">第 {nextChap} 章 剧情意图</label>
            <textarea
              value={userIntent}
              onChange={e => setUserIntent(e.target.value)}
              disabled={disableInput}
              rows={6}
              className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors resize-none text-gray-700 placeholder-gray-400 disabled:bg-gray-50 disabled:text-gray-500"
            />
            <div className="text-right text-xs text-gray-400 mt-2">
              {userIntent.length} 字
            </div>
          </div>

          {!disableInput && (
            <div className="flex flex-col sm:flex-row gap-3 pt-6 border-t border-gray-100">
              <Button 
                onClick={() => handleBrainstorm(true)} 
                disabled={isLoading} 
                variant="secondary" 
                size="lg"
                className="flex-1"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />}
                自动推演
                <span className="ml-2 text-xs text-gray-500">基于前文自动续写</span>
              </Button>
              <Button 
                onClick={() => handleBrainstorm(false)} 
                disabled={isLoading || !userIntent.trim()} 
                size="lg"
                glow
                className="flex-1"
              >
                {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                三选一构思
                <ChevronRight className="w-4 h-4 ml-auto" />
              </Button>
            </div>
          )}
        </div>
      </Card>

      {/* Brainstorm Ideas */}
      {brainstormIdeas.length > 0 && (
        <div className="space-y-4 animate-fade-in-scale">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">请选择一个剧情走向</h3>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setBrainstormIdeas([])}>
              🔄 不满意，重新输入
            </Button>
          </div>
          
          <div className="grid gap-4 md:grid-cols-3">
            {brainstormIdeas.map((idea, idx) => (
              <Card
                key={idx}
                hover
                padding="md"
                className="cursor-pointer group flex flex-col h-full"
              >
                <div className="flex-1 space-y-3">
                  <div className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-bold text-sm mb-2">
                    {idea.option || ['A', 'B', 'C'][idx]}
                  </div>
                  <h4 className="font-semibold text-gray-900 text-lg group-hover:text-blue-600 transition-colors">
                    {idea.title}
                  </h4>
                  <p className="text-gray-600 text-sm leading-relaxed">{idea.desc}</p>
                  
                  {idea.impact && (
                    <div className="pt-3 mt-3 border-t border-gray-100">
                      <p className="text-xs font-medium text-gray-800 mb-1">🎯 影响:</p>
                      <p className="text-xs text-gray-600">{idea.impact}</p>
                    </div>
                  )}
                </div>
                <div className="pt-4 mt-4">
                  <Button 
                    variant="primary" 
                    className="w-full"
                    onClick={() => handleSelectIdea(idea)}
                    disabled={isLoading}
                  >
                    🎬 选用方案 {idea.option || ['A', 'B', 'C'][idx]}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

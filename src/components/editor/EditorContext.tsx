import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { api } from '@/lib/api';
import type { WorldConfig, BookPlan } from '@/types/editor';

interface EditorContextType {
  bookId: string;
  threadId: string;
  setThreadId: (id: string) => void;
  activeSection: 'create' | 'outline' | 'draft';
  setActiveSection: (s: 'create' | 'outline' | 'draft') => void;
  generateMode: 'scenes' | 'direct';
  setGenerateMode: (m: 'scenes' | 'direct') => void;
  writerStyle: string;
  setWriterStyle: (s: string) => void;
  currentModel: string;
  setCurrentModel: (m: string) => void;
  
  // Data
  worldConfig: WorldConfig | null;
  bookPlan: BookPlan | null;
  heroStatus: any | null; // using any since it's dynamic
  activeChars: any[];
  nextChap: number;
  
  // App state
  userIntent: string;
  setUserIntent: (i: string) => void;
  brainstormIdeas: any[];
  setBrainstormIdeas: (ideas: any[]) => void;
  currentOutline: any | null;
  setCurrentOutline: (outline: any) => void;
  finalDraft: string;
  setFinalDraft: (draft: string) => void;
  statusChanged: boolean;
  setStatusChanged: (changed: boolean) => void;
  
  // Actions
  refreshData: () => Promise<void>;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
}

const EditorContext = createContext<EditorContextType | undefined>(undefined);

export function EditorProvider({ bookId, children }: { bookId: string, children: ReactNode }) {
  const [threadId, setThreadId] = useState<string>(crypto.randomUUID());
  const [activeSection, setActiveSection] = useState<'create' | 'outline' | 'draft'>('create');
  const [generateMode, setGenerateMode] = useState<'scenes' | 'direct'>('scenes');
  const [writerStyle, setWriterStyle] = useState("男频-系统数据");
  
  const [worldConfig, setWorldConfig] = useState<WorldConfig | null>(null);
  const [bookPlan, setBookPlan] = useState<BookPlan | null>(null);
  const [heroStatus, setHeroStatus] = useState<any | null>(null);
  const [activeChars, setActiveChars] = useState<any[]>([]);
  const [nextChap, setNextChap] = useState(1);
  
  const [userIntent, setUserIntent] = useState('');
  const [brainstormIdeas, setBrainstormIdeas] = useState<any[]>([]);
  const [currentOutline, setCurrentOutline] = useState<any>(null);
  const [finalDraft, setFinalDraft] = useState('');
  const [statusChanged, setStatusChanged] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);

  const refreshData = async () => {
    try {
      const [bookInfo, world, plan, num, llmConfig] = await Promise.all([
        api.getBook(bookId).catch(() => null),
        api.getWorldConfig(bookId).catch(() => null),
        api.getBookPlan(bookId).catch(() => null),
        api.getNextChapterNum(bookId).catch(() => 1),
        api.getLLMConfig().catch(() => null),
      ]);
      
      // 从DB恢复的配置中获取当前模型
      let modelName = '';
      const currentProvider = llmConfig?.current_provider || 'deepseek';
      
      // 优先使用 current_model（全局当前模型）
      if (llmConfig?.current_model) {
        modelName = llmConfig.current_model;
      } else if (llmConfig && llmConfig[currentProvider]) {
        // 回退到 provider 配置的 current_model
        const providerConfig = llmConfig[currentProvider];
        if (providerConfig?.current_model) {
          modelName = providerConfig.current_model;
        }
      }
      
      // 如果仍然没有获取到模型，设置默认值
      if (!modelName) {
        if (currentProvider === 'deepseek') modelName = 'deepseek-chat';
        else if (currentProvider === 'openai') modelName = 'gpt-4o';
        else if (currentProvider === 'anthropic') modelName = 'claude-3-5-sonnet-20241022';
        else if (currentProvider === 'openrouter') modelName = 'anthropic/claude-3.5-sonnet';
        else modelName = 'gpt-4o';
      }
      
      setCurrentModel(modelName);
      
      // 从书籍信息中获取风格，如果没有则使用默认
      if (bookInfo?.style) {
        setWriterStyle(bookInfo.style);
      }
      
      if (world) setWorldConfig(world);
      if (plan) setBookPlan(plan);
      if (num) setNextChap(num);

      try {
        const activeResp = await api.getActiveCharacters(bookId);
        if (activeResp) {
          const allChars = [...(activeResp.main || []), ...(activeResp.support || [])];
          setActiveChars(allChars);
        }
        const heroResp = await api.getHeroStatus(bookId);
        if (heroResp) setHeroStatus(heroResp);
      } catch (e) {
        console.warn("Characters error", e);
      }
    } catch (err) {
      console.error("Failed to load editor data", err);
    }
  };

  useEffect(() => {
    refreshData();
  }, [bookId]);

  return (
<EditorContext.Provider value={{
        bookId, threadId, setThreadId,
        activeSection, setActiveSection,
        generateMode, setGenerateMode,
        writerStyle, setWriterStyle, currentModel, setCurrentModel,
      worldConfig, bookPlan, heroStatus, activeChars, nextChap,
      userIntent, setUserIntent,
      brainstormIdeas, setBrainstormIdeas,
      currentOutline, setCurrentOutline,
      finalDraft, setFinalDraft, statusChanged, setStatusChanged,
      refreshData, isLoading, setIsLoading
    }}>
      {children}
    </EditorContext.Provider>
  );
}

export function useEditor() {
  const context = useContext(EditorContext);
  if (context === undefined) {
    throw new Error('useEditor must be used within an EditorProvider');
  }
  return context;
}

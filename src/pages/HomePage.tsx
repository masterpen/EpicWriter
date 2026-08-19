import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Navigation } from '@/components/ui/Navigation';
import { 
  BookOpen, Plus, Sparkles, Trash2, ArrowRight, Loader2, 
  Wand2, Feather, Zap, Clock, Tag, MessageCircleQuestion
} from 'lucide-react';

// 注意：风格列表的单一来源 (SSOT) 在后端 app/core/style_system.py 的 LEGACY_STYLE_OPTIONS
// 如需新增/修改风格，请同步更新后端 SSOT 和此处
const STYLE_OPTIONS = [
  { value: "男频-热血玄幻", label: "⚔️ 热血玄幻", desc: "高燃战斗，逆天改命" },
  { value: "男频-系统数据", label: "📊 系统数据", desc: "面板升级，数据为王" },
  { value: "男频-诡秘智斗", label: "🔮 诡秘智斗", desc: "悬疑推理，步步为营" },
  { value: "男频-稳健苟道", label: "🛡️ 稳健苟道", desc: "稳扎稳打，长命百岁" },
  { value: "男频-无敌碾压", label: "👑 无敌碾压", desc: "开局巅峰，横推一切" },
  { value: "男频-末世/无限流", label: "☢️ 末世废土", desc: "末日求生，重建文明" },
  { value: "男频-历史权谋", label: "🏛️ 历史权谋", desc: "朝堂博弈，权倾天下" },
  { value: "女频-古言权谋", label: "🌸 古言权谋", desc: "宫廷争斗，凤仪天下" },
  { value: "女频-现言救赎", label: "💝 现言救赎", desc: "都市情缘，温暖治愈" },
];

export default function HomePage() {
  const [books, setBooks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'manual' | 'ai'>('manual');
  const [manualTitle, setManualTitle] = useState('');
  const [idea, setIdea] = useState('');
  const [selectedStyle, setSelectedStyle] = useState(STYLE_OPTIONS[0].value);
  const [chapterCount, setChapterCount] = useState('100');
  const [genesisLoading, setGenesisLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [animatedStats, setAnimatedStats] = useState({ books: 0, words: 0, hours: 0 });
  const navigate = useNavigate();

  useEffect(() => { 
    fetchBooks(); 
    const timer = setTimeout(() => {
      setAnimatedStats({ books: 12, words: 256000, hours: 48 });
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const fetchBooks = async () => {
    try {
      const data = await api.getAllBooks();
      setBooks(Array.isArray(data.books) ? data.books : []);
    } catch (err) { 
      console.error(err); 
    } finally {
      setLoading(false);
    }
  };

  const handleManualCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!manualTitle.trim()) return;
    try {
      await api.createBook(manualTitle);
      setManualTitle('');
      fetchBooks();
    } catch (err) { alert('创建失败'); }
  };

  const handleAIGenesis = async (e: FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) { alert('请输入脑洞'); return; }
    setGenesisLoading(true);
    try {
      const resp = await api.genesisBook(idea, parseInt(chapterCount) || 100, selectedStyle);
      if (resp?.book_id) {
        setTimeout(() => navigate(`/editor/${resp.book_id}`), 1000);
      }
    } catch (err) { alert('生成失败'); }
    finally { setGenesisLoading(false); }
  };

  const handleDelete = async (bookId: string) => {
    try {
      await api.deleteBook(bookId);
      setDeleteConfirm(null);
      fetchBooks();
    } catch (err) { alert('删除失败'); }
  };

  const formatNumber = (num: number) => {
    if (num >= 10000) return (num / 10000).toFixed(1) + 'w';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num.toString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      <Navigation />

      <div className="container mx-auto px-4 sm:px-6 py-8 pb-32">
        {/* Hero Section */}
        <section className="text-center mb-16 animate-fade-in">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-100 border border-blue-200 mb-6">
            <Zap className="w-4 h-4 text-blue-600" />
            <span className="text-sm text-blue-700 font-medium">AI 驱动的小说创作系统</span>
          </div>
          <h1 className="text-5xl sm:text-6xl font-bold mb-4 tracking-tight">
            <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">创作无限可能</span>
          </h1>
          <p className="text-gray-600 text-lg max-w-2xl mx-auto mb-10">
            从灵感到完稿，EpicWriter 助你打造百万字级小说世界
          </p>

          {/* Stats */}
          <div className="flex flex-wrap justify-center gap-8 sm:gap-12">
            <div className="text-center animate-slide-in-up delay-100">
              <div className="text-3xl font-bold text-blue-600">{formatNumber(animatedStats.books)}</div>
              <div className="text-sm text-gray-500">作品数量</div>
            </div>
            <div className="text-center animate-slide-in-up delay-200">
              <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">{formatNumber(animatedStats.words)}</div>
              <div className="text-sm text-gray-500">总字数</div>
            </div>
            <div className="text-center animate-slide-in-up delay-300">
              <div className="text-3xl font-bold text-purple-600">{animatedStats.hours}+</div>
              <div className="text-sm text-gray-500">创作时长</div>
            </div>
          </div>
        </section>

        {/* Create Section */}
        <section className="max-w-3xl mx-auto mb-16 animate-fade-in-scale">
          <Card className="relative overflow-hidden" padding="lg">
            {/* Tab Toggle */}
            <div className="flex p-1 mb-8 bg-gray-100 rounded-xl">
              <button
                onClick={() => setActiveTab('manual')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-medium transition-all duration-300 ${
                  activeTab === 'manual'
                    ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/20'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Feather className="w-4 h-4" />
                手动创建
              </button>
              <button
                onClick={() => setActiveTab('ai')}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-medium transition-all duration-300 ${
                  activeTab === 'ai'
                    ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/20'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Wand2 className="w-4 h-4" />
                AI 创世纪
              </button>
            </div>

            {activeTab === 'manual' ? (
              <form onSubmit={handleManualCreate} className="space-y-6">
                <div>
                  <label className="block text-sm text-gray-700 mb-2 font-medium">作品名称</label>
                  <input
                    type="text"
                    value={manualTitle}
                    onChange={e => setManualTitle(e.target.value)}
                    placeholder="输入你的小说名称..."
                    className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors"
                  />
                </div>
                <Button type="submit" size="lg" glow className="w-full">
                  <Plus className="w-5 h-5" />
                  创建新书
                </Button>
              </form>
            ) : (
              <form onSubmit={handleAIGenesis} className="space-y-6">
                <div>
                  <label className="block text-sm text-gray-700 mb-2 font-medium">创作灵感</label>
                  <textarea
                    value={idea}
                    onChange={e => setIdea(e.target.value)}
                    placeholder="描述你的小说创意，比如：一个被系统选中的程序员穿越到修仙世界，用代码改写天道规则..."
                    rows={4}
                    className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors resize-none"
                  />
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-700 mb-2 font-medium">选择风格</label>
                    <div className="relative">
                      <Tag className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <select
                        value={selectedStyle}
                        onChange={e => setSelectedStyle(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors bg-white"
                      >
                        {STYLE_OPTIONS.map(style => (
                          <option key={style.value} value={style.value}>
                            {style.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      {STYLE_OPTIONS.find(s => s.value === selectedStyle)?.desc}
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-700 mb-2 font-medium">预期篇幅</label>
                    <div className="relative">
                      <BookOpen className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="number"
                        value={chapterCount}
                        onChange={e => setChapterCount(e.target.value)}
                        min="20"
                        max="500"
                        className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none transition-colors"
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-2">章节数（20-500章）</p>
                  </div>
                </div>

                <Button 
                  type="submit" 
                  loading={genesisLoading} 
                  size="lg" 
                  glow 
                  className="w-full"
                >
                  <Sparkles className="w-5 h-5" />
                  {genesisLoading ? 'AI 正在创作中…' : '启动创世纪'}
                </Button>

                <div className="relative flex items-center justify-center gap-4 py-1">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-xs text-gray-400 whitespace-nowrap">或</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                <Button
                  type="button"
                  variant="gradient"
                  size="lg"
                  className="w-full"
                  onClick={() => navigate('/interview', {
                    state: { rawIdea: idea, style: selectedStyle }
                  })}
                >
                  <MessageCircleQuestion className="w-5 h-5" />
                  创作访谈（推荐）
                  <ArrowRight className="w-4 h-4" />
                </Button>
                <p className="text-xs text-gray-400 text-center -mt-2">
                  通过多轮选择题细化设定，比较多套方案后再生成，避免设定空泛
                </p>
              </form>
            )}
          </Card>
        </section>

        {/* Books Section */}
        <section className="animate-fade-in delay-200">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-blue-600" />
              我的书架
            </h2>
            <span className="text-sm text-gray-500">{books.length} 部作品</span>
          </div>

          {loading ? (
            <div className="flex justify-center py-16">
              <div className="flex flex-col items-center gap-4">
                <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
                <p className="text-gray-500">加载中...</p>
              </div>
            </div>
          ) : books.length === 0 ? (
            <Card className="text-center py-16" hover>
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center">
                <BookOpen className="w-10 h-10 text-blue-600" />
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">书架空空如也</h3>
              <p className="text-gray-500 mb-6">开始你的第一部作品吧</p>
              <Button variant="outline" onClick={() => setActiveTab('ai')}>
                <Sparkles className="w-4 h-4" />
                使用 AI 创作
              </Button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {books.map((book, index) => (
                <Card 
                  key={book.book_id} 
                  hover
                  className="group animate-fade-in-scale"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  {/* Book Cover */}
                  <div className="relative h-32 mb-4 rounded-xl overflow-hidden bg-gradient-to-br from-blue-400/20 to-indigo-400/20">
                    <div className="absolute inset-0 flex items-center justify-center">
                      <BookOpen className="w-12 h-12 text-blue-300" />
                    </div>
                    <div className="absolute top-3 right-3 flex gap-1">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-white/90 backdrop-blur-sm text-blue-600">
                        连载中
                      </span>
                    </div>
                  </div>

                  {/* Book Info */}
                  <div className="space-y-2 mb-4">
                    <h3 className="font-semibold text-gray-900 text-lg truncate">
                      {book.title}
                    </h3>
                    <p className="text-xs text-gray-500 font-mono">
                      ID: {book.book_id.slice(0, 8)}...
                    </p>
                    <div className="flex items-center gap-4 text-sm text-gray-600">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        刚刚更新
                      </span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2">
                    {deleteConfirm === book.book_id ? (
                      <>
                        <Button
                          size="sm"
                          variant="gradient"
                          onClick={() => handleDelete(book.book_id)}
                          className="flex-1"
                        >
                          确认删除
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setDeleteConfirm(null)}
                        >
                          取消
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button 
                          variant="primary" 
                          size="sm" 
                          className="flex-1"
                          onClick={() => navigate(`/editor/${book.book_id}`)}
                        >
                          <ArrowRight className="w-4 h-4 mr-1" />
                          继续创作
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleteConfirm(book.book_id)}
                          className="text-red-500 hover:text-red-600 hover:bg-red-50 px-2.5"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

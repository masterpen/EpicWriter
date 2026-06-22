import { Link } from 'react-router-dom';
import { BookOpen, PenTool, Settings, Palette } from 'lucide-react';

export const Navigation = () => {
  return (
    <nav className="sticky top-0 z-50 glass border-b border-white/10 backdrop-blur-xl">
      <div className="container mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/30 group-hover:shadow-xl group-hover:shadow-blue-500/40 transition-all duration-300">
              <PenTool className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900 dark:text-white group-hover:text-blue-500 transition-colors">
              EpicWriter
            </span>
          </Link>

          {/* Navigation Links */}
          <div className="hidden sm:flex items-center gap-6">
            <Link 
              to="/" 
              className="text-gray-600 dark:text-gray-300 hover:text-blue-500 dark:hover:text-blue-400 transition-colors font-medium"
            >
              <BookOpen className="w-5 h-5 inline-block mr-1" />
              我的书架
            </Link>
            <Link 
              to="/styles" 
              className="text-gray-600 dark:text-gray-300 hover:text-blue-500 dark:hover:text-blue-400 transition-colors font-medium"
            >
              <Palette className="w-5 h-5 inline-block mr-1" />
              风格系统
            </Link>
            <Link 
              to="/settings" 
              className="text-gray-600 dark:text-gray-300 hover:text-blue-500 dark:hover:text-blue-400 transition-colors font-medium"
            >
              <Settings className="w-5 h-5 inline-block mr-1" />
              设置
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
};
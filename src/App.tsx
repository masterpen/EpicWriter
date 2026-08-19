import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import AuthPage from './pages/AuthPage';
import HomePage from './pages/HomePage';
import EditorPage from './pages/EditorPage';
import SettingsPage from './pages/SettingsPage';
import PromptEditorPage from './pages/PromptEditorPage';
import StyleEditorPage from './pages/StyleEditorPage';
import CreativeInterviewPage from './pages/CreativeInterviewPage';
import VariantComparePage from './pages/VariantComparePage';
import BiblePreviewPage from './pages/BiblePreviewPage';

// 受保护路由：未登录跳转到 /login，登录后回跳原路径
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        Loading...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage />} />
      <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
      <Route path="/prompts" element={<ProtectedRoute><PromptEditorPage /></ProtectedRoute>} />
      <Route path="/styles" element={<ProtectedRoute><StyleEditorPage /></ProtectedRoute>} />
      <Route path="/interview" element={<ProtectedRoute><CreativeInterviewPage /></ProtectedRoute>} />
      <Route path="/interview/variants" element={<ProtectedRoute><VariantComparePage /></ProtectedRoute>} />
      <Route path="/interview/bible-preview" element={<ProtectedRoute><BiblePreviewPage /></ProtectedRoute>} />
      <Route path="/editor/:id" element={<ProtectedRoute><EditorPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}

export default App;

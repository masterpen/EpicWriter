import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import EditorPage from './pages/EditorPage';
import SettingsPage from './pages/SettingsPage';
import PromptEditorPage from './pages/PromptEditorPage';
import StyleEditorPage from './pages/StyleEditorPage';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/prompts" element={<PromptEditorPage />} />
      <Route path="/styles" element={<StyleEditorPage />} />
      <Route path="/editor/:id" element={<EditorPage />} />
    </Routes>
  );
}

function App() {
  return (
    <Router>
      <AppRoutes />
    </Router>
  );
}

export default App;
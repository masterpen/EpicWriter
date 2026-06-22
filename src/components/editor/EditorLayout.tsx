import { Sidebar } from './Sidebar';
import { SceneA } from './SceneA';
import { SceneB } from './SceneB';
import { SceneC } from './SceneC';

interface EditorLayoutProps {
  bookId: string;
  activeSection: 'create' | 'outline' | 'draft';
}

export function EditorLayout({ bookId, activeSection }: EditorLayoutProps) {
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar - fixed width */}
      <div className="w-80 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <Sidebar bookId={bookId} />
      </div>

      {/* Main Content - scrollable */}
      <div className="flex-1 flex flex-col h-screen overflow-y-auto relative bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
        {activeSection === 'create' && <SceneA bookId={bookId} />}
        {activeSection === 'outline' && <SceneB bookId={bookId} />}
        {activeSection === 'draft' && <SceneC bookId={bookId} />}
      </div>
    </div>
  );
}

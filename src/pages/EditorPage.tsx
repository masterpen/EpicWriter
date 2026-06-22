import { useParams } from 'react-router-dom';
import { EditorProvider, useEditor } from '@/components/editor/EditorContext';
import { EditorLayout } from '@/components/editor/EditorLayout';
import { Card } from '@/components/ui/Card';
import { Sparkles } from 'lucide-react';

const LoadingOverlay = ({ message = 'AI 正在处理中…' }: { message?: string }) => (
  <div className="fixed inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center z-[100]">
    <Card className="px-8 py-6 flex flex-col items-center gap-4" padding="lg">
      <div className="w-10 h-10 border-4 border-blue-500/30 border-t-blue-400 rounded-full animate-spin" />
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-blue-500 animate-pulse" />
        <span className="text-gray-700 font-medium">{message}</span>
      </div>
    </Card>
  </div>
);

function EditorContent({ bookId }: { bookId: string }) {
  const { activeSection, isLoading } = useEditor();

  return (
    <>
      {isLoading && <LoadingOverlay />}
      <EditorLayout bookId={bookId} activeSection={activeSection} />
    </>
  );
}

export default function EditorPage() {
  const { id: bookId } = useParams<{ id: string }>();

  if (!bookId) {
    return <div className="p-8 text-center text-gray-500">Book ID is missing.</div>;
  }

  return (
    <EditorProvider bookId={bookId}>
      <EditorContent bookId={bookId} />
    </EditorProvider>
  );
}

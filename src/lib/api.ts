const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const TOKEN_KEY = 'epicwriter_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'API Error' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }
  
  return response.json();
}

export interface AuthUser {
  user_id: string;
  username: string;
  email: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export const api = {
  // Auth
  register: (username: string, email: string, password: string) =>
    fetchApi<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    }),
  
  login: (username: string, password: string) =>
    fetchApi<LoginResponse>('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
    }),
  
  getCurrentUser: () =>
    fetchApi<AuthUser>('/auth/me'),
  
  // Books
  getAllBooks: () => fetchApi<{ books: any[] }>('/books'),
  
  getBook: (bookId: string) => fetchApi<any>(`/books/${bookId}`),
  
  createBook: (title: string) => 
    fetchApi<{ book_id: string }>('/books', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  
  deleteBook: (bookId: string) =>
    fetchApi<void>(`/books/${bookId}`, { method: 'DELETE' }),
  
  // Update book style
  updateBookStyle: (bookId: string, style: string) =>
    fetchApi<any>(`/books/${bookId}/style`, {
      method: 'PATCH',
      body: JSON.stringify({ style }),
    }),
  
  // Books - AI Genesis
  genesisBook: (idea: string, targetChapters: number, style: string) =>
    fetchApi<{ book_id: string }>('/books/genesis', {
      method: 'POST',
      body: JSON.stringify({ idea, target_chapters: targetChapters, style }),
    }),
  
  // World Config
  getWorldConfig: (bookId: string) => 
    fetchApi<any>(`/books/${bookId}/world`),
    
  updateWorldConfig: (bookId: string, intro: string, powerSystem: string) =>
    fetchApi<any>(`/books/${bookId}/world`, {
      method: 'PATCH',
      body: JSON.stringify({ intro, power_system: powerSystem }),
    }),
  
  // Book Plan
  getBookPlan: (bookId: string) => 
    fetchApi<any>(`/books/${bookId}/plan`),
    
  updateBookPlanField: (bookId: string, field: string, value: any) =>
    fetchApi<any>(`/books/${bookId}/plan`, {
      method: 'PATCH',
      body: JSON.stringify({ [field]: value }),
    }),
  
  // Chapter
  getNextChapterNum: (bookId: string) => 
    fetchApi<number>(`/workflow/chapters/next_num?book_id=${bookId}`).then((res: any) => res.next_num || 1),
  
  // Characters
  getActiveCharacters: (bookId: string) =>
    fetchApi<any>(`/books/${bookId}/characters/active`),
  
  getHeroStatus: (bookId: string) =>
    fetchApi<any>(`/books/${bookId}/characters/hero`),
  
  // Brainstorming
  generateBrainstormingOptions: (intent: string, chapterNum: number, bookId: string) =>
    fetchApi<any[]>('/workflow/brainstorm', {
      method: 'POST',
      body: JSON.stringify({ user_intent: intent, chapter_num: chapterNum, book_id: bookId }),
    }),
  
  // Content Generation
  generateContent: (params: {
    book_id: string;
    chapter_num: number;
    user_intent: string;
    style: string;
    is_batch_mode: boolean;
    thread_id: string;
    generate_mode?: string;
  }) => fetchApi<any>('/workflow/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  }),
  
  // Content Analysis
  analyzeDraft: (bookId: string, content: string) =>
    fetchApi<any>(`/workflow/analyze?book_id=${bookId}`, {
      method: 'POST',
      body: JSON.stringify({
        content: content,
        title: "Analysis",
        summary: ""
      }),
    }),
  
  // Outline
  approveOutline: (threadId: string, chapterTitle: string, scenes: string[], style: string) =>
    fetchApi<any>('/workflow/outline/approve', {
      method: 'PUT',
      body: JSON.stringify({ thread_id: threadId, chapter_title: chapterTitle, scenes, style }),
    }),
  
  // Archive
  archiveChapter: (bookId: string, chapter: any) =>
    fetchApi<void>(`/workflow/chapters/archive?book_id=${bookId}`, {
      method: 'POST',
      body: JSON.stringify(chapter),
    }),
  
  // LLM Config
  getLLMConfig: () => fetchApi<any>('/config/llm'),

  getLLMProviders: () => fetchApi<{ providers: any[]; active: { provider: string; model: string } }>('/config/llm/providers'),

  updateLLMConfig: (config: {
    provider: string;
    api_key: string;
    base_url?: string;
    current_model?: string;
    models?: Array<{ model_name: string; display_name: string; is_default: boolean }>;
    temperature?: number;
    max_tokens?: number;
  }) => fetchApi<any>('/config/llm', {
    method: 'POST',
    body: JSON.stringify(config),
  }),

  switchLLMProvider: (provider: string, model?: string) =>
    fetchApi<any>('/config/llm/switch', {
      method: 'POST',
      body: JSON.stringify({ provider, model }),
    }),

  addModel: (provider: string, modelName: string, displayName: string) =>
    fetchApi<any>('/config/llm/model/add', {
      method: 'POST',
      body: JSON.stringify({ provider, model_name: modelName, display_name: displayName }),
    }),

  removeModel: (provider: string, modelName: string) =>
    fetchApi<any>('/config/llm/model/remove', {
      method: 'POST',
      body: JSON.stringify({ provider, model_name: modelName }),
    }),

  testLLMConnection: (config: {
    provider: string;
    api_key: string;
    base_url?: string;
    current_model?: string;
  }) => fetchApi<any>('/config/llm/test', {
    method: 'POST',
    body: JSON.stringify(config),
  }),

  // Prompt Config
  getAllPrompts: () =>
    fetchApi<Record<string, any>>('/config/prompts'),

  getPromptMeta: () =>
    fetchApi<{ stages: any[] }>('/config/prompts/meta'),

  updatePrompt: (stage: string, system?: string, template?: string) =>
    fetchApi<{ status: string }>(`/config/prompts/${stage}`, {
      method: 'PUT',
      body: JSON.stringify({ system, template }),
    }),

  resetPrompt: (stage: string) =>
    fetchApi<{ status: string }>(`/config/prompts/${stage}`, { method: 'DELETE' }),

  // Style System (五维风格系统)
  getStyleCards: () =>
    fetchApi<string[]>('/styles/'),

  getStyleCard: (name: string) =>
    fetchApi<any>(`/styles/${encodeURIComponent(name)}`),

  createStyleCard: (card: any) =>
    fetchApi<any>('/styles/', {
      method: 'POST',
      body: JSON.stringify(card),
    }),

  deleteStyleCard: (name: string) =>
    fetchApi<any>(`/styles/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  addStyleExample: (name: string, example: { scene_type: string; content: string; source?: string }) =>
    fetchApi<any>(`/styles/${encodeURIComponent(name)}/examples`, {
      method: 'POST',
      body: JSON.stringify(example),
    }),

  removeStyleExample: (name: string, index: number) =>
    fetchApi<any>(`/styles/${encodeURIComponent(name)}/examples/${index}`, { method: 'DELETE' }),

  regenerateStyleInstructions: (name: string) =>
    fetchApi<any>(`/styles/${encodeURIComponent(name)}/regenerate`, { method: 'POST' }),

  migrateLegacyStyles: () =>
    fetchApi<any>('/styles/migrate-legacy', { method: 'POST' }),
};

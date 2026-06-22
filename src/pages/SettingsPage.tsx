import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Settings, Check, Loader2, Key, Globe, Cpu, Plus, Trash2, AlertCircle, RefreshCw } from 'lucide-react';

interface ModelOption {
  model_name: string;
  display_name: string;
  is_default: boolean;
}

interface ProviderInfo {
  provider: string;
  name: string;
  icon: string;
  enabled: boolean;
  current_model: string;
  models: ModelOption[];
}

const PROVIDER_META: Record<string, { name: string; icon: string; baseUrl: string }> = {
  deepseek: { name: 'DeepSeek', icon: '🔥', baseUrl: 'https://api.deepseek.com' },
  openai: { name: 'OpenAI', icon: '🤖', baseUrl: 'https://api.openai.com/v1' },
  openrouter: { name: 'OpenRouter', icon: '🌐', baseUrl: 'https://openrouter.ai/api/v1' },
  anthropic: { name: 'Anthropic', icon: '🧠', baseUrl: 'https://api.anthropic.com' },
  nvidia: { name: 'NVIDIA NIM', icon: '💚', baseUrl: 'https://integrate.api.nvidia.com/v1' },
  custom: { name: '自定义', icon: '⚙️', baseUrl: '' },
};

export default function SettingsPage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeProvider, setActiveProvider] = useState('deepseek');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [newModelName, setNewModelName] = useState('');
  const [newModelDisplay, setNewModelDisplay] = useState('');
  const [loading, setLoading] = useState(true);
  const [configRestored, setConfigRestored] = useState(false);

  const [config, setConfig] = useState({
    api_key: '',
    base_url: '',
    models: [] as ModelOption[],
    current_model: '',
    temperature: 0.7,
    max_tokens: 4096,
  });

  // 加载提供商配置
  const loadProviders = useCallback(async () => {
    try {
      const data = await api.getLLMConfig();
      const list: ProviderInfo[] = [];

      for (const p of ['deepseek', 'openai', 'openrouter', 'anthropic', 'nvidia', 'custom']) {
        const meta = PROVIDER_META[p];
        const raw = data?.[p];
        const models: ModelOption[] = raw?.models || [];

        list.push({
          provider: p,
          name: meta.name,
          icon: meta.icon,
          enabled: raw?.api_key_stored || raw?.enabled || false,
          current_model: raw?.current_model || '',
          models,
        });
      }

      setProviders(list);

      // 恢复当前激活的提供商
      if (data?.current_provider) {
        setActiveProvider(data.current_provider);
      }
      
      // 标记配置已从DB恢复
      if (data?.configured) {
        setConfigRestored(true);
      }
    } catch (e) {
      console.error('Failed to load providers', e);
    }
  }, []);

  // 加载指定提供商的详细配置
  const loadProviderDetail = useCallback(async (providerValue: string) => {
    try {
      const data = await api.getLLMConfig();
      const raw = data?.[providerValue];
      const meta = PROVIDER_META[providerValue];

      setConfig({
        api_key: raw?.api_key_stored ? '••••••••' : (raw?.api_key || ''),
        base_url: raw?.base_url || meta.baseUrl,
        models: raw?.models || [],
        current_model: raw?.current_model || '',
        temperature: raw?.temperature ?? 0.7,
        max_tokens: raw?.max_tokens ?? 4096,
      });
    } catch {
      const meta = PROVIDER_META[providerValue];
      setConfig({
        api_key: '',
        base_url: meta.baseUrl,
        models: [],
        current_model: '',
        temperature: 0.7,
        max_tokens: 4096,
      });
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try {
        const data = await api.getLLMConfig();
        if (data?.current_provider) {
          setActiveProvider(data.current_provider);
        }
        await loadProviders();
        await loadProviderDetail(data?.current_provider || 'deepseek');
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [loadProviders, loadProviderDetail]);

  useEffect(() => {
    if (!loading) {
      loadProviderDetail(activeProvider);
    }
  }, [activeProvider, loading, loadProviderDetail]);

  const handleSave = async () => {
    setSaving(true);
    setTestResult(null);

    try {
      await api.updateLLMConfig({
        provider: activeProvider,
        api_key: config.api_key === '••••••••' ? '' : config.api_key,
        base_url: config.base_url,
        current_model: config.current_model,
        models: config.models.map(m => ({
          model_name: m.model_name,
          display_name: m.display_name,
          is_default: m.is_default,
        })),
        temperature: config.temperature,
        max_tokens: config.max_tokens,
      });

      setConfig(prev => ({ ...prev, api_key: '••••••••' }));
      await loadProviders();
      setConfigRestored(true);
    } catch (e: any) {
      alert('保存失败: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      await api.testLLMConnection({
        provider: activeProvider,
        api_key: config.api_key === '••••••••' ? '' : config.api_key,
        base_url: config.base_url,
        current_model: config.current_model,
      });

      setTestResult({ success: true, message: `API 连接成功！模型: ${config.current_model}` });
    } catch (e: any) {
      setTestResult({ success: false, message: e.message || '连接失败' });
    } finally {
      setTesting(false);
    }
  };

  const handleAddModel = async () => {
    if (!newModelName.trim()) return;

    try {
      await api.addModel(activeProvider, newModelName.trim(), newModelDisplay.trim() || newModelName.trim());
      setNewModelName('');
      setNewModelDisplay('');
      await loadProviderDetail(activeProvider);
      await loadProviders();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleRemoveModel = async (modelName: string) => {
    try {
      await api.removeModel(activeProvider, modelName);
      await loadProviderDetail(activeProvider);
      await loadProviders();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleSetDefaultModel = async (modelName: string) => {
    try {
      await api.updateLLMConfig({
        provider: activeProvider,
        api_key: '',
        base_url: config.base_url,
        current_model: modelName,
        models: config.models.map(m => ({
          ...m,
          is_default: m.model_name === modelName,
        })),
      });

      await api.switchLLMProvider(activeProvider, modelName);
      setConfig(prev => ({ ...prev, current_model: modelName }));
      await loadProviders();
    } catch (e: any) {
      alert('切换失败: ' + e.message);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    await loadProviders();
    await loadProviderDetail(activeProvider);
    setLoading(false);
  };

  const currentMeta = PROVIDER_META[activeProvider];
  const enabledProviders = providers.filter(p => p.enabled);
  const allModels = providers.filter(p => p.enabled).flatMap(p =>
    p.models.map(m => ({ ...m, provider: p.provider, providerName: p.name, providerIcon: p.icon }))
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
          <p className="text-gray-500">正在加载配置...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center">
              <Settings className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">LLM 配置中心</h1>
              <p className="text-gray-500">配置多个 AI 提供商和模型，一次配置持久保存</p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            className="p-2 rounded-lg hover:bg-white/60 text-gray-500 hover:text-blue-600 transition-colors"
            title="刷新配置"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>

        {/* Config Status Bar */}
        {configRestored && enabledProviders.length > 0 && (
          <div className="mb-6 p-4 rounded-xl bg-green-50 border border-green-200 flex items-center gap-3">
            <Check className="w-5 h-5 text-green-600 flex-shrink-0" />
            <div className="flex-1">
              <span className="text-sm text-green-800 font-medium">
                配置已从数据库恢复 · 已配置 {enabledProviders.length} 个提供商 · 共 {allModels.length} 个模型
              </span>
            </div>
          </div>
        )}

        {!configRestored && (
          <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <span className="text-sm text-amber-800">
              尚未检测到已保存的配置。请至少配置一个提供商的 API Key 并保存，配置将持久化到数据库。
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左侧：提供商列表 */}
          <div className="lg:col-span-1">
            <Card padding="lg">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Globe className="w-5 h-5 text-blue-500" />
                提供商
              </h2>
              <div className="space-y-2">
                {providers.map((provider) => (
                  <button
                    key={provider.provider}
                    onClick={() => setActiveProvider(provider.provider)}
                    className={`w-full p-3 rounded-xl border-2 transition-all text-left ${
                      activeProvider === provider.provider
                        ? 'border-blue-500 bg-blue-50 shadow-md'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{provider.icon}</span>
                        <div>
                          <div className="font-medium text-gray-900 text-sm">{provider.name}</div>
                          {provider.enabled && provider.current_model && (
                            <div className="text-xs text-green-600 font-mono">{provider.current_model}</div>
                          )}
                        </div>
                      </div>
                      {provider.enabled ? (
                        <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">已配置</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">未配置</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </Card>
          </div>

          {/* 右侧：配置详情 */}
          <div className="lg:col-span-2 space-y-6">
            <Card padding="lg">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Key className="w-5 h-5 text-blue-500" />
                {currentMeta.icon} {currentMeta.name} 配置
              </h2>

              <div className="space-y-4">
                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={config.api_key}
                    onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                    placeholder="输入 API Key"
                    className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none"
                  />
                  {config.api_key === '••••••••' && (
                    <p className="text-xs text-green-600 mt-1">✓ API Key 已保存（出于安全考虑不显示明文）</p>
                  )}
                </div>

                {/* Base URL */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Base URL
                  </label>
                  <input
                    type="text"
                    value={config.base_url}
                    onChange={(e) => setConfig({ ...config, base_url: e.target.value })}
                    placeholder={currentMeta.baseUrl}
                    className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none"
                  />
                  <p className="text-xs text-gray-400 mt-1">留空将使用默认地址: {currentMeta.baseUrl || '自定义'}</p>
                </div>

                {/* 模型管理 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    可用模型 ({config.models.length})
                  </label>
                  <div className="space-y-2">
                    {config.models.map((m) => (
                      <div
                        key={m.model_name}
                        className={`flex items-center justify-between p-3 rounded-lg border-2 transition-all ${
                          config.current_model === m.model_name
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 text-sm">{m.display_name}</span>
                          <span className="text-xs text-gray-500 font-mono">{m.model_name}</span>
                          {config.current_model === m.model_name && (
                            <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded">当前</span>
                          )}
                          {m.is_default && config.current_model !== m.model_name && (
                            <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">默认</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {config.current_model !== m.model_name && (
                            <button
                              onClick={() => handleSetDefaultModel(m.model_name)}
                              className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
                            >
                              设为当前
                            </button>
                          )}
                          {!m.is_default && config.models.length > 1 && config.current_model !== m.model_name && (
                            <button
                              onClick={() => handleRemoveModel(m.model_name)}
                              className="text-gray-400 hover:text-red-500"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* 添加自定义模型 */}
                  <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                    <p className="text-xs text-gray-500 mb-2">添加自定义模型（无需预设列表，填入模型ID即可）</p>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newModelName}
                        onChange={(e) => setNewModelName(e.target.value)}
                        placeholder="模型ID (如: deepseek-v3, qwen-max)"
                        className="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-blue-500 focus:outline-none"
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAddModel(); }}
                      />
                      <input
                        type="text"
                        value={newModelDisplay}
                        onChange={(e) => setNewModelDisplay(e.target.value)}
                        placeholder="显示名 (可选)"
                        className="w-28 px-3 py-2 text-sm rounded-lg border border-gray-200 focus:border-blue-500 focus:outline-none"
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAddModel(); }}
                      />
                      <button
                        onClick={handleAddModel}
                        disabled={!newModelName.trim()}
                        className="px-3 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        <Plus className="w-4 h-4" />
                        添加
                      </button>
                    </div>
                  </div>
                </div>

                {/* Temperature & Max Tokens */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Temperature ({config.temperature})
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={config.temperature}
                      onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>精确</span>
                      <span>创意</span>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Max Tokens
                    </label>
                    <input
                      type="number"
                      value={config.max_tokens}
                      onChange={(e) => setConfig({ ...config, max_tokens: parseInt(e.target.value) })}
                      className="w-full px-4 py-3 rounded-xl border-2 border-gray-200 focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>

                {/* 测试结果 */}
                {testResult && (
                  <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? (
                        <Check className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-500" />
                      )}
                      <span className={testResult.success ? 'text-green-700' : 'text-red-700'}>
                        {testResult.message}
                      </span>
                    </div>
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex gap-3 pt-4">
                  <Button
                    onClick={handleTest}
                    disabled={testing || (!config.api_key || config.api_key === '••••••••') || !config.current_model}
                    variant="outline"
                  >
                    {testing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Cpu className="w-4 h-4 mr-2" />}
                    测试连接
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={saving}
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                    保存配置
                  </Button>
                </div>
              </div>
            </Card>

            {/* All Models Overview */}
            {enabledProviders.length > 0 && (
              <Card padding="lg">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-blue-500" />
                  所有已配置模型一览
                </h2>
                <div className="space-y-3">
                  {enabledProviders.map(provider => (
                    <div key={provider.provider} className="border border-gray-200 rounded-lg overflow-hidden">
                      <div className="bg-gray-50 px-4 py-2 flex items-center gap-2 border-b border-gray-200">
                        <span className="text-lg">{provider.icon}</span>
                        <span className="font-medium text-gray-900 text-sm">{provider.name}</span>
                        <span className="text-xs text-gray-500 ml-auto">{provider.models.length} 个模型</span>
                      </div>
                      <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {provider.models.map(m => (
                          <div
                            key={m.model_name}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${
                              provider.current_model === m.model_name
                                ? 'bg-blue-50 border border-blue-200'
                                : 'bg-white border border-gray-100'
                            }`}
                          >
                            {provider.current_model === m.model_name ? (
                              <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                            ) : (
                              <span className="w-2 h-2 rounded-full bg-gray-300 flex-shrink-0" />
                            )}
                            <div className="flex-1 min-w-0">
                              <span className="font-medium text-gray-800">{m.display_name}</span>
                              <span className="text-xs text-gray-400 ml-1 font-mono">{m.model_name}</span>
                            </div>
                            {provider.current_model === m.model_name && (
                              <span className="text-xs text-blue-600 flex-shrink-0">活跃</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            <Card className="p-4 bg-blue-50 border-blue-200">
              <p className="text-sm text-blue-800">
                <strong>💡 持久化存储：</strong> 配置保存在 Neo4j 数据库中，服务重启后自动恢复。你可以在编辑器的侧边栏中随时切换不同的提供商和模型。
              </p>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

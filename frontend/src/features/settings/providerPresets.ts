export type AiProviderPreset = {
  id: string
  label: string
  group: 'labs' | 'clouds' | 'local'
  adapter: 'openai_compatible' | 'anthropic' | 'gemini' | 'local_http'
  baseUrl: string
  model: string
  note: string
}

export const AI_PROVIDER_PRESETS: AiProviderPreset[] = [
  { id: 'google-gemini', label: 'Google Gemini', group: 'labs', adapter: 'gemini', baseUrl: 'https://generativelanguage.googleapis.com/v1beta', model: 'gemini-2.5-flash', note: 'Native Gemini REST API' },
  { id: 'anthropic', label: 'Anthropic Claude', group: 'labs', adapter: 'anthropic', baseUrl: 'https://api.anthropic.com', model: 'claude-sonnet-5', note: 'Native Anthropic Messages API' },
  { id: 'openai', label: 'OpenAI', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.openai.com/v1', model: '', note: 'OpenAI Chat Completions API' },
  { id: 'xai', label: 'xAI (Grok)', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.x.ai/v1', model: 'grok-4.6', note: 'Grok Chat Completions API' },
  { id: 'mistral', label: 'Mistral AI', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.mistral.ai/v1', model: 'mistral-small-latest', note: 'Mistral OpenAI-compatible API' },
  { id: 'cohere', label: 'Cohere', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.cohere.ai/compatibility/v1', model: 'command-a-plus-05-2026', note: 'Cohere Compatibility API' },
  { id: 'deepseek', label: 'DeepSeek', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat', note: 'DeepSeek OpenAI-compatible API' },
  { id: 'moonshot', label: 'Moonshot AI (Kimi)', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.moonshot.ai/v1', model: '', note: 'Moonshot OpenAI-compatible API' },
  { id: 'qwen', label: 'Alibaba Qwen (DashScope)', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', note: 'DashScope international compatibility API' },
  { id: 'zai', label: 'Z.ai (GLM)', group: 'labs', adapter: 'openai_compatible', baseUrl: 'https://api.z.ai/api/paas/v4', model: '', note: 'Z.ai OpenAI-compatible API' },

  { id: 'nvidia', label: 'NVIDIA NIM', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://integrate.api.nvidia.com/v1', model: 'nvidia/nemotron-3.5-lightning-30b-a3b', note: 'NVIDIA hosted NIM catalog' },
  { id: 'huggingface', label: 'Hugging Face Inference Providers', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://router.huggingface.co/v1', model: 'openai/gpt-oss-120b:fastest', note: 'Hugging Face multi-provider router' },
  { id: 'groq', label: 'Groq', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.groq.com/openai/v1', model: '', note: 'Groq OpenAI-compatible API' },
  { id: 'openrouter', label: 'OpenRouter', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://openrouter.ai/api/v1', model: '', note: 'Multi-provider model router' },
  { id: 'together', label: 'Together AI', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.together.xyz/v1', model: '', note: 'Together OpenAI-compatible API' },
  { id: 'fireworks', label: 'Fireworks AI', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.fireworks.ai/inference/v1', model: '', note: 'Fireworks OpenAI-compatible API' },
  { id: 'cerebras', label: 'Cerebras Inference', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.cerebras.ai/v1', model: '', note: 'Cerebras OpenAI-compatible API' },
  { id: 'sambanova', label: 'SambaNova Cloud', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.sambanova.ai/v1', model: '', note: 'SambaNova OpenAI-compatible API' },
  { id: 'deepinfra', label: 'DeepInfra', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.deepinfra.com/v1/openai', model: '', note: 'DeepInfra OpenAI-compatible API' },
  { id: 'perplexity', label: 'Perplexity', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.perplexity.ai', model: 'sonar', note: 'Perplexity Sonar API' },
  { id: 'siliconflow', label: 'SiliconFlow', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.siliconflow.com/v1', model: '', note: 'SiliconFlow OpenAI-compatible API' },
  { id: 'novita', label: 'Novita AI', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.novita.ai/v3/openai', model: '', note: 'Novita OpenAI-compatible API' },
  { id: 'hyperbolic', label: 'Hyperbolic', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.hyperbolic.xyz/v1', model: '', note: 'Hyperbolic OpenAI-compatible API' },
  { id: 'nebius', label: 'Nebius AI Studio', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.studio.nebius.ai/v1', model: '', note: 'Nebius OpenAI-compatible API' },
  { id: 'aimlapi', label: 'AI/ML API', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.aimlapi.com/v1', model: '', note: 'AI/ML multi-model API' },
  { id: 'featherless', label: 'Featherless AI', group: 'clouds', adapter: 'openai_compatible', baseUrl: 'https://api.featherless.ai/v1', model: '', note: 'Featherless OpenAI-compatible API' },

  { id: 'ollama', label: 'Ollama', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:11434/v1', model: '', note: 'Local Ollama OpenAI compatibility' },
  { id: 'lmstudio', label: 'LM Studio', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:1234/v1', model: '', note: 'Local LM Studio server' },
  { id: 'localai', label: 'LocalAI', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:8080/v1', model: '', note: 'LocalAI OpenAI-compatible server' },
  { id: 'vllm', label: 'vLLM', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:8000/v1', model: '', note: 'Local vLLM OpenAI server' },
  { id: 'llamacpp', label: 'llama.cpp Server', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:8080/v1', model: '', note: 'llama.cpp OpenAI-compatible server' },
  { id: 'jan', label: 'Jan', group: 'local', adapter: 'local_http', baseUrl: 'http://127.0.0.1:1337/v1', model: '', note: 'Jan local OpenAI-compatible server' },
]

export const AI_PROVIDER_PRESET_GROUPS = [
  { id: 'labs', label: 'Model geliştiricileri' },
  { id: 'clouds', label: 'Inference ve model bulutları' },
  { id: 'local', label: 'Yerel cihaz sağlayıcıları' },
] as const

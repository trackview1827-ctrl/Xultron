from app.models import Provider
from app.providers.adapters import AnthropicAdapter, CustomHTTPAdapter, GeminiAdapter, MockAdapter, OpenAICompatibleAdapter
from app.providers.base import ProviderConfig, ProviderFailure
from app.security.crypto import decrypt_secret

ADAPTERS = {
    "openai_compatible": OpenAICompatibleAdapter,
    "local_http": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "custom_http": CustomHTTPAdapter,
    "mock": MockAdapter,
}

KINDS = {"ai", "stt", "tts"}


def provider_config(provider: Provider) -> ProviderConfig:
    api_key = decrypt_secret(provider.credential.encrypted_api_key) if provider.credential else None
    return ProviderConfig(
        id=provider.id,
        name=provider.name,
        kind=provider.kind,
        adapter=provider.adapter,
        base_url=provider.base_url,
        api_key=api_key,
        model=provider.model,
        temperature=provider.temperature,
        max_tokens=provider.max_tokens,
        streaming=provider.streaming,
        config=provider.config or {},
    )


def build(provider: Provider):
    cls = ADAPTERS.get(provider.adapter)
    if not cls:
        raise ProviderFailure("provider_adapter_not_supported", "Provider adapter is not supported.", 422)
    return cls(provider_config(provider))

from app.models import Provider
from app.providers.adapters import AnthropicAdapter, CodexOAuthAdapter, CustomHTTPAdapter, ElevenLabsAdapter, GeminiAdapter, MockAdapter, OpenAICompatibleAdapter, WhisperCppAdapter
from app.providers.base import ProviderConfig, ProviderFailure
from app.security.crypto import decrypt_secret

ADAPTERS = {
    "openai_compatible": OpenAICompatibleAdapter,
    "local_http": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "custom_http": CustomHTTPAdapter,
    "mock": MockAdapter,
    "openai_codex_oauth": CodexOAuthAdapter,
    "elevenlabs": ElevenLabsAdapter,
    "whisper_cpp": WhisperCppAdapter,
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
        access_token=decrypt_secret(provider.credential.encrypted_access_token) if provider.credential else None,
        refresh_token=decrypt_secret(provider.credential.encrypted_refresh_token) if provider.credential else None,
        account_id=provider.credential.oauth_account_id if provider.credential else None,
        auth_mode="codex_oauth" if provider.credential and provider.credential.encrypted_access_token else "api_key",
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

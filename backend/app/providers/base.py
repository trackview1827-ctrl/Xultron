from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class ProviderConfig:
    id: str
    name: str
    kind: str
    adapter: str
    base_url: str | None
    api_key: str | None
    model: str | None
    temperature: float | None
    max_tokens: int | None
    streaming: bool
    config: dict


class ProviderFailure(Exception):
    def __init__(self, code: str, message: str, status: int = 502, retryable: bool = False):
        self.code = code
        self.message = message
        self.status = status
        self.retryable = retryable
        super().__init__(message)


class AIProvider(Protocol):
    def test(self) -> dict: ...
    def models(self) -> list[dict]: ...
    def complete(self, messages: list[dict]) -> str: ...
    def stream(self, messages: list[dict]) -> Iterable[str]: ...


class STTProvider(Protocol):
    def test(self) -> dict: ...
    def transcribe(self, audio: bytes, filename: str, language: str | None) -> dict: ...


class TTSProvider(Protocol):
    def test(self) -> dict: ...
    def synthesize(self, text: str, voice: str | None) -> tuple[bytes, str]: ...

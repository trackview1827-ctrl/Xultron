"""Generic capability registry used by Xultron's agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


Handler = Callable[[Mapping[str, Any]], Any]
Check = Callable[[], bool]


@dataclass(frozen=True)
class ToolSpec:
    """A tool declaration independent from the model that selected it."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    required_permissions: tuple[str, ...] = ()
    availability_check: Check | None = None
    side_effect: bool = False
    risk_level: str = "low"
    reversible: bool = True
    timeout_seconds: int = 10
    idempotent: bool = True
    verification_strategy: str = "inspect_result"
    handler: Handler | None = None

    def available(self) -> bool:
        return self.availability_check is None or bool(self.availability_check())


class ToolRegistry:
    """Registry for discoverable, metadata-rich agent tools.

    Selection can use the metadata without knowing implementation details. The
    registry deliberately refuses undeclared tools and side effects unless the
    caller explicitly opts in, keeping the default verification path read-only.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        if not spec.name or "." in spec.name and any(not part for part in spec.name.split(".")):
            raise ValueError("tool name must be non-empty and well formed")
        if spec.risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError("unsupported risk level")
        if spec.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> tuple[ToolSpec, ...]:
        return tuple(self._tools.values())

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": dict(tool.input_schema),
                "outputSchema": dict(tool.output_schema),
                "requiredPermissions": list(tool.required_permissions),
                "sideEffect": tool.side_effect,
                "riskLevel": tool.risk_level,
                "reversible": tool.reversible,
                "timeoutSeconds": tool.timeout_seconds,
                "idempotent": tool.idempotent,
                "verificationStrategy": tool.verification_strategy,
                "available": tool.available(),
            }
            for tool in self._tools.values()
        ]

    def execute(
        self,
        name: str,
        payload: Mapping[str, Any],
        *,
        allow_side_effects: bool = False,
        granted_permissions: set[str] | frozenset[str] = frozenset(),
        approved_risk_levels: set[str] | frozenset[str] = frozenset(),
    ) -> Any:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"unknown tool: {name}")
        if not spec.available():
            raise RuntimeError(f"tool unavailable: {name}")
        if spec.side_effect and not allow_side_effects:
            raise PermissionError(f"side-effecting tool requires explicit permission: {name}")
        missing = set(spec.required_permissions) - set(granted_permissions)
        if missing:
            raise PermissionError(f"missing tool permissions: {', '.join(sorted(missing))}")
        if spec.risk_level in {"high", "critical"} and spec.risk_level not in approved_risk_levels:
            raise PermissionError(f"risk approval required for {spec.risk_level} tool: {name}")
        if spec.handler is None:
            raise RuntimeError(f"tool has no handler: {name}")
        return spec.handler(payload)

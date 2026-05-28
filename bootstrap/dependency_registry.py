"""Central dependency registry — all app.state wiring lives here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DependencyRegistry:
    """Central registry for all runtime components.

    No component should import from main.py — dependency flows
    only through this registry.
    """

    _components: dict[str, Any] = field(default_factory=dict)

    def register(self, name: str, component: Any) -> None:
        """Register a component by name."""
        self._components[name] = component

    def get(self, name: str) -> Any:
        """Get a component by name. Raises KeyError if not found."""
        if name not in self._components:
            raise KeyError(f"Component '{name}' not registered")
        return self._components[name]

    def get_optional(self, name: str) -> Any | None:
        """Get a component by name, or None if not registered."""
        return self._components.get(name)

    def has(self, name: str) -> bool:
        """Check if a component is registered."""
        return name in self._components

    def register_to_app_state(self, app) -> None:
        """Wire all registered components into FastAPI app.state."""
        for name, component in self._components.items():
            setattr(app.state, name, component)
        logger.info(
            "registry_wired_to_app",
            component_count=len(self._components),
        )

    @property
    def component_count(self) -> int:
        return len(self._components)

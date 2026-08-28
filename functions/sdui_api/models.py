from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_THEME = "light"
DEFAULT_DENSITY = "comfortable"


@dataclass(frozen=True)
class Component:
    id: str
    type: str
    props: Mapping[str, Any]
    required_entitlements: frozenset[str]
    children: tuple[Component, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Component:
        return cls(
            id=document["id"],
            type=document["type"],
            props=dict(document.get("props", {})),
            required_entitlements=frozenset(document.get("requiredEntitlements", [])),
            children=tuple(cls.from_document(child) for child in document.get("children", [])),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "props": dict(self.props),
            "children": [child.to_payload() for child in self.children],
        }


@dataclass(frozen=True)
class Variant:
    audience: str
    components: tuple[Component, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Variant:
        return cls(
            audience=document["audience"],
            components=tuple(Component.from_document(component) for component in document.get("components", [])),
        )


@dataclass(frozen=True)
class UiDefinition:
    surface: str
    version: str
    revision: str
    components: tuple[Component, ...]
    variants: tuple[Variant, ...]

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> UiDefinition:
        return cls(
            surface=document["surface"],
            version=document["version"],
            revision=document["revision"],
            components=tuple(Component.from_document(component) for component in document.get("components", [])),
            variants=tuple(Variant.from_document(variant) for variant in document.get("variants", [])),
        )


@dataclass(frozen=True)
class Preferences:
    theme: str = DEFAULT_THEME
    density: str = DEFAULT_DENSITY
    pinned_component_ids: tuple[str, ...] = ()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> Preferences:
        return cls(
            theme=document.get("theme", DEFAULT_THEME),
            density=document.get("density", DEFAULT_DENSITY),
            pinned_component_ids=tuple(document.get("pinnedComponentIds", [])),
        )


@dataclass(frozen=True)
class AccountProfile:
    user_id: str
    entitlements: frozenset[str] = frozenset()
    audiences: frozenset[str] = frozenset()
    preferences: Preferences = Preferences()

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> AccountProfile:
        return cls(
            user_id=document["userId"],
            entitlements=frozenset(document.get("entitlements", [])),
            audiences=frozenset(document.get("audiences", [])),
            preferences=Preferences.from_document(document.get("preferences", {})),
        )

    @classmethod
    def empty(cls, user_id: str) -> AccountProfile:
        return cls(user_id=user_id)


@dataclass(frozen=True)
class ResolvedUi:
    surface: str
    version: str
    revision: str
    theme: str
    density: str
    components: Sequence[Component]

    def to_payload(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "version": self.version,
            "revision": self.revision,
            "theme": self.theme,
            "density": self.density,
            "components": [component.to_payload() for component in self.components],
        }

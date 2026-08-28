import hashlib
import json
from collections.abc import Iterable, Sequence

from auth import Principal
from models import AccountProfile, Component, ResolvedUi, UiDefinition

ETAG_LENGTH = 16


def resolve(definition: UiDefinition, profile: AccountProfile, principal: Principal) -> ResolvedUi:
    audiences = profile.audiences | principal.app_roles

    components: tuple[Component, ...] = definition.components
    for variant in definition.variants:
        if variant.audience in audiences:
            components = _merge(components, variant.components)

    components = _filter_by_entitlements(components, profile.entitlements)
    components = _apply_pins(components, profile.preferences.pinned_component_ids)

    return ResolvedUi(
        surface=definition.surface,
        version=definition.version,
        revision=definition.revision,
        theme=profile.preferences.theme,
        density=profile.preferences.density,
        components=components,
    )


def etag_of(resolved: ResolvedUi) -> str:
    payload = json.dumps(resolved.to_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:ETAG_LENGTH]
    return '"' + digest + '"'


def _merge(base: Sequence[Component], overrides: Sequence[Component]) -> tuple[Component, ...]:
    override_by_id = {component.id: component for component in overrides}
    merged = [_merge_component(component, override_by_id.pop(component.id, None)) for component in base]
    merged.extend(override for override in overrides if override.id in override_by_id)
    return tuple(merged)


def _merge_component(base: Component, override: Component | None) -> Component:
    if override is None:
        return base
    return Component(
        id=base.id,
        type=override.type,
        props={**base.props, **override.props},
        required_entitlements=override.required_entitlements or base.required_entitlements,
        children=_merge(base.children, override.children),
    )


def _filter_by_entitlements(components: Iterable[Component], entitlements: frozenset[str]) -> tuple[Component, ...]:
    return tuple(
        Component(
            id=component.id,
            type=component.type,
            props=component.props,
            required_entitlements=component.required_entitlements,
            children=_filter_by_entitlements(component.children, entitlements),
        )
        for component in components
        if component.required_entitlements <= entitlements
    )


def _apply_pins(components: Sequence[Component], pinned_component_ids: Sequence[str]) -> tuple[Component, ...]:
    if not pinned_component_ids:
        return tuple(components)
    component_by_id = {component.id: component for component in components}
    pinned = [component_by_id.pop(pinned_id) for pinned_id in pinned_component_ids if pinned_id in component_by_id]
    return tuple(pinned) + tuple(component for component in components if component.id in component_by_id)

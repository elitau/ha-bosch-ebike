"""Give a shared bike's second account its own entities.

Bosch's "Share eBike" lets a main user invite other riders, each with their
own SingleKey ID. Rides belong to the account whose phone was connected, so
every account has its own ride history - but all of them report the same bike
ID. Every entity's unique_id is built from that bike ID, so the second config
entry's entities collided with the first entry's and Home Assistant dropped
them all.

No Home Assistant imports: entities and devices are duck-typed so the logic
stays testable with plain fakes (tests/test_shared_bike.py).
"""
from __future__ import annotations

from typing import Any, Iterable


def scope_shared_bike_entities(
    entities: list[Any],
    devices: Iterable[Any],
    *,
    entry_id: str,
    account_label: str,
    domain: str,
) -> list[Any]:
    """Re-scope entities of bikes already claimed by another config entry."""
    claimed = {
        ident
        for device in devices
        if entry_id not in device.config_entries
        for dom, ident in device.identifiers
        if dom == domain
    }
    for entity in entities:
        bike_ids = {
            ident
            for dom, ident in entity._attr_device_info["identifiers"]
            if dom == domain and ident in claimed
        }
        if not bike_ids:
            continue
        bike_id = bike_ids.pop()
        entity._attr_unique_id = f"{entry_id}_{entity._attr_unique_id}"
        device_info = entity._attr_device_info
        device_info["identifiers"] = {(domain, f"{bike_id}_{entry_id}")}
        if device_info.get("name"):
            device_info["name"] = f"{device_info['name']} ({account_label})"
    return entities


def scope_for_entry(hass: Any, entry: Any, entities: list[Any]) -> list[Any]:
    """Apply scope_shared_bike_entities() against the live device registry.

    Called by every platform right before async_add_entities(). The bike's
    device already belonging to another entry is what marks this entry as a
    second account on a shared bike; the main user's entry owns that device
    and is therefore never re-scoped.
    """
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN

    return scope_shared_bike_entities(
        entities,
        dr.async_get(hass).devices.values(),
        entry_id=entry.entry_id,
        account_label=entry.title or entry.entry_id[:8],
        domain=DOMAIN,
    )

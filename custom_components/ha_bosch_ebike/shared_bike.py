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

import logging
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)


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
        for ident in _own_identifiers(device.identifiers, domain)
    }
    for entity in entities:
        bike_ids = _own_identifiers(
            entity._attr_device_info["identifiers"], domain
        ) & claimed
        if not bike_ids:
            continue
        bike_id = bike_ids.pop()
        entity._attr_unique_id = f"{entry_id}_{entity._attr_unique_id}"
        device_info = entity._attr_device_info
        device_info["identifiers"] = {(domain, f"{bike_id}_{entry_id}")}
        if device_info.get("name"):
            device_info["name"] = f"{device_info['name']} ({account_label})"
    return entities


def _own_identifiers(identifiers: Iterable[tuple], domain: str) -> set[str]:
    """Return the ids of this domain's (domain, id) pairs.

    Other integrations may register identifiers that are not pairs, so never
    unpack blindly - one foreign three-part identifier would otherwise break
    every platform's setup.
    """
    return {t[1] for t in identifiers if len(t) == 2 and t[0] == domain}


def scope_for_entry(hass: Any, entry: Any, entities: list[Any]) -> list[Any]:
    """Apply scope_shared_bike_entities() against the live device registry.

    Called by every platform right before async_add_entities(). The bike's
    device already belonging to another entry is what marks this entry as a
    second account on a shared bike; the main user's entry owns that device
    and is therefore never re-scoped.
    """
    from homeassistant.helpers import device_registry as dr

    from .const import DOMAIN

    try:
        return scope_shared_bike_entities(
            entities,
            iter(dr.async_get(hass).devices),
            entry_id=entry.entry_id,
            account_label=entry.title or entry.entry_id[:8],
            domain=DOMAIN,
        )
    except Exception:  # noqa: BLE001 - never let this take down a platform
        # Worst case the second account's entities collide again, as they did
        # before this module existed; the main user's entities must load.
        _LOGGER.exception("Bosch eBike: shared-bike scoping failed, skipping it")
        return entities

"""Standalone tests for shared_bike.py — run with: python3 tests/test_shared_bike.py

One bike, shared via Bosch's "Share eBike" between a main user and an invited
rider with their own SingleKey ID: both config entries report the same bike
ID, so every entity of the second entry used to collide on its unique_id
("does not generate unique IDs ... already exists - ignoring") and the second
account's rides never showed up in Home Assistant.

shared_bike.py has no Home Assistant imports; entities and devices are passed
in as plain objects, so these tests use small fakes instead of HA.
"""
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components" / "ha_bosch_ebike" / "shared_bike.py"
)
_spec = importlib.util.spec_from_file_location("shared_bike", _MODULE_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
scope_shared_bike_entities = _mod.scope_shared_bike_entities

DOMAIN = "ha_bosch_ebike"
BIKE = "bike-1"


class FakeEntity:
    def __init__(self, unique_id, identifier, name="Cargo Line"):
        self._attr_unique_id = unique_id
        self._attr_device_info = {"identifiers": {(DOMAIN, identifier)}, "name": name}


class FakeDevice:
    def __init__(self, identifier, config_entries):
        self.identifiers = {(DOMAIN, identifier)}
        self.config_entries = set(config_entries)


def _scope(entities, devices, entry_id="entry-b", label="Anne"):
    return scope_shared_bike_entities(
        entities, devices, entry_id=entry_id, account_label=label, domain=DOMAIN
    )


def test_bike_without_existing_device_is_left_alone():
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE)
    _scope([entity], devices=[])
    assert entity._attr_unique_id == f"{BIKE}_last_ride_distance"
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, BIKE)}


def test_bike_claimed_by_another_entry_gets_entry_scoped_unique_id():
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE)
    _scope([entity], devices=[FakeDevice(BIKE, ["entry-a"])], entry_id="entry-b")
    assert entity._attr_unique_id == f"entry-b_{BIKE}_last_ride_distance"


def test_bike_claimed_by_another_entry_gets_its_own_device():
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE)
    _scope([entity], devices=[FakeDevice(BIKE, ["entry-a"])], entry_id="entry-b")
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, f"{BIKE}_entry-b")}


def test_own_device_name_carries_the_account_label():
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE, name="Cargo Line")
    _scope([entity], devices=[FakeDevice(BIKE, ["entry-a"])], label="Anne")
    assert entity._attr_device_info["name"] == "Cargo Line (Anne)"


def test_entry_that_owns_the_bike_device_keeps_its_unique_ids():
    # The main user's entry must never be re-scoped: that would orphan all of
    # its existing entities and their history.
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE)
    _scope([entity], devices=[FakeDevice(BIKE, ["entry-a"])], entry_id="entry-a")
    assert entity._attr_unique_id == f"{BIKE}_last_ride_distance"
    assert entity._attr_device_info["identifiers"] == {(DOMAIN, BIKE)}


def test_account_level_entity_of_the_second_entry_is_left_alone():
    # The unassigned-activities sensor hangs off a per-entry account device,
    # not off a bike, so it never collides and must not be touched.
    entity = FakeEntity("entry-b_unassigned_activities", "entry-b", name="Account")
    _scope([entity], devices=[FakeDevice(BIKE, ["entry-a"])], entry_id="entry-b")
    assert entity._attr_unique_id == "entry-b_unassigned_activities"
    assert entity._attr_device_info["name"] == "Account"


def test_foreign_device_with_three_part_identifier_does_not_break_setup():
    # Other integrations may register identifiers that are not (domain, id)
    # pairs. Unpacking every identifier as a pair raised "too many values to
    # unpack" and took down every platform of every entry on a real install.
    foreign = FakeDevice(BIKE, ["entry-a"])
    foreign.identifiers = {("some_other_domain", "hub", "node-7")}
    entity = FakeEntity(f"{BIKE}_last_ride_distance", BIKE)
    _scope([entity], devices=[foreign, FakeDevice(BIKE, ["entry-a"])])
    assert entity._attr_unique_id == f"entry-b_{BIKE}_last_ride_distance"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")

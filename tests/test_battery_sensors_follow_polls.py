"""Standalone tests for the per-battery cloud sensors — run with:
python3 tests/test_battery_sensors_follow_polls.py

Wh Lifetime and the three charge cycle sensors used to read the battery dict
that existed when the entity was created, so they only changed when the entry
was loaded again (a restart or a reload). Every poll hands the sensor the
current bike, and these sensors have to read their battery from it.

sensor.py imports Home Assistant, so _create_battery_sensors and the HA-free
helpers it uses are extracted from its source and exec'd with small stand-ins
for the description and entity classes, the same way test_trick_sensors.py
does it. The stand-ins keep the description, so the test calls the real
value_fn of every sensor.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
_SENSOR = _ROOT / "custom_components" / "ha_bosch_ebike" / "sensor.py"

_WANTED = {"_safe_get", "_battery_at", "_create_battery_sensors"}
_tree = ast.parse(_SENSOR.read_text(encoding="utf-8"))
_picked = [n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name in _WANTED]
assert {n.name for n in _picked} == _WANTED, (
    f"sensor.py no longer defines {_WANTED - {n.name for n in _picked}} at module "
    "level - update this test alongside the rename"
)


class _Description:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Sensor:
    def __init__(self, coordinator, description, bike_id, drive_name):
        self.entity_description = description


_ns: dict = {
    "Any": Any,
    "Callable": Callable,
    "BoschBikeSensorDescription": _Description,
    "BoschEBikeSensor": _Sensor,
    "BoschEBikeCoordinator": object,
    "UnitOfEnergy": SimpleNamespace(WATT_HOUR="Wh"),
    "SensorDeviceClass": SimpleNamespace(ENERGY="energy"),
    "SensorStateClass": SimpleNamespace(TOTAL_INCREASING="total_increasing"),
}
exec(  # noqa: S102 - executing our own source, see the module docstring
    compile(ast.Module(body=_picked, type_ignores=[]), str(_SENSOR), "exec"),
    _ns,
)
_create_battery_sensors = _ns["_create_battery_sensors"]


def _bike(*batteries):
    return {"id": "bike-1", "batteries": list(batteries)}


def _battery(wh, total, on_bike, off_bike):
    return {
        "productName": "PowerPack 800 Frame",
        "deliveredWhOverLifetime": wh,
        "chargeCycles": {"total": total, "onBike": on_bike, "offBike": off_bike},
    }


def _values(sensors, bike):
    return {s.entity_description.key: s.entity_description.value_fn(bike) for s in sensors}


def test_values_follow_the_current_poll_not_the_setup_data():
    # Real numbers from a shared Cargo Line: a ride and a charge between two polls.
    at_setup = _bike(_battery(4512, 6.6, 0.0, 6.6))
    later = _bike(_battery(4671, 6.7, 0.0, 6.7))
    sensors = _create_battery_sensors(None, "bike-1", "Cargo Line", 0, "battery_1", "PowerPack 800 Frame")

    assert _values(sensors, at_setup) == {
        "battery_1_wh_lifetime": 4512,
        "battery_1_charge_cycles_total": 6.6,
        "battery_1_charge_cycles_on_bike": 0.0,
        "battery_1_charge_cycles_off_bike": 6.6,
    }
    assert _values(sensors, later) == {
        "battery_1_wh_lifetime": 4671,
        "battery_1_charge_cycles_total": 6.7,
        "battery_1_charge_cycles_on_bike": 0.0,
        "battery_1_charge_cycles_off_bike": 6.7,
    }


def test_second_battery_reads_its_own_entry():
    bike = _bike(_battery(1000, 2.0, 1.0, 1.0), _battery(300, 0.5, 0.5, 0.0))
    first = _create_battery_sensors(None, "bike-1", "Cargo Line", 0, "battery_1", "Battery 1")
    second = _create_battery_sensors(None, "bike-1", "Cargo Line", 1, "battery_2", "Battery 2")

    assert _values(first, bike)["battery_1_wh_lifetime"] == 1000
    assert _values(second, bike)["battery_2_wh_lifetime"] == 300
    assert _values(second, bike)["battery_2_charge_cycles_total"] == 0.5


def test_missing_battery_reads_as_unknown():
    # A poll without the battery (removed, or a partial cloud answer) shows
    # unknown instead of raising or keeping an old value.
    sensors = _create_battery_sensors(None, "bike-1", "Cargo Line", 1, "battery_2", "Battery 2")
    for bike in (_bike(_battery(1000, 2.0, 1.0, 1.0)), {"id": "bike-1"}, {"id": "bike-1", "batteries": None}):
        assert set(_values(sensors, bike).values()) == {None}


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

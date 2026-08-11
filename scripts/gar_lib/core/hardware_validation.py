"""Strict, offline validation of a product hardware contract.

The CSV files used by ``gar hw init`` describe an implementation.  This module
checks the earlier, declarative boundary: a product requirement, a target's
capabilities, and the product-to-target binding.  It deliberately has no
connection or deployment dependency, so it is safe to run in CI before a
physical target is touched.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
KINDS = frozenset({"gpio", "spi", "video", "network"})
COMMON_REQUIREMENT_FIELDS = frozenset({"id", "kind", "component", "required_drivers"})
COMMON_RESOURCE_FIELDS = frozenset({"id", "kind", "device", "drivers", "pinmux"})
PLATFORM_FIELDS = frozenset({"architecture", "abi", "toolchain_triple", "init_system", "privilege_model"})
REQUIREMENT_FIELDS = {
    "gpio": COMMON_REQUIREMENT_FIELDS | {"direction", "voltage_v"},
    "spi": COMMON_REQUIREMENT_FIELDS | {"min_speed_hz", "mode", "device", "voltage_v"},
    "video": COMMON_REQUIREMENT_FIELDS | {"min_fps", "device"},
    "network": COMMON_REQUIREMENT_FIELDS,
}
RESOURCE_FIELDS = {
    "gpio": COMMON_RESOURCE_FIELDS | {"lines", "line_pins", "directions", "voltage_v"},
    "spi": COMMON_RESOURCE_FIELDS | {"bus", "chip_select", "max_speed_hz", "modes", "signal_pins", "voltage_v"},
    "video": COMMON_RESOURCE_FIELDS | {"max_fps", "signal_pins"},
    "network": COMMON_RESOURCE_FIELDS | {"signal_pins"},
}


@dataclass(frozen=True)
class HardwareValidationReport:
    """The stable machine-readable outcome of hardware validation."""

    product: str | None
    target_id: str | None
    platform: dict[str, str] | None
    requirements_path: Path
    capabilities_path: Path
    binding_path: Path
    assignments: list[dict[str, object]]
    errors: list[dict[str, object]]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "command": "hw.validate",
            "ok": self.ok,
            "exit_code": self.exit_code,
            "product": self.product,
            "target_id": self.target_id,
            "platform": self.platform,
            "paths": {
                "requirements": str(self.requirements_path),
                "capabilities": str(self.capabilities_path),
                "binding": str(self.binding_path),
            },
            "assignments": self.assignments,
            "errors": self.errors,
        }


def validate_hardware_contract(
    *,
    requirements_path: Path,
    capabilities_path: Path,
    binding_path: Path,
    selected_target_id: str | None = None,
) -> HardwareValidationReport:
    """Validate schema v1 inputs and cross-file hardware compatibility."""

    errors: list[dict[str, object]] = []
    requirements = _load_json_object(requirements_path, "requirements", errors)
    capabilities = _load_json_object(capabilities_path, "capabilities", errors)
    binding = _load_json_object(binding_path, "binding", errors)
    product = _optional_string(requirements.get("product")) if requirements else None
    target_id = _optional_string(capabilities.get("target_id")) if capabilities else selected_target_id
    platform = _optional_platform(capabilities.get("platform")) if capabilities else None

    _validate_requirements_document(requirements, errors)
    _validate_capabilities_document(capabilities, errors)
    _validate_binding_document(binding, errors)
    if errors:
        return HardwareValidationReport(
            product, target_id, platform, requirements_path, capabilities_path, binding_path, [], errors
        )

    assert requirements is not None and capabilities is not None and binding is not None
    product = str(requirements["product"])
    target_id = str(capabilities["target_id"])
    _validate_identity(product, target_id, binding, selected_target_id, errors)

    requirement_by_id = {str(item["id"]): item for item in requirements["requirements"]}
    resource_by_id = {str(item["id"]): item for item in capabilities["resources"]}
    assignments: list[dict[str, object]] = []
    used_gpio_lines: dict[tuple[str, int], str] = {}
    used_spi_addresses: dict[tuple[int, int], str] = {}
    used_physical_pins: dict[str, str] = {}
    seen_requirement_mappings: set[str] = set()

    for mapping in binding["mappings"]:
        requirement_id = str(mapping["requirement"])
        resource_id = str(mapping["resource"])
        requirement = requirement_by_id.get(requirement_id)
        resource = resource_by_id.get(resource_id)
        context: dict[str, object] = {"requirement": requirement_id, "resource": resource_id}
        for field in ("line", "physical_pin", "physical_pins", "pinmux"):
            if field in mapping:
                context[field] = mapping[field]
        if requirement_id in seen_requirement_mappings:
            _error(errors, "duplicate_requirement_mapping", "requirement is mapped more than once", **context)
            continue
        seen_requirement_mappings.add(requirement_id)
        if requirement is None:
            _error(errors, "missing_requirement", "mapping references an unknown requirement", **context)
            continue
        if resource is None:
            _error(errors, "missing_resource", "mapping references an unknown resource", **context)
            continue

        context["component"] = requirement["component"]
        context["device"] = resource["device"]
        context["pinmux_settings"] = resource["pinmux"]["settings"]
        if requirement["kind"] == "spi":
            context.update(
                {
                    "bus": resource["bus"],
                    "chip_select": resource["chip_select"],
                    "max_speed_hz": resource["max_speed_hz"],
                    "mode": requirement["mode"],
                }
            )

        valid = _validate_mapping(
            requirement,
            resource,
            mapping,
            errors,
            context,
            used_gpio_lines,
            used_spi_addresses,
            used_physical_pins,
        )
        if valid:
            assignments.append(context)

    for requirement_id in requirement_by_id:
        if requirement_id not in seen_requirement_mappings:
            _error(errors, "missing_mapping", "requirement has no target resource mapping", requirement=requirement_id)

    return HardwareValidationReport(
        product, target_id, platform, requirements_path, capabilities_path, binding_path, assignments, errors
    )


def _load_json_object(path: Path, label: str, errors: list[dict[str, object]]) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        _error(errors, "input_unavailable", f"cannot read {label}: {error}", input=label, path=str(path))
        return None
    except json.JSONDecodeError as error:
        _error(errors, "invalid_json", f"invalid JSON in {label}: {error.msg}", input=label, path=str(path))
        return None
    if not isinstance(raw, dict):
        _error(errors, "invalid_schema", f"{label} root must be an object", input=label, path=str(path))
        return None
    return raw


def _validate_requirements_document(document: dict[str, Any] | None, errors: list[dict[str, object]]) -> None:
    if document is None:
        return
    _exact_keys(document, {"schema_version", "product", "requirements"}, "requirements", errors)
    if document.get("schema_version") != SCHEMA_VERSION:
        _error(errors, "unsupported_schema", "requirements schema_version must be 1", input="requirements")
    if not _nonempty_string(document.get("product")):
        _error(errors, "invalid_schema", "requirements product must be a non-empty string", input="requirements")
    entries = document.get("requirements")
    if not isinstance(entries, list):
        _error(errors, "invalid_schema", "requirements requirements must be an array", input="requirements")
        return
    _validate_entries(entries, "requirement", REQUIREMENT_FIELDS, errors)


def _validate_capabilities_document(document: dict[str, Any] | None, errors: list[dict[str, object]]) -> None:
    if document is None:
        return
    _exact_keys(document, {"schema_version", "target_id", "platform", "resources"}, "capabilities", errors)
    if document.get("schema_version") != SCHEMA_VERSION:
        _error(errors, "unsupported_schema", "capabilities schema_version must be 1", input="capabilities")
    if not _nonempty_string(document.get("target_id")):
        _error(errors, "invalid_schema", "capabilities target_id must be a non-empty string", input="capabilities")
    platform = document.get("platform")
    if not isinstance(platform, dict):
        _error(errors, "invalid_schema", "capabilities platform must be an object", input="capabilities")
    else:
        _exact_keys(platform, PLATFORM_FIELDS, "platform", errors)
        for field in ("architecture", "abi", "toolchain_triple"):
            if not _nonempty_string(platform.get(field)):
                _error(errors, "invalid_schema", f"platform {field} must be a non-empty string", input="capabilities")
        if platform.get("init_system") not in {"systemd", "busybox"}:
            _error(
                errors,
                "invalid_schema",
                "platform init_system must be systemd or busybox",
                input="capabilities",
            )
        if platform.get("privilege_model") not in {"root", "sudo-noninteractive"}:
            _error(
                errors,
                "invalid_schema",
                "platform privilege_model must be root or sudo-noninteractive",
                input="capabilities",
            )
    entries = document.get("resources")
    if not isinstance(entries, list):
        _error(errors, "invalid_schema", "capabilities resources must be an array", input="capabilities")
        return
    _validate_entries(entries, "resource", RESOURCE_FIELDS, errors)


def _validate_binding_document(document: dict[str, Any] | None, errors: list[dict[str, object]]) -> None:
    if document is None:
        return
    _exact_keys(document, {"schema_version", "product", "target_id", "mappings"}, "binding", errors)
    if document.get("schema_version") != SCHEMA_VERSION:
        _error(errors, "unsupported_schema", "binding schema_version must be 1", input="binding")
    for field in ("product", "target_id"):
        if not _nonempty_string(document.get(field)):
            _error(errors, "invalid_schema", f"binding {field} must be a non-empty string", input="binding")
    mappings = document.get("mappings")
    if not isinstance(mappings, list):
        _error(errors, "invalid_schema", "binding mappings must be an array", input="binding")
        return
    for index, mapping in enumerate(mappings):
        if not isinstance(mapping, dict):
            _error(errors, "invalid_schema", "mapping must be an object", input="binding", index=index)
            continue
        keys = set(mapping)
        allowed = {"requirement", "resource", "line", "physical_pin", "physical_pins", "pinmux"}
        if not {"requirement", "resource"} <= keys or not keys <= allowed:
            _error(errors, "invalid_schema", "mapping has unsupported or missing fields", input="binding", index=index)
            continue
        if not _nonempty_string(mapping.get("requirement")) or not _nonempty_string(mapping.get("resource")):
            _error(
                errors,
                "invalid_schema",
                "mapping requirement and resource must be non-empty strings",
                input="binding",
                index=index,
            )
        if "line" in mapping and not _nonnegative_integer(mapping["line"]):
            _error(
                errors, "invalid_schema", "mapping line must be a non-negative integer", input="binding", index=index
            )
        if "physical_pin" in mapping and not _nonempty_string(mapping["physical_pin"]):
            _error(
                errors,
                "invalid_schema",
                "mapping physical_pin must be a non-empty string",
                input="binding",
                index=index,
            )
        if "physical_pins" in mapping and (
            not isinstance(mapping["physical_pins"], list)
            or not mapping["physical_pins"]
            or not all(_nonempty_string(item) for item in mapping["physical_pins"])
            or len(mapping["physical_pins"]) != len(set(mapping["physical_pins"]))
        ):
            _error(
                errors,
                "invalid_schema",
                "mapping physical_pins must be an array of non-empty strings",
                input="binding",
                index=index,
            )
        if ("physical_pin" in mapping) == ("physical_pins" in mapping):
            _error(
                errors,
                "invalid_schema",
                "mapping must define exactly one of physical_pin or physical_pins",
                input="binding",
                index=index,
            )
        if not _nonempty_string(mapping.get("pinmux")):
            _error(errors, "invalid_schema", "mapping pinmux must be a non-empty string", input="binding", index=index)


def _validate_entries(
    entries: list[Any],
    label: str,
    fields_by_kind: Mapping[str, frozenset[str]],
    errors: list[dict[str, object]],
) -> None:
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            _error(errors, "invalid_schema", f"{label} must be an object", input=label, index=index)
            continue
        kind = entry.get("kind")
        item_id = entry.get("id")
        if kind not in KINDS:
            _error(errors, "invalid_schema", f"{label} kind must be one of {sorted(KINDS)}", input=label, index=index)
            continue
        expected = fields_by_kind[str(kind)]
        if str(kind) == "video":
            _allowed_keys(entry, {expected, expected | {"voltage_v"}}, label, errors, index=index)
        else:
            _exact_keys(entry, expected, label, errors, index=index)
        if not _nonempty_string(item_id):
            _error(errors, "invalid_schema", f"{label} id must be a non-empty string", input=label, index=index)
        elif str(item_id) in seen_ids:
            _error(errors, "duplicate_id", f"duplicate {label} id", input=label, id=item_id)
        else:
            seen_ids.add(str(item_id))
        _validate_common_entry(entry, label, errors, index)
        _validate_kind_entry(entry, label, errors, index)


def _validate_common_entry(entry: dict[str, Any], label: str, errors: list[dict[str, object]], index: int) -> None:
    drivers = entry.get("required_drivers" if label == "requirement" else "drivers")
    if (
        not isinstance(drivers, list)
        or not drivers
        or not all(_nonempty_string(item) for item in drivers)
        or len(drivers) != len(set(drivers))
    ):
        field = "required_drivers" if label == "requirement" else "drivers"
        _error(
            errors, "invalid_schema", f"{label} {field} must be an array of non-empty strings", input=label, index=index
        )
    if label == "requirement" and not _nonempty_string(entry.get("component")):
        _error(errors, "invalid_schema", "requirement component must be a non-empty string", input=label, index=index)
    if label == "resource":
        if not _nonempty_string(entry.get("device")):
            _error(errors, "invalid_schema", "resource device must be a non-empty string", input=label, index=index)
        _validate_pinmux(entry.get("pinmux"), errors, index)
    if "voltage_v" in entry and (not _number(entry["voltage_v"]) or float(entry["voltage_v"]) <= 0):
        _error(errors, "invalid_schema", f"{label} voltage_v must be a positive number", input=label, index=index)


def _validate_kind_entry(entry: dict[str, Any], label: str, errors: list[dict[str, object]], index: int) -> None:
    kind = entry["kind"]
    if kind == "gpio":
        direction = entry.get("direction") if label == "requirement" else entry.get("directions")
        if label == "requirement":
            if direction not in {"input", "output"}:
                _error(
                    errors,
                    "invalid_schema",
                    "gpio requirement direction must be input or output",
                    input=label,
                    index=index,
                )
        else:
            if (
                not isinstance(direction, list)
                or not direction
                or not all(item in {"input", "output"} for item in direction)
                or len(direction) != len(set(direction))
            ):
                _error(
                    errors,
                    "invalid_schema",
                    "gpio resource directions must list input/output",
                    input=label,
                    index=index,
                )
            lines = entry.get("lines")
            if (
                not isinstance(lines, list)
                or not lines
                or not all(_nonnegative_integer(item) for item in lines)
                or len(lines) != len(set(lines))
            ):
                _error(
                    errors,
                    "invalid_schema",
                    "gpio resource lines must be a unique non-empty array of non-negative integers",
                    input=label,
                    index=index,
                )
            _validate_line_pins(entry.get("line_pins"), lines, errors, index)
    elif kind == "spi":
        if label == "requirement":
            if not _positive_integer(entry.get("min_speed_hz")):
                _error(
                    errors,
                    "invalid_schema",
                    "spi requirement min_speed_hz must be positive integer",
                    input=label,
                    index=index,
                )
            if not _integer(entry.get("mode")) or entry["mode"] not in {0, 1, 2, 3}:
                _error(errors, "invalid_schema", "spi requirement mode must be 0..3", input=label, index=index)
            if not _nonempty_string(entry.get("device")):
                _error(errors, "invalid_schema", "spi requirement device must be non-empty", input=label, index=index)
        elif not (
            _nonnegative_integer(entry.get("bus"))
            and _nonnegative_integer(entry.get("chip_select"))
            and _positive_integer(entry.get("max_speed_hz"))
            and isinstance(entry.get("modes"), list)
            and bool(entry["modes"])
            and all(_integer(mode) and mode in {0, 1, 2, 3} for mode in entry["modes"])
            and len(entry["modes"]) == len(set(entry["modes"]))
        ):
            _error(
                errors,
                "invalid_schema",
                "spi resource bus/chip_select/max_speed_hz/modes are invalid",
                input=label,
                index=index,
            )
        if label == "resource":
            _validate_signal_pins(entry.get("signal_pins"), errors, index)
    elif kind == "video":
        if label == "requirement":
            if not _positive_integer(entry.get("min_fps")) or not _nonempty_string(entry.get("device")):
                _error(
                    errors,
                    "invalid_schema",
                    "video requirement min_fps/device are invalid",
                    input=label,
                    index=index,
                )
        elif not _positive_integer(entry.get("max_fps")):
            _error(
                errors, "invalid_schema", "video resource max_fps must be positive integer", input=label, index=index
            )
        if label == "resource":
            _validate_signal_pins(entry.get("signal_pins"), errors, index)
    elif kind == "network" and label == "resource":
        _validate_signal_pins(entry.get("signal_pins"), errors, index)


def _validate_identity(
    product: str,
    target_id: str,
    binding: dict[str, Any],
    selected_target_id: str | None,
    errors: list[dict[str, object]],
) -> None:
    if binding["product"] != product:
        _error(
            errors,
            "product_drift",
            "binding product does not match requirements product",
            expected=product,
            actual=binding["product"],
        )
    if binding["target_id"] != target_id:
        _error(
            errors,
            "target_drift",
            "binding target_id does not match capabilities target_id",
            expected=target_id,
            actual=binding["target_id"],
        )
    if selected_target_id and target_id != selected_target_id:
        _error(
            errors,
            "target_drift",
            "capabilities target_id does not match selected workspace target",
            expected=selected_target_id,
            actual=target_id,
        )


def _validate_mapping(
    requirement: dict[str, Any],
    resource: dict[str, Any],
    mapping: dict[str, Any],
    errors: list[dict[str, object]],
    context: dict[str, object],
    used_gpio_lines: dict[tuple[str, int], str],
    used_spi_addresses: dict[tuple[int, int], str],
    used_physical_pins: dict[str, str],
) -> bool:
    valid = True
    if requirement["kind"] != resource["kind"]:
        _error(errors, "kind_mismatch", "requirement kind does not match resource kind", **context)
        return False
    if "voltage_v" in requirement:
        if "voltage_v" not in resource:
            _error(errors, "voltage_missing", "resource has no voltage for a voltage-bound requirement", **context)
            valid = False
        elif float(requirement["voltage_v"]) != float(resource["voltage_v"]):
            _error(errors, "voltage_mismatch", "requirement voltage does not match resource voltage", **context)
            valid = False
    missing_drivers = sorted(set(requirement["required_drivers"]) - set(resource["drivers"]))
    if missing_drivers:
        _error(errors, "driver_missing", "resource lacks required driver", missing=missing_drivers, **context)
        valid = False
    kind = requirement["kind"]
    if kind in {"spi", "video"} and requirement["device"] != resource["device"]:
        _error(errors, "device_mismatch", "requirement device does not match resource device", **context)
        valid = False
    valid = (
        _validate_physical_mapping(
            requirement,
            resource,
            mapping,
            errors,
            context,
            used_physical_pins,
        )
        and valid
    )
    if kind == "gpio":
        valid = _validate_gpio_mapping(requirement, resource, mapping, errors, context, used_gpio_lines) and valid
    elif kind == "spi":
        valid = _validate_spi_mapping(requirement, resource, errors, context, used_spi_addresses) and valid
    elif kind == "video" and int(resource["max_fps"]) < int(requirement["min_fps"]):
        _error(errors, "video_fps_too_low", "resource maximum FPS is below requirement", **context)
        valid = False
    return valid


def _validate_physical_mapping(
    requirement: dict[str, Any],
    resource: dict[str, Any],
    mapping: dict[str, Any],
    errors: list[dict[str, object]],
    context: dict[str, object],
    used: dict[str, str],
) -> bool:
    valid = True
    if mapping["pinmux"] != resource["pinmux"]["id"]:
        _error(errors, "pinmux_mismatch", "binding pinmux is not provided by the resource", **context)
        valid = False

    pins: list[str] = []
    kind = requirement["kind"]
    if kind == "gpio":
        line = mapping.get("line")
        expected = resource["line_pins"].get(str(line))
        actual = mapping.get("physical_pin")
        if not isinstance(actual, str) or actual != expected:
            _error(
                errors,
                "physical_pin_mismatch",
                "GPIO physical pin does not match the target line",
                expected=expected,
                **context,
            )
            valid = False
        elif actual:
            pins.append(actual)
    elif kind == "spi":
        actual_signals = _parse_signal_pins(mapping.get("physical_pins"))
        expected_signals = resource["signal_pins"]
        if actual_signals != expected_signals:
            _error(
                errors,
                "physical_pin_mismatch",
                "SPI signal-to-pin assignment does not match the target resource",
                expected=[f"{pin}:{signal}" for signal, pin in expected_signals.items()],
                **context,
            )
            valid = False
        else:
            pins.extend(actual_signals.values())
    else:
        actual = mapping.get("physical_pin")
        if not isinstance(actual, str) or actual not in resource["signal_pins"].values():
            _error(
                errors,
                "physical_pin_mismatch",
                "physical connector is not provided by the target resource",
                expected=sorted(resource["signal_pins"].values()),
                **context,
            )
            valid = False
        elif actual:
            pins.append(actual)

    for pin in pins:
        other = used.get(pin)
        if other is not None:
            _error(
                errors,
                "physical_pin_conflict",
                "physical pin is already assigned",
                conflicting_physical_pin=pin,
                conflicting_requirement=other,
                **context,
            )
            valid = False
        else:
            used[pin] = str(requirement["id"])
    return valid


def _parse_signal_pins(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        return {}
    parsed: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            return {}
        pin, separator, signal = item.rpartition(":")
        if not separator or not pin.strip() or not signal.strip() or signal in parsed:
            return {}
        parsed[signal] = pin
    return parsed


def _validate_pinmux(value: object, errors: list[dict[str, object]], index: int) -> None:
    if not isinstance(value, dict):
        _error(errors, "invalid_schema", "resource pinmux must be an object", input="resource", index=index)
        return
    _exact_keys(value, {"id", "settings"}, "pinmux", errors, index=index)
    settings = value.get("settings")
    if (
        not _nonempty_string(value.get("id"))
        or not isinstance(settings, list)
        or not all(_nonempty_string(item) for item in settings)
    ):
        _error(
            errors,
            "invalid_schema",
            "resource pinmux requires a non-empty id and an array of non-empty settings",
            input="resource",
            index=index,
        )
    elif len(settings) != len(set(settings)):
        _error(errors, "invalid_schema", "resource pinmux settings must be unique", input="resource", index=index)


def _validate_line_pins(
    value: object,
    lines: object,
    errors: list[dict[str, object]],
    index: int,
) -> None:
    if (
        not isinstance(value, dict)
        or not isinstance(lines, list)
        or set(value) != {str(line) for line in lines}
        or not all(_nonempty_string(pin) for pin in value.values())
        or len(value.values()) != len(set(value.values()))
    ):
        _error(
            errors,
            "invalid_schema",
            "gpio resource line_pins must map every line to one unique physical pin",
            input="resource",
            index=index,
        )


def _validate_signal_pins(value: object, errors: list[dict[str, object]], index: int) -> None:
    if (
        not isinstance(value, dict)
        or not value
        or not all(_nonempty_string(signal) and _nonempty_string(pin) for signal, pin in value.items())
        or len(value.values()) != len(set(value.values()))
    ):
        _error(
            errors,
            "invalid_schema",
            "resource signal_pins must map signals to unique physical pins",
            input="resource",
            index=index,
        )


def _validate_gpio_mapping(
    requirement: dict[str, Any],
    resource: dict[str, Any],
    mapping: dict[str, Any],
    errors: list[dict[str, object]],
    context: dict[str, object],
    used: dict[tuple[str, int], str],
) -> bool:
    line = mapping.get("line")
    if not _integer(line):
        _error(errors, "missing_line", "gpio mapping requires an integer line", **context)
        return False
    if line not in resource["lines"]:
        _error(errors, "invalid_line", "gpio mapping line is not provided by resource", **context)
        return False
    if requirement["direction"] not in resource["directions"]:
        _error(errors, "direction_mismatch", "gpio resource does not support required direction", **context)
        return False
    key = (str(resource["device"]), int(line))
    other = used.get(key)
    if other is not None:
        _error(errors, "gpio_pin_conflict", "gpio line is already assigned", conflicting_requirement=other, **context)
        return False
    used[key] = str(requirement["id"])
    return True


def _validate_spi_mapping(
    requirement: dict[str, Any],
    resource: dict[str, Any],
    errors: list[dict[str, object]],
    context: dict[str, object],
    used: dict[tuple[int, int], str],
) -> bool:
    valid = True
    if int(requirement["mode"]) not in resource["modes"]:
        _error(errors, "spi_mode_unsupported", "resource does not support the required SPI mode", **context)
        valid = False
    if int(resource["max_speed_hz"]) < int(requirement["min_speed_hz"]):
        _error(errors, "spi_speed_too_low", "resource maximum SPI speed is below requirement", **context)
        valid = False
    key = (int(resource["bus"]), int(resource["chip_select"]))
    other = used.get(key)
    if other is not None:
        _error(
            errors,
            "spi_bus_cs_conflict",
            "SPI bus/chip-select is already assigned",
            conflicting_requirement=other,
            **context,
        )
        valid = False
    else:
        used[key] = str(requirement["id"])
    return valid


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str] | frozenset[str],
    label: str,
    errors: list[dict[str, object]],
    **context: object,
) -> None:
    if set(value) != set(expected):
        _error(errors, "invalid_schema", f"{label} fields must be exactly {sorted(expected)}", input=label, **context)


def _allowed_keys(
    value: Mapping[str, Any],
    expected_sets: set[frozenset[str]],
    label: str,
    errors: list[dict[str, object]],
    **context: object,
) -> None:
    if frozenset(value) not in expected_sets:
        expected = " or ".join(str(sorted(item)) for item in sorted(expected_sets, key=len))
        _error(errors, "invalid_schema", f"{label} fields must be exactly {expected}", input=label, **context)


def _error(errors: list[dict[str, object]], code: str, message: str, **context: object) -> None:
    errors.append({"code": code, "message": message, **context})


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional_string(value: object) -> str | None:
    return value if _nonempty_string(value) else None


def _optional_platform(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict) or not all(_nonempty_string(item) for item in value.values()):
        return None
    return {str(key): str(item) for key, item in value.items()}


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonnegative_integer(value: object) -> bool:
    return _integer(value) and int(value) >= 0


def _positive_integer(value: object) -> bool:
    return _integer(value) and int(value) > 0


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)

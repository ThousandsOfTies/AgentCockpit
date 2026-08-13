"""Product-neutral multi-bridge scenario DSL for ``gar system test``.

The system topology owns node identities and lifecycle.  A scenario is a
separate, product-owned document that sends opaque commands to bridge APIs,
observes JSON state into named metrics, and asserts only on those metrics.
GAR therefore never learns the product protocol behind an action name.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.simulation.hardware import io_actions
from scripts.gar_lib.system.model import SystemTopology

_IDENTIFIER_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
_OPERATORS = frozenset({"eq", "ne", "gt", "gte", "lt", "lte", "exists"})
_MAX_BRIDGE_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class SystemScenario:
    name: str
    steps: tuple[dict[str, object], ...]
    cleanup: tuple[dict[str, object], ...] = ()


class BridgeScenarioAdapter(Protocol):
    """Transport boundary. Tests inject a fake; production uses HTTP JSON."""

    def command(self, node: str, via: str, action: str, params: Mapping[str, object]) -> object: ...

    def metrics(self, node: str, application: str) -> object: ...


class HttpBridgeScenarioAdapter:
    """Bridge adapter using the same action vocabulary as ``gar sim io``."""

    def __init__(self, bridges: Mapping[str, str], *, timeout_seconds: float = 10):
        self.bridges = dict(bridges)
        self.timeout_seconds = timeout_seconds

    def command(self, node: str, via: str, action: str, params: Mapping[str, object]) -> object:
        if via != "bridge":
            raise GarDomainError(f"HTTP bridge adapterは {via} commandを実行できません")
        device = _optional_string(params.get("device"))
        try:
            request = io_actions.resolve(action, device, params)
        except (KeyError, TypeError, ValueError) as error:
            raise GarDomainError(f"scenario bridge commandが不正です: {error}") from error
        payload = dict(request.fields) if request.method != "GET" else None
        return self._request(node, request.method, request.path, payload)

    def metrics(self, node: str, application: str) -> object:
        return self._request(node, "GET", f"/api/metrics/{urllib.parse.quote(application, safe='')}", None)

    def _request(self, node: str, method: str, path: str, payload: dict[str, object] | None) -> object:
        bridge_url = self.bridges.get(node)
        if bridge_url is None:
            raise GarDomainError(f"scenario bridgeが未定義です: {node}")
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        request = urllib.request.Request(f"{bridge_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = response.read(_MAX_BRIDGE_RESPONSE_BYTES + 1)
        except urllib.error.URLError as error:
            raise GarDomainError(f"scenario bridgeへ接続できません: {node}: {error.reason}") from error
        except TimeoutError as error:
            raise GarDomainError(f"scenario bridgeがtimeoutしました: {node}") from error
        try:
            if len(raw) > _MAX_BRIDGE_RESPONSE_BYTES:
                raise GarDomainError(f"scenario bridge responseが上限を超えています: {node}")
            decoded = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant) if raw else {}
            if not isinstance(decoded, dict):
                raise GarDomainError(f"scenario bridgeはJSON objectを返す必要があります: {node}")
            return decoded
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise GarDomainError(f"scenario bridgeがJSONを返しません: {node}") from error


@dataclass(frozen=True)
class ScenarioReport:
    name: str
    steps: list[dict[str, object]]
    metrics: dict[str, object]
    assertions: list[dict[str, object]]
    cleanup: list[dict[str, object]]
    failures: list[dict[str, object]]

    @property
    def ok(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "name": self.name,
            "ok": self.ok,
            "steps": self.steps,
            "metrics": self.metrics,
            "assertions": self.assertions,
            "cleanup": self.cleanup,
            "failures": self.failures,
        }


def load_scenario(path: str | Path, topology: SystemTopology) -> SystemScenario:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as error:
        raise GarDomainError(f"scenario fileを読み込めません: {source}: {error}") from error
    except (json.JSONDecodeError, ValueError) as error:
        raise GarDomainError(f"scenario fileはJSONである必要があります: {source}: {error}") from error
    return scenario_from_value(raw, topology)


def scenario_from_value(raw: object, topology: SystemTopology) -> SystemScenario:
    root = _object(raw, "scenario")
    _fields(root, {"schema_version", "name", "steps", "cleanup"}, {"schema_version", "name", "steps"}, "scenario")
    if root.get("schema_version") != 1:
        raise GarDomainError("scenario.schema_version は 1 である必要があります")
    name = _nonempty(root.get("name"), "scenario.name")
    raw_steps = root.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise GarDomainError("scenario.steps は空でないarrayである必要があります")
    steps: list[dict[str, object]] = []
    metrics: set[str] = set()
    for index, raw_step in enumerate(raw_steps):
        step = _step(raw_step, index, topology, metrics)
        steps.append(step)
        if step["type"] == "observe":
            metrics.add(str(step["metric"]))
    raw_cleanup = root.get("cleanup", [])
    if not isinstance(raw_cleanup, list):
        raise GarDomainError("scenario.cleanup はarrayである必要があります")
    cleanup: list[dict[str, object]] = []
    for index, raw_step in enumerate(raw_cleanup):
        step = _step(raw_step, index, topology, set())
        if step["type"] != "command":
            raise GarDomainError(f"scenario.cleanup[{index}] はcommand stepだけ指定できます")
        cleanup.append(step)
    return SystemScenario(name=name, steps=tuple(steps), cleanup=tuple(cleanup))


def run_scenario(
    scenario: SystemScenario,
    *,
    adapter: BridgeScenarioAdapter,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> ScenarioReport:
    """Execute a validated scenario without any product-specific interpretation."""

    transport = adapter
    metrics: dict[str, object] = {}
    observations: dict[str, tuple[str, str, str]] = {}
    steps: list[dict[str, object]] = []
    assertions: list[dict[str, object]] = []
    cleanup: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    stopped_nodes: set[str] = set()
    for index, step in enumerate(scenario.steps, start=1):
        detail: dict[str, object] = {"index": index, "type": step["type"], "ok": True}
        try:
            kind = step["type"]
            if kind == "command":
                response = transport.command(
                    str(step["node"]), str(step["via"]), str(step["action"]), _mapping(step["params"])
                )
                detail["node"] = step["node"]
                detail["via"] = step["via"]
                detail["action"] = step["action"]
                detail["response"] = response
                if step["via"] == "runtime":
                    if step["action"] == "stop":
                        stopped_nodes.add(str(step["node"]))
                    else:
                        stopped_nodes.discard(str(step["node"]))
            elif kind == "observe":
                value, attempts = _observe_value(step, transport, sleep, monotonic)
                metric = str(step["metric"])
                metrics[metric] = value
                observations[metric] = (str(step["node"]), str(step["application"]), str(step["path"]))
                detail.update({"node": step["node"], "metric": metric, "value": value, "attempts": attempts})
            elif kind == "assert":
                metric = str(step["metric"])
                expected = metrics[str(step["value_metric"])] if "value_metric" in step else step.get("value")
                actual, attempts, passed, comparison_error = _eventual_assertion(
                    step,
                    metric,
                    expected,
                    metrics,
                    observations,
                    transport,
                    sleep,
                    monotonic,
                )
                assertion = {
                    "index": index,
                    "metric": metric,
                    "op": step["op"],
                    "actual": actual,
                    "attempts": attempts,
                    **(
                        {"expected": expected, "expected_metric": step["value_metric"]}
                        if "value_metric" in step
                        else {"expected": expected}
                    ),
                    "ok": passed,
                }
                if comparison_error is not None:
                    assertion["error"] = comparison_error
                assertions.append(assertion)
                detail.update(assertion)
                if not passed:
                    raise GarDomainError(comparison_error or f"assertion failed: {metric} {step['op']}")
            else:  # wait
                milliseconds = int(step["milliseconds"])
                sleep(milliseconds / 1000)
                detail["milliseconds"] = milliseconds
        except Exception as error:
            detail["ok"] = False
            detail["error"] = str(error)
            failures.append({"index": index, "type": step["type"], "error": str(error)})
            steps.append(detail)
            break
        steps.append(detail)
    # Declared cleanup is run regardless of the primary result.  When an old
    # scenario omitted cleanup, retain the conservative runtime-start fallback
    # so a failed recovery cannot leave a source stopped.
    cleanup_steps = list(scenario.cleanup)
    cleanup_steps.extend(
        {"type": "command", "node": node, "via": "runtime", "action": "start", "params": {}}
        for node in sorted(stopped_nodes)
        if not any(
            str(step["node"]) == node and step["via"] == "runtime" and step["action"] == "start"
            for step in cleanup_steps
        )
    )
    for index, step in enumerate(cleanup_steps, start=1):
        detail: dict[str, object] = {
            "index": index,
            "type": "command",
            "node": step["node"],
            "via": step["via"],
            "action": step["action"],
            "ok": True,
        }
        try:
            detail["response"] = transport.command(
                str(step["node"]), str(step["via"]), str(step["action"]), _mapping(step["params"])
            )
        except Exception as error:
            detail.update({"ok": False, "error": str(error)})
            failures.append({"type": "cleanup", "node": str(step["node"]), "error": str(error)})
        cleanup.append(detail)
    return ScenarioReport(scenario.name, steps, metrics, assertions, cleanup, failures)


def _step(
    raw: object,
    index: int,
    topology: SystemTopology,
    metrics: set[str],
) -> dict[str, object]:
    where = f"scenario.steps[{index}]"
    step = _object(raw, where)
    kind = _nonempty(step.get("type"), f"{where}.type")
    if kind == "command":
        _fields(step, {"type", "node", "via", "action", "params"}, {"type", "node", "action"}, where)
        node = _scenario_node(step.get("node"), where, topology)
        via = step.get("via", "bridge")
        if via not in {"bridge", "runtime"}:
            raise GarDomainError(f"{where}.via は bridge または runtime である必要があります")
        action = _nonempty(step.get("action"), f"{where}.action")
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise GarDomainError(f"{where}.params はobjectである必要があります")
        if via == "runtime" and (action not in {"start", "stop"} or params):
            raise GarDomainError(f"{where}: runtime commandはparamsなしのstartまたはstopだけです")
        if via == "bridge":
            _bridge_command(action, params, where)
            try:
                io_actions.resolve(action, _optional_string(params.get("device")), params)
            except (KeyError, TypeError, ValueError) as error:
                raise GarDomainError(f"{where} のbridge commandが不正です: {error}") from error
        return {"type": kind, "node": node, "via": via, "action": action, "params": dict(params)}
    if kind == "observe":
        _fields(
            step,
            {"type", "node", "metric", "path", "timeout_ms", "interval_ms"},
            {"type", "node", "metric", "path"},
            where,
        )
        node = _scenario_node(step.get("node"), where, topology)
        metric_kind = _metric(step.get("metric"), f"{where}.metric")
        path = _path(step.get("path"), f"{where}.path")
        metric = f"{node}.{metric_kind}.{path}" if "." not in metric_kind else metric_kind
        result: dict[str, object] = {
            "type": kind,
            "node": node,
            "application": topology.nodes[node].app,
            "metric": metric,
            "path": path,
        }
        return _eventual_fields(step, result, where)
    if kind == "assert":
        _fields(
            step,
            {"type", "metric", "op", "value", "value_metric", "timeout_ms", "interval_ms"},
            {"type", "metric", "op"},
            where,
        )
        metric = _metric(step.get("metric"), f"{where}.metric")
        if metric not in metrics:
            raise GarDomainError(f"{where}.metric は先行するobserve metricを参照する必要があります: {metric}")
        op = _nonempty(step.get("op"), f"{where}.op")
        if op not in _OPERATORS:
            raise GarDomainError(f"{where}.op は {sorted(_OPERATORS)} のいずれかである必要があります")
        if op == "exists":
            if "value" in step or "value_metric" in step:
                raise GarDomainError(f"{where}.value/value_metric は exists assertionに指定できません")
            result: dict[str, object] = {"type": kind, "metric": metric, "op": op}
            return _eventual_fields(step, result, where)
        has_value, has_value_metric = "value" in step, "value_metric" in step
        if has_value == has_value_metric:
            raise GarDomainError(f"{where} は value または value_metric のどちらか一方が必要です")
        if has_value:
            if not _scalar(step["value"]):
                raise GarDomainError(f"{where}.value はscalarである必要があります")
            result = {"type": kind, "metric": metric, "op": op, "value": step["value"]}
        else:
            value_metric = _metric(step["value_metric"], f"{where}.value_metric")
            if value_metric not in metrics:
                raise GarDomainError(
                    f"{where}.value_metric は先行するobserve metricを参照する必要があります: {value_metric}"
                )
            result = {"type": kind, "metric": metric, "op": op, "value_metric": value_metric}
        return _eventual_fields(step, result, where)
    if kind == "wait":
        _fields(step, {"type", "milliseconds"}, {"type", "milliseconds"}, where)
        milliseconds = step.get("milliseconds")
        if not isinstance(milliseconds, int) or isinstance(milliseconds, bool) or not 0 <= milliseconds <= 60_000:
            raise GarDomainError(f"{where}.milliseconds は0から60000の整数である必要があります")
        return {"type": kind, "milliseconds": milliseconds}
    raise GarDomainError(f"{where}.type は command、observe、assert、wait のいずれかである必要があります")


def _bridge_command(action: str, params: Mapping[str, object], where: str) -> None:
    if action not in {"rotate", "press"} or params.get("device") != "rotary":
        raise GarDomainError(f"{where}: bridge commandはdevice=rotaryのrotateまたはpressだけです")
    allowed = {"device"} | ({"direction"} if action == "rotate" else set())
    if set(params) != allowed:
        raise GarDomainError(f"{where}.params は {sorted(allowed)} と一致する必要があります")
    if action == "rotate" and (
        not isinstance(params["direction"], int)
        or isinstance(params["direction"], bool)
        or params["direction"] not in {-1, 1}
    ):
        raise GarDomainError(f"{where}.params.direction は-1または1の整数である必要があります")


def _eventual_fields(step: Mapping[str, object], result: dict[str, object], where: str) -> dict[str, object]:
    timeout = step.get("timeout_ms", 0)
    interval = step.get("interval_ms", 100)
    for name, value in (("timeout_ms", timeout), ("interval_ms", interval)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 60_000:
            raise GarDomainError(f"{where}.{name} は0から60000の整数である必要があります")
    if timeout and not interval:
        raise GarDomainError(f"{where}.interval_ms はtimeout_ms指定時に1以上です")
    if timeout:
        result["timeout_ms"] = timeout
        result["interval_ms"] = interval
    return result


def _eventual_assertion(
    step: Mapping[str, object],
    metric: str,
    expected: object,
    metrics: dict[str, object],
    observations: Mapping[str, tuple[str, str, str]],
    adapter: BridgeScenarioAdapter,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> tuple[object, int, bool, str | None]:
    timeout = int(step.get("timeout_ms", 0))
    interval = int(step.get("interval_ms", 100))
    attempts = 0
    deadline = monotonic() + timeout / 1000
    while True:
        attempts += 1
        actual = metrics[metric]
        comparison_error: str | None = None
        try:
            passed = _compare(str(step["op"]), actual, expected)
        except GarDomainError as error:
            passed = False
            comparison_error = str(error)
        if passed:
            return actual, attempts, True, None
        if not timeout or monotonic() >= deadline:
            return actual, attempts, False, comparison_error
        observed = observations.get(metric)
        if observed is None:
            return actual, attempts, False, comparison_error
        sleep(interval / 1000)
        node, application, path = observed
        metrics[metric] = _get_path(adapter.metrics(node, application), path)


def _observe_value(
    step: Mapping[str, object],
    adapter: BridgeScenarioAdapter,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> tuple[object, int]:
    timeout = int(step.get("timeout_ms", 0))
    interval = int(step.get("interval_ms", 100))
    deadline = monotonic() + timeout / 1000
    attempts = 0
    while True:
        attempts += 1
        try:
            state = adapter.metrics(str(step["node"]), str(step["application"]))
            return _get_path(state, str(step["path"])), attempts
        except GarDomainError:
            if not timeout or monotonic() >= deadline:
                raise
            sleep(interval / 1000)


def _scenario_node(raw: object, where: str, topology: SystemTopology) -> str:
    node = _identifier(raw, f"{where}.node")
    if node not in topology.nodes:
        raise GarDomainError(f"{where}.node は存在しないnodeです: {node}")
    if topology.nodes[node].environment != "sim":
        raise GarDomainError(f"{where}.node はsim nodeである必要があります: {node}")
    return node


def _compare(op: str, actual: object, expected: object) -> bool:
    if op == "exists":
        return actual is not None
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if not isinstance(actual, int | float) or isinstance(actual, bool) or not math.isfinite(actual):
        raise GarDomainError(f"numeric assertion requires a numeric metric, got {type(actual).__name__}")
    if not isinstance(expected, int | float) or isinstance(expected, bool) or not math.isfinite(expected):
        raise GarDomainError("numeric assertion requires a numeric value")
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    return actual <= expected


def _get_path(value: object, path: str) -> object:
    current = value
    try:
        for part in path.split("."):
            if isinstance(current, dict):
                current = current[part]
            elif isinstance(current, list):
                current = current[int(part)]
            else:
                raise KeyError(part)
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise GarDomainError(f"scenario state pathがありません: {path}") from error
    return current


def _object(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GarDomainError(f"{where} はobjectである必要があります")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _only(value: Mapping[str, object], allowed: set[str], where: str) -> None:
    _fields(value, allowed, allowed, where)


def _fields(value: Mapping[str, object], allowed: set[str], required: set[str], where: str) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown or missing:
        raise GarDomainError(f"{where} のfieldが不正です: unknown={sorted(unknown)}, missing={sorted(missing)}")


def _nonempty(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GarDomainError(f"{where} は空でない文字列である必要があります")
    return value.strip()


def _identifier(value: object, where: str) -> str:
    text = _nonempty(value, where)
    if text[0] not in "abcdefghijklmnopqrstuvwxyz" or any(char not in _IDENTIFIER_CHARS for char in text):
        raise GarDomainError(f"{where} は安全なidentifierである必要があります")
    return text


def _metric(value: object, where: str) -> str:
    text = _nonempty(value, where)
    if any(
        not part or part[0] not in "abcdefghijklmnopqrstuvwxyz" or any(char not in _IDENTIFIER_CHARS for char in part)
        for part in text.split(".")
    ):
        raise GarDomainError(f"{where} は dot-separated safe metric名である必要があります")
    return text


def _path(value: object, where: str) -> str:
    text = _nonempty(value, where)
    if any(not part or not part.replace("_", "").replace("-", "").isalnum() for part in text.split(".")):
        raise GarDomainError(f"{where} は安全なstate pathである必要があります")
    return text


def _scalar(value: object) -> bool:
    return (isinstance(value, str | int | bool) or value is None) or (isinstance(value, float) and math.isfinite(value))


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"JSON numeric constant is not allowed: {value}")

from __future__ import annotations

import inspect
import pkgutil
from pathlib import Path

import scripts.gar_lib.environments.registry as registry_pkg
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption


class EnvironmentDiscoveryError(RuntimeError):
    pass


CATEGORY_METADATA = {
    "codespace": {
        "name": "開発環境",
        "order": 10,
    },
    "simulator": {
        "name": "シミュレート環境",
        "order": 20,
    },
    "target": {
        "name": "実機環境",
        "order": 30,
    },
}


def discover_environments() -> list[type[EnvironmentSetupOption]]:
    environments: list[type[EnvironmentSetupOption]] = []
    environment_ids: dict[str, type[EnvironmentSetupOption]] = {}

    for module_info in pkgutil.walk_packages(
        registry_pkg.__path__,
        prefix=f"{registry_pkg.__name__}.",
    ):
        if not _is_environment_module(module_info.name):
            continue

        module = __import__(module_info.name, fromlist=[""])
        category_id = _category_id_for_module(module.__name__)
        category = CATEGORY_METADATA.get(category_id, {})

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is EnvironmentSetupOption:
                continue
            if not issubclass(obj, EnvironmentSetupOption):
                continue
            if obj.__module__ != module.__name__:
                continue

            _validate_environment(obj)
            existing = environment_ids.get(obj.environment_id)
            if existing is not None:
                raise EnvironmentDiscoveryError(
                    "duplicate environment_id "
                    f"{obj.environment_id!r}: {existing.__name__}, {obj.__name__}"
            )
            environment_ids[obj.environment_id] = obj
            obj.category_id = category_id
            obj.category_name = category.get("name", category_id)
            obj.category_order = category.get("order", 100)
            environments.append(obj)

    return sorted(
        environments,
        key=lambda cls: (
            cls.category_order,
            cls.display_order,
            cls.display_name.lower(),
        ),
    )


def _validate_environment(environment: type[EnvironmentSetupOption]) -> None:
    for attr in ("environment_id", "display_name", "description"):
        value = getattr(environment, attr, None)
        if not isinstance(value, str) or not value.strip():
            raise EnvironmentDiscoveryError(
                f"{environment.__name__} must define non-empty {attr}"
            )

    required_commands = getattr(environment, "required_commands", None)
    if not isinstance(required_commands, tuple):
        raise EnvironmentDiscoveryError(
            f"{environment.__name__}.required_commands must be a tuple[str, ...]"
        )
    if not all(isinstance(command, str) for command in required_commands):
        raise EnvironmentDiscoveryError(
            f"{environment.__name__}.required_commands must contain strings only"
        )

def _is_environment_module(module_name: str) -> bool:
    relative = module_name.removeprefix(f"{registry_pkg.__name__}.")
    parts = relative.split(".")
    if len(parts) != 2:
        return False
    return not any(part.startswith("_") for part in parts)


def _category_id_for_module(module_name: str) -> str:
    relative = module_name.removeprefix(f"{registry_pkg.__name__}.")
    return Path(relative.replace(".", "/")).parts[0]

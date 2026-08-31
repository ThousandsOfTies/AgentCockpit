"""Environment setup choices, registered explicitly by category."""

from scripts.gar_lib.environments.registry.codespace import (
    ENVIRONMENT_OPTIONS as DEVELOPMENT_ENVIRONMENTS,
)
from scripts.gar_lib.environments.registry.simulation_host import (
    ENVIRONMENT_OPTIONS as SIMULATION_HOST_ENVIRONMENTS,
)
from scripts.gar_lib.environments.registry.simulator import (
    ENVIRONMENT_OPTIONS as SIMULATION_ENVIRONMENTS,
)
from scripts.gar_lib.environments.registry.target import (
    ENVIRONMENT_OPTIONS as TARGET_ENVIRONMENTS,
)
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption

ENVIRONMENT_OPTIONS: tuple[type[EnvironmentSetupOption], ...] = (
    *DEVELOPMENT_ENVIRONMENTS,
    *SIMULATION_ENVIRONMENTS,
    *SIMULATION_HOST_ENVIRONMENTS,
    *TARGET_ENVIRONMENTS,
)

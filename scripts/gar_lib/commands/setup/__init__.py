"""Public entry points for the ``gar setup`` command package."""

from scripts.gar_lib.commands.setup.command import (
    add_setup_parser,
    run_setup,
    run_setup_cli,
)
from scripts.gar_lib.commands.setup.environment_setup import (
    EnvironmentCategory,
    EnvironmentSelection,
    EnvironmentSelectionStatus,
    configure_default_ec2_host,
    ensure_environment_dependencies,
    first_unconfigured_category_index,
)
from scripts.gar_lib.commands.setup.target_setup import configure_target_connection
from scripts.gar_lib.commands.setup.workspace_setup import (
    default_workspace_name,
    default_workspace_product_name,
)

__all__ = [
    "EnvironmentCategory",
    "EnvironmentSelection",
    "EnvironmentSelectionStatus",
    "add_setup_parser",
    "configure_default_ec2_host",
    "configure_target_connection",
    "default_workspace_name",
    "default_workspace_product_name",
    "ensure_environment_dependencies",
    "first_unconfigured_category_index",
    "run_setup",
    "run_setup_cli",
]

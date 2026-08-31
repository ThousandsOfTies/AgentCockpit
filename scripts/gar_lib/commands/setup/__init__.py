"""Implementation package for the public ``gar config`` command."""

from scripts.gar_lib.commands.setup.command import (
    add_config_parser,
    run_config_cli,
    run_setup,
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
    "add_config_parser",
    "configure_default_ec2_host",
    "configure_target_connection",
    "default_workspace_name",
    "default_workspace_product_name",
    "ensure_environment_dependencies",
    "first_unconfigured_category_index",
    "run_setup",
    "run_config_cli",
]

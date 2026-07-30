"""Concrete build environments."""

from scripts.gar_lib.build.environment import BuildEnvironment, build_environment_for
from scripts.gar_lib.build.spec import (
    BuildSpec,
    ProductBuildSpecResolver,
)
from scripts.gar_lib.build.codespaces import CodespacesBuildEnvironment
from scripts.gar_lib.build.local import LocalBuildEnvironment

__all__ = [
    "BuildEnvironment",
    "BuildSpec",
    "CodespacesBuildEnvironment",
    "LocalBuildEnvironment",
    "ProductBuildSpecResolver",
    "build_environment_for",
]

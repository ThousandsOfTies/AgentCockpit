"""Concrete build environments."""

from scripts.gar_lib.build._base import (
    BuildEnvironment,
    BuildSpec,
    ProductBuildSpecResolver,
)
from scripts.gar_lib.build.backends import build_environment_for
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

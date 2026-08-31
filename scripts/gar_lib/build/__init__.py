"""Concrete build environments."""

from scripts.gar_lib.build.codespaces import CodespacesBuildEnvironment
from scripts.gar_lib.build.docker import DockerBuildEnvironment
from scripts.gar_lib.build.environment import BuildEnvironment, build_environment_for
from scripts.gar_lib.build.local import LocalBuildEnvironment
from scripts.gar_lib.build.spec import (
    BuildSpec,
    ProductBuildSpecResolver,
)

__all__ = [
    "BuildEnvironment",
    "BuildSpec",
    "CodespacesBuildEnvironment",
    "DockerBuildEnvironment",
    "LocalBuildEnvironment",
    "ProductBuildSpecResolver",
    "build_environment_for",
]

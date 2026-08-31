"""Explicit registry of SimulationHost providers."""

from scripts.gar_lib.environments.registry.simulation_host.aws_ec2 import AwsEc2SimulationHostSetup
from scripts.gar_lib.environments.registry.simulation_host.virtualbox import VirtualBoxSimulationHostSetup
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption

ENVIRONMENT_OPTIONS: tuple[type[EnvironmentSetupOption], ...] = (
    VirtualBoxSimulationHostSetup,
    AwsEc2SimulationHostSetup,
)

# gar_lib 公開メンバ参照一覧

`tools/gen_gar_lib_dsm.py` により自動生成。 各moduleのtop-level公開関数/class/UPPER定数が、どのmoduleから参照されているかを一覧化。

注意: 静的なimport解析のみのため、`mock.patch("...")` の文字列指定や `getattr` 経由の参照は数え漏れることがあります。

## `access.adb` (scripts/gar_lib/access/adb.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AdbShellChannel` | 45 | target.composition(2), tests.test_gar_access_channels(2) |
| `AdbFileChannel` | 53 | target.composition(2), tests.test_gar_access_channels(1) |

## `access.aws` (scripts/gar_lib/access/aws.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsCommandChannel` | 24 | simulation.host.aws_ec2(1), simulation.runtime.aws_ssm(1) |
| `AwsCliChannel` | 28 | simulation.composition(2), tests.test_gar_simulation_host(1) |

## `access.channel` (scripts/gar_lib/access/channel.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AccessResult` | 13 | access.adb(4), access.aws(2), access.docker(6), access.ssh(4), simulation.diagnostics.model(1), simulation.hardware.control(1), simulation.host.aws_ec2(1), tests.test_gar_docker_simulation_host(23), tests.test_gar_hardware_control(4), tests.test_gar_linux_systemd_environment(7), tests.test_gar_simulation_host(10) |
| `ConsoleSession` | 23 | access.serial(2) |
| `CommandChannel` | 27 | simulation.hardware.control(1), simulation.host.aws_ec2(1), simulation.host.docker(1), simulation.runtime.linux_systemd(1), target.file_transfer(1) |
| `FileChannel` | 31 | simulation.runtime.linux_systemd(1), target.file_transfer(1) |
| `ConsoleChannel` | 37 | _(外部参照なし)_ |
| `run_cli` | 44 | access.adb(2), access.aws(1), access.docker(3), access.ssh(2) |

## `access.codespaces` (scripts/gar_lib/access/codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `select_codespace_from_list` | 6 | artifacts.manifest(1), commands.code(2), tests.test_gar_access_codespaces(2) |
| `codespace_list_rows` | 17 | commands.code(1), tests.test_gar_access_codespaces(1) |

## `access.docker` (scripts/gar_lib/access/docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DAEMON_FAILURE_MARKERS` | 13 | _(外部参照なし)_ |
| `CONTAINER_FAILURE_MARKERS` | 20 | _(外部参照なし)_ |
| `docker_executable` | 28 | _(外部参照なし)_ |
| `connection_reason` | 35 | _(外部参照なし)_ |
| `DockerCliCommandChannel` | 44 | simulation.host.docker(1) |
| `DockerCliChannel` | 48 | simulation.composition(1), tests.test_gar_docker_simulation_host(2) |
| `DockerCommandChannel` | 64 | simulation.composition(3), tests.test_gar_docker_simulation_host(4) |
| `DockerFileChannel` | 93 | simulation.composition(1), tests.test_gar_docker_simulation_host(2) |

## `access.serial` (scripts/gar_lib/access/serial.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SerialConsoleChannel` | 10 | tests.test_gar_access_channels(1) |

## `access.ssh` (scripts/gar_lib/access/ssh.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SSH_CONNECTION_OPTIONS` | 11 | _(外部参照なし)_ |
| `SshCommandChannel` | 38 | simulation.composition(3), target.composition(1), tests.test_gar_access_channels(3) |
| `ScpFileChannel` | 65 | simulation.composition(1), target.composition(1), tests.test_gar_access_channels(1) |

## `api` (scripts/gar_lib/api.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Gar` | 25 | commands.sim(7), commands.target(1), tests.test_gar_sim_architecture(4), tests.test_gar_sim_lifecycle(7), tests.test_gar_target_architecture(2) |
| `Simulation` | 32 | _(外部参照なし)_ |
| `SimulationApp` | 43 | _(外部参照なし)_ |
| `SimulationRuntime` | 61 | _(外部参照なし)_ |
| `SimulationHost` | 126 | _(外部参照なし)_ |
| `SimulationGpio` | 148 | _(外部参照なし)_ |
| `SimulationIo` | 177 | _(外部参照なし)_ |
| `Target` | 202 | _(外部参照なし)_ |

## `artifacts.manifest` (scripts/gar_lib/artifacts/manifest.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_CODESPACE_ARTIFACT_ROOT` | 27 | _(外部参照なし)_ |
| `ArtifactManifestError` | 30 | _(外部参照なし)_ |
| `DeployFile` | 35 | _(外部参照なし)_ |
| `DeploySection` | 50 | _(外部参照なし)_ |
| `ArtifactManifest` | 69 | _(外部参照なし)_ |
| `parse_artifact_manifest` | 93 | tests.test_gar_artifacts(1) |
| `default_artifacts_dir` | 151 | _(外部参照なし)_ |
| `default_codespace_artifact_root` | 155 | _(外部参照なし)_ |
| `select_codespace` | 159 | _(外部参照なし)_ |
| `gh_env` | 181 | _(外部参照なし)_ |
| `artifact_manifest_deploy_sources` | 187 | _(外部参照なし)_ |
| `fetch_codespace_artifacts` | 201 | artifacts.store(1), tests.test_gar_target_cli(1) |
| `gh_codespace_cp` | 270 | _(外部参照なし)_ |
| `find_artifact_manifest` | 284 | _(外部参照なし)_ |
| `load_artifact_manifest` | 295 | _(外部参照なし)_ |
| `artifact_deploy_files` | 316 | _(外部参照なし)_ |
| `resolve_artifact_src` | 332 | simulation.runtime.linux_systemd(1), simulation.runtime.mujoco(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1), tests.test_gar_artifacts(2) |
| `load_deploy_files` | 372 | artifacts.store(1), simulation.runtime.linux_systemd(1), simulation.runtime.mujoco(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1) |
| `target_dest_path` | 385 | target.file_transfer(1) |

## `artifacts.store` (scripts/gar_lib/artifacts/store.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ArtifactStore` | 21 | _(外部参照なし)_ |
| `BuildArtifactStore` | 25 | api(5), build.codespaces(1), build.environment(1), build.local(1) |
| `LocalArtifactStore` | 35 | api(1), tests.test_gar_artifacts(2), tests.test_gar_sim_architecture(4), tests.test_gar_target_architecture(1) |

## `build.codespaces` (scripts/gar_lib/build/codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `CodespacesBuildEnvironment` | 16 | build.environment(1), tests.test_gar_build_variables(1), tests.test_gar_sim_architecture(2) |

## `build.environment` (scripts/gar_lib/build/environment.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `BuildEnvironment` | 15 | _(外部参照なし)_ |
| `build_environment_for` | 23 | api(5), tests.test_gar_sim_architecture(2), tests.test_gar_target_architecture(1) |

## `build.local` (scripts/gar_lib/build/local.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalBuildEnvironment` | 15 | build.environment(1), tests.test_gar_build_variables(1), tests.test_gar_sim_architecture(2) |

## `build.spec` (scripts/gar_lib/build/spec.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_REMOTE_SIM_ARCH` | 14 | _(外部参照なし)_ |
| `BuildSpec` | 18 | _(外部参照なし)_ |
| `compiler_for_architecture` | 23 | _(外部参照なし)_ |
| `simulation_build_variables` | 31 | _(外部参照なし)_ |
| `ProductBuildSpecResolver` | 49 | build.codespaces(2), build.local(2), tests.test_gar_build_variables(1) |

## `cli` (scripts/gar_lib/cli.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `CliParserBundle` | 20 | _(外部参照なし)_ |
| `normalize_question_help` | 27 | tests.test_gar_cli(2) |
| `enable_argcomplete` | 38 | _(外部参照なし)_ |
| `build_parser_bundle` | 46 | tests.test_gar_cli(1) |
| `build_parser` | 65 | tests.test_gar_cli(1) |
| `run_cli_command` | 71 | _(外部参照なし)_ |
| `main` | 99 | scripts.gar(entrypoint)(1), __main__(1), tests.support.gar_cli_test_support(2), tests.test_gar_cli(9), tests.test_gar_code_cli(6), tests.test_gar_sim_io(1), tests.test_gar_sim_lifecycle(1), tests.test_gar_target_architecture(1), tests.test_gar_terminal_hw(7), tests.test_gar_usb(1) |

## `commands.code` (scripts/gar_lib/commands/code.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_CODESPACE_REMOTE_PATH` | 40 | _(外部参照なし)_ |
| `CodeStartOptions` | 44 | _(外部参照なし)_ |
| `add_code_parser` | 79 | cli(1) |
| `run_code_cli` | 134 | cli(1) |
| `run_code_command` | 151 | tests.test_gar_code(1), tests.test_gar_code_cli(2) |
| `run_local_code_command` | 229 | _(外部参照なし)_ |
| `boot_code_codespace` | 246 | _(外部参照なし)_ |
| `start_code_codespace` | 284 | tests.test_gar_code(2), tests.test_gar_code_cli(4) |
| `resolve_code_start_options` | 380 | _(外部参照なし)_ |
| `validate_code_start_options` | 426 | _(外部参照なし)_ |
| `configure_codespace_ssh` | 458 | _(外部参照なし)_ |
| `resolve_codespace_remote_path` | 488 | _(外部参照なし)_ |
| `configure_vscode_codespace` | 508 | _(外部参照なし)_ |
| `report_codespace_start` | 521 | _(外部参照なし)_ |
| `stop_code_codespace` | 534 | tests.test_gar_code_cli(2) |
| `shutdown_code_codespace` | 588 | tests.test_gar_code_cli(1) |
| `status_code_codespace` | 637 | _(外部参照なし)_ |
| `select_code_codespace` | 690 | _(外部参照なし)_ |
| `load_codespace_state` | 725 | _(外部参照なし)_ |
| `default_codespaces_mount_dir` | 731 | _(外部参照なし)_ |

## `commands.code_connection` (scripts/gar_lib/commands/code_connection.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_GH_TIMEOUT_SECONDS` | 13 | _(外部参照なし)_ |
| `SSH_CONFIG_INCLUDE` | 14 | _(外部参照なし)_ |
| `gh_timeout_seconds` | 17 | commands.code(4) |
| `run_gh_captured` | 39 | commands.code(6) |
| `print_completed_stderr` | 69 | commands.code(6) |
| `install_codespace_ssh_config` | 75 | commands.code(1) |
| `first_ssh_host` | 90 | tests.test_gar_code(1) |
| `remote_path_exists` | 103 | commands.code(1), tests.test_gar_code(1) |
| `detect_codespace_workspace` | 119 | commands.code(1) |
| `run_codespace_remote` | 137 | _(外部参照なし)_ |
| `mount_codespace_code` | 156 | commands.code(1), tests.test_gar_code(1) |
| `unmount_codespace_code` | 199 | commands.code(2) |

## `commands.code_state` (scripts/gar_lib/commands/code_state.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `CodespaceConnectionState` | 14 | commands.code(3), tests.test_gar_code(5) |
| `codespace_state_path` | 91 | commands.code(2) |
| `load_connection_state` | 96 | commands.code(4), tests.test_gar_code(1) |
| `load_legacy_codespace_state` | 120 | commands.code(1) |
| `codespace_terminal_script` | 147 | commands.code(1), tests.test_gar_code(1) |

## `commands.completion` (scripts/gar_lib/commands/completion.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `add_completion_parser` | 10 | cli(1) |
| `run_completion_command` | 25 | cli(1) |
| `completion_bash_script` | 42 | _(外部参照なし)_ |
| `parser_completion_words` | 56 | _(外部参照なし)_ |

## `commands.hw` (scripts/gar_lib/commands/hw.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `add_hw_parser` | 12 | cli(1) |
| `run_hw_cli` | 41 | cli(1) |
| `run_hw_command` | 53 | _(外部参照なし)_ |

## `commands.infra` (scripts/gar_lib/commands/infra.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TERRAFORM_DIR` | 26 | _(外部参照なし)_ |
| `run_sim_infra_command` | 203 | commands.sim(1), tests.test_gar_sim_infra(4) |

## `commands.recovery` (scripts/gar_lib/commands/recovery.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RecoveryAction` | 16 | _(外部参照なし)_ |
| `report_access_failure` | 22 | commands.sim(1), commands.target(1), tests.test_gar_access_recovery(1) |
| `plan_access_recovery` | 51 | tests.test_gar_access_recovery(3) |

## `commands.setup.command` (scripts/gar_lib/commands/setup/command.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `add_setup_parser` | 64 | _(外部参照なし)_ |
| `run_setup_cli` | 89 | _(外部参照なし)_ |
| `run_setup` | 97 | _(外部参照なし)_ |
| `ensure_gar_tools_for_setup` | 371 | _(外部参照なし)_ |
| `clear_setup_screen` | 384 | _(外部参照なし)_ |
| `print_terminal_bridge_status` | 390 | _(外部参照なし)_ |

## `commands.setup.environment_setup` (scripts/gar_lib/commands/setup/environment_setup.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `EnvironmentCategory` | 33 | _(外部参照なし)_ |
| `SetupMenuChoice` | 41 | commands.setup.command(2) |
| `EnvironmentSelectionStatus` | 46 | commands.setup.command(2) |
| `EnvironmentSelection` | 53 | _(外部参照なし)_ |
| `configure_default_ec2_host` | 72 | commands.setup.command(2) |
| `ensure_environment_dependencies` | 119 | commands.setup.command(1), tests.test_gar_config_context(1) |
| `print_environment_overview` | 173 | commands.setup.command(1) |
| `select_setup_category` | 209 | commands.setup.command(1) |
| `select_environment_for_category` | 281 | commands.setup.command(1) |
| `unconfigured_categories` | 345 | commands.setup.command(2) |
| `first_unconfigured_category_index` | 370 | _(外部参照なし)_ |
| `grouped_environments` | 401 | _(外部参照なし)_ |
| `environment_by_id` | 424 | _(外部参照なし)_ |

## `commands.setup.target_setup` (scripts/gar_lib/commands/setup/target_setup.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `configure_target` | 29 | commands.setup.command(1) |
| `save_selected_target` | 48 | commands.setup.command(1) |
| `ensure_selected_target_ready` | 56 | _(外部参照なし)_ |
| `prune_removed_target_backends` | 63 | _(外部参照なし)_ |
| `removable_target_backend_categories` | 70 | _(外部参照なし)_ |
| `managed_backend_categories` | 74 | _(外部参照なし)_ |
| `prepare_target_backend` | 85 | commands.setup.command(1) |
| `select_target` | 97 | commands.setup.command(1) |
| `print_target_summary` | 113 | _(外部参照なし)_ |
| `print_selected_target_summary` | 126 | _(外部参照なし)_ |
| `selected_target_manifest` | 138 | commands.setup.command(3) |
| `optional_setup_categories` | 146 | commands.setup.command(2) |
| `configure_esp32_serial_port` | 175 | commands.setup.command(1) |
| `configure_target_connection` | 223 | commands.setup.command(2) |
| `detect_esp32_serial_port_candidates` | 273 | _(外部参照なし)_ |
| `print_target_next_steps` | 283 | commands.setup.command(1) |

## `commands.setup.workspace_setup` (scripts/gar_lib/commands/setup/workspace_setup.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `configure_workspace_root` | 29 | commands.setup.command(1), tests.test_gar_workspace_setup(1) |
| `print_workspace_entry` | 157 | _(外部参照なし)_ |
| `workspace_duplicate` | 168 | _(外部参照なし)_ |
| `default_workspace_name` | 190 | _(外部参照なし)_ |
| `default_workspace_product_name` | 201 | _(外部参照なし)_ |
| `prompt_workspace_entry` | 209 | _(外部参照なし)_ |
| `print_codespace_candidates` | 327 | _(外部参照なし)_ |
| `probe_git_workspace` | 342 | _(外部参照なし)_ |

## `commands.sim` (scripts/gar_lib/commands/sim.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SIM_ACTIONS` | 28 | _(外部参照なし)_ |
| `add_sim_parser` | 102 | cli(1) |
| `run_sim_command` | 297 | cli(1) |

## `commands.target` (scripts/gar_lib/commands/target.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TARGET_ACTIONS` | 17 | _(外部参照なし)_ |
| `add_target_parser` | 24 | cli(1) |
| `run_target_command` | 52 | cli(1) |

## `commands.terminal` (scripts/gar_lib/commands/terminal.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `add_terminal_parser` | 17 | cli(1) |
| `run_terminal_cli` | 59 | cli(1) |
| `run_terminal_run_command` | 79 | commands.sim(1), commands.target(1), tests.test_gar_terminal_hw(2) |
| `run_terminal_gc_command` | 112 | tests.test_gar_terminal_hw(2) |

## `commands.usb` (scripts/gar_lib/commands/usb.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ANDROID_HINTS` | 32 | _(外部参照なし)_ |
| `ANDROID_VIDS` | 34 | _(外部参照なし)_ |
| `add_usb_parser` | 37 | cli(1) |
| `run_usb_cli` | 76 | cli(1) |
| `UsbDevice` | 92 | _(外部参照なし)_ |
| `UsbipdCommandError` | 118 | _(外部参照なし)_ |
| `parse_usbipd_list` | 248 | tests.test_gar_usb(6) |
| `list_usb_devices` | 297 | _(外部参照なし)_ |
| `run_usb_command` | 305 | tests.test_gar_usb(5), tests.test_gar_usb_failures(2) |

## `commands.workspace_resolver` (scripts/gar_lib/commands/workspace_resolver.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `resolve_workspace` | 97 | commands.code(1), commands.sim(1), commands.target(1), tests.test_gar_setup_config(1), tests.test_gar_sim_architecture(5) |

## `core.archive` (scripts/gar_lib/core/archive.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `UnsafeArchiveError` | 9 | environments.installers.renode(1), tests.test_gar_archive(3) |
| `safe_extract_tar` | 13 | environments.installers.renode(1), tests.test_gar_archive(4) |

## `core.artifact` (scripts/gar_lib/core/artifact.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ArtifactKind` | 12 | api(8), artifacts.store(16), build.codespaces(3), build.environment(3), build.local(3), build.spec(6), simulation.runtime.linux_systemd(3), simulation.runtime.mujoco(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1), tests.test_gar_artifacts(5), tests.test_gar_build_variables(8), tests.test_gar_linux_systemd_environment(2), tests.test_gar_mujoco_environment(1), tests.test_gar_pending_simulation_environments(1), tests.test_gar_sim_architecture(6), tests.test_gar_target_architecture(7), tests.test_gar_wokwi_environment(5) |
| `Artifact` | 19 | api(7), artifacts.store(10), build.codespaces(2), build.environment(2), build.local(2), commands.sim(2), simulation.runtime.contract(1), simulation.runtime.linux_systemd(1), simulation.runtime.mujoco(1), simulation.runtime.pending(1), simulation.runtime.wokwi(1), target.environment(1), target.esp32(2), target.file_transfer(1), tests.test_gar_linux_systemd_environment(2), tests.test_gar_mujoco_environment(2), tests.test_gar_pending_simulation_environments(1), tests.test_gar_target_architecture(2), tests.test_gar_wokwi_environment(5) |

## `core.command` (scripts/gar_lib/core/command.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GarCommand` | 10 | commands.sim(7), commands.target(2), tests.support.gar_cli_test_support(2), tests.test_gar_sim_io(2) |
| `SIM_APP_BUILD` | 28 | tests.test_gar_cli(3) |
| `SIM_APP_CLEAN` | 29 | tests.test_gar_cli(1) |
| `SIM_APP_DEPLOY` | 30 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_BUILD` | 31 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_DEPLOY` | 32 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_START` | 33 | tests.test_gar_sim_io(1) |
| `SIM_RUNTIME_STOP` | 34 | _(外部参照なし)_ |
| `SIM_RUNTIME_STATUS` | 35 | _(外部参照なし)_ |
| `SIM_RUNTIME_LOG` | 36 | _(外部参照なし)_ |
| `SIM_RUNTIME_DIAG` | 37 | tests.test_gar_sim_io(1) |
| `SIM_HOST_START` | 38 | tests.test_gar_cli(2) |
| `SIM_HOST_STOP` | 39 | tests.test_gar_cli(1) |
| `SIM_HOST_STATUS` | 40 | tests.test_gar_cli(2) |
| `TARGET_BUILD` | 41 | tests.test_gar_cli(1) |
| `TARGET_DEPLOY` | 42 | tests.test_gar_cli(1) |
| `TARGET_FETCH` | 43 | tests.test_gar_cli(1) |

## `core.config` (scripts/gar_lib/core/config.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `PROJECT_ROOT` | 13 | artifacts.manifest(1), artifacts.store(1), commands.infra(1), core.hardware(1), core.tools_repository(5), environments.registry.target.esp32_esptool(2), simulation.composition(1), simulation.runtime.mujoco(4), simulation.session.remote(1), vscode.terminal_bridge(1), tests.test_gar_setup_config(3) |
| `CONFIG_PATH` | 17 | commands.terminal(2) |
| `VSCODE_EXT_NAME` | 19 | vscode.terminal_bridge(3) |
| `VSCODE_EXT_VERSION` | 20 | vscode.terminal_bridge(2) |
| `DEFAULT_EC2_INSTANCE_ID` | 22 | _(外部参照なし)_ |
| `DEFAULT_EC2_REGION` | 23 | _(外部参照なし)_ |
| `RUNTIME_HOST_PATTERN` | 24 | _(外部参照なし)_ |
| `is_valid_runtime_host` | 27 | commands.setup.command(1), commands.setup.environment_setup(1) |
| `load_config` | 110 | commands.hw(1), commands.infra(1), commands.setup.command(2), commands.usb(1), commands.workspace_resolver(1), tests.test_gar_config_context(3), tests.test_gar_setup_config(5) |
| `save_config` | 246 | commands.infra(1), commands.setup.command(1), commands.setup.environment_setup(3), commands.setup.target_setup(6), commands.setup.workspace_setup(1), commands.usb(1), environments.registry.target.adb_win(1), tests.test_gar_setup_config(8) |
| `default_config` | 301 | tests.test_gar_setup_config(2) |
| `default_ec2_host` | 309 | commands.infra(2), commands.setup.command(2), commands.setup.environment_setup(1) |
| `default_ec2_instance_id` | 316 | commands.infra(1) |
| `default_ec2_region` | 323 | commands.infra(1) |
| `ec2_repo_dir` | 330 | _(外部参照なし)_ |
| `saved_usb_busid` | 337 | commands.usb(2) |
| `set_saved_usb_busid` | 344 | commands.usb(1) |
| `saved_esp32_serial_port` | 352 | commands.setup.target_setup(1) |
| `set_saved_esp32_serial_port` | 359 | commands.setup.target_setup(2) |
| `saved_target_setting` | 367 | commands.setup.target_setup(2) |
| `set_saved_target_setting` | 374 | commands.setup.target_setup(2) |
| `saved_workspaces` | 382 | commands.setup.workspace_setup(1), commands.workspace_resolver(1) |
| `set_saved_workspaces` | 386 | commands.setup.workspace_setup(1) |
| `saved_adb_exe` | 397 | environments.registry.target.adb_win(1) |
| `set_saved_adb_exe` | 404 | environments.registry.target.adb_win(1) |
| `set_default_ec2_host` | 414 | commands.setup.environment_setup(2) |
| `set_default_ec2_instance_id` | 422 | commands.infra(1) |
| `set_default_ec2_private_ip` | 430 | commands.infra(1) |
| `set_default_ec2_region` | 438 | commands.infra(1) |

## `core.errors` (scripts/gar_lib/core/errors.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GarDomainError` | 4 | access.aws(1), access.docker(1), artifacts.store(11), build.codespaces(2), build.environment(1), build.local(4), build.spec(1), commands.code(1), commands.sim(14), commands.target(6), commands.workspace_resolver(1), core.workspace(5), simulation.composition(8), simulation.host.aws_ec2(4), simulation.host.docker(7), simulation.runtime.linux_systemd(6), simulation.runtime.mujoco(8), simulation.runtime.pending(1), simulation.runtime.wokwi(15), target.composition(4), target.esp32(4), target.file_transfer(6), target.manifest(1), tests.test_gar_artifacts(1), tests.test_gar_docker_simulation_host(5), tests.test_gar_mujoco_environment(1), tests.test_gar_pending_simulation_environments(2), tests.test_gar_sim_architecture(1), tests.test_gar_simulation_host(3), tests.test_gar_wokwi_environment(4) |
| `AccessConnectionError` | 8 | access.adb(1), access.aws(1), access.docker(3), access.ssh(2), commands.recovery(2), commands.sim(1), commands.target(1), tests.test_gar_access_channels(3), tests.test_gar_access_recovery(4), tests.test_gar_docker_simulation_host(2), tests.test_gar_sim_lifecycle(1), tests.test_gar_simulation_host(1), tests.test_gar_target_architecture(1) |

## `core.hardware` (scripts/gar_lib/core/hardware.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HW_TEMPLATE_FILES` | 16 | tests.test_gar_terminal_hw(2) |
| `HW_DIR` | 46 | _(外部参照なし)_ |
| `DEFAULT_HW_TARGET` | 47 | _(外部参照なし)_ |
| `TARGET_ID_PATTERN` | 48 | _(外部参照なし)_ |
| `load_hw_definition` | 82 | api(1) |
| `write_hw_template` | 96 | commands.hw(1), tests.test_gar_terminal_hw(1) |

## `core.tools_repository` (scripts/gar_lib/core/tools_repository.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_GAR_TOOLS_REPO` | 11 | _(外部参照なし)_ |
| `gar_tools_root` | 14 | commands.workspace_resolver(1), core.hardware(1), simulation.composition(1), target.manifest(1) |
| `find_gar_tools_root` | 21 | _(外部参照なし)_ |
| `gar_tools_root_candidates` | 28 | _(外部参照なし)_ |
| `ensure_gar_tools_available` | 52 | commands.setup.command(1), tests.test_gar_setup_config(1) |

## `core.workspace` (scripts/gar_lib/core/workspace.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Workspace` | 21 | api(9), artifacts.store(13), build.codespaces(3), build.environment(4), build.local(3), build.spec(2), commands.code(2), commands.recovery(2), commands.workspace_resolver(3), core.artifact(1), simulation.composition(8), target.composition(1), tests.support.gar_cli_test_support(2), tests.test_gar_access_recovery(1), tests.test_gar_artifacts(2), tests.test_gar_build_variables(4), tests.test_gar_cli(1), tests.test_gar_code(1), tests.test_gar_code_cli(2), tests.test_gar_docker_simulation_host(2), tests.test_gar_linux_systemd_environment(2), tests.test_gar_mujoco_environment(1), tests.test_gar_pending_simulation_environments(2), tests.test_gar_sim_architecture(5), tests.test_gar_sim_lifecycle(1), tests.test_gar_simulation_host(4), tests.test_gar_target_architecture(5), tests.test_gar_wokwi_environment(2), tests.test_gar_workspace(1) |

## `core.workspace_settings` (scripts/gar_lib/core/workspace_settings.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SettingsMapping` | 10 | _(外部参照なし)_ |
| `WorkspaceConnection` | 39 | core.workspace(2), tests.test_gar_workspace(1) |
| `SelectedEnvironments` | 60 | core.workspace(3), tests.test_gar_workspace(1) |
| `Ec2Settings` | 79 | core.workspace(3), tests.test_gar_workspace(1) |
| `DockerSettings` | 98 | core.workspace(3), simulation.composition(1), tests.test_gar_workspace(2) |
| `TargetSettings` | 123 | core.workspace(3) |
| `AdbSettings` | 139 | core.workspace(3) |
| `Esp32Settings` | 153 | core.workspace(3) |

## `environments.discovery` (scripts/gar_lib/environments/discovery.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `EnvironmentDiscoveryError` | 7 | _(外部参照なし)_ |
| `discover_environments` | 11 | commands.setup.command(1), target.manifest(1), tests.test_gar_discovery(4) |

## `environments.docker_install` (scripts/gar_lib/environments/docker_install.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DOCKER_INSTALL_COMMANDS` | 12 | _(外部参照なし)_ |
| `GROUP_REFRESH_NOTE` | 20 | _(外部参照なし)_ |
| `is_wsl_or_linux` | 23 | _(外部参照なし)_ |
| `docker_install_hint` | 28 | environments.registry.codespace.local_docker(1), environments.registry.simulator.local_docker(1) |
| `install_docker` | 42 | environments.registry.codespace.local_docker(1), environments.registry.simulator.local_docker(1) |

## `environments.install` (scripts/gar_lib/environments/install.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `sudo_block_reason` | 12 | environments.docker_install(1), environments.installers.aws_ssm(1), environments.registry.codespace.github_codespaces(1), environments.registry.target.adb_usb(1) |
| `print_user_terminal_handoff` | 33 | environments.docker_install(1), environments.installers.aws_ssm(1), environments.registry.codespace.github_codespaces(1), environments.registry.target.adb_usb(1) |
| `create_visible_terminal_request` | 59 | _(外部参照なし)_ |

## `environments.installers.aws_ssm` (scripts/gar_lib/environments/installers/aws_ssm.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `aws_ssm_install_hint` | 16 | environments.registry.simulator.aws_ssm(1) |
| `install_aws_ssm_dependencies` | 21 | environments.registry.simulator.aws_ssm(1) |

## `environments.installers.renode` (scripts/gar_lib/environments/installers/renode.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RENODE_RELEASES_API` | 30 | _(外部参照なし)_ |
| `RENODE_RELEASES_PAGE` | 31 | _(外部参照なし)_ |
| `RENODE_DOCS` | 32 | _(外部参照なし)_ |
| `INSTALL_ROOT` | 34 | _(外部参照なし)_ |
| `TEST_VENV` | 35 | _(外部参照なし)_ |
| `BIN_DIR` | 36 | _(外部参照なし)_ |
| `LAUNCHER` | 37 | _(外部参照なし)_ |
| `TEST_LAUNCHER` | 38 | _(外部参照なし)_ |
| `renode_dependency_status` | 41 | environments.registry.simulator.renode_mcu(1) |
| `renode_install_hint` | 52 | environments.registry.simulator.renode_mcu(1) |
| `install_renode_dependencies` | 64 | environments.registry.simulator.renode_mcu(1) |

## `environments.registry` (scripts/gar_lib/environments/registry/__init__.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ENVIRONMENT_OPTIONS` | 14 | environments.discovery(2) |

## `environments.registry.codespace` (scripts/gar_lib/environments/registry/codespace/__init__.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ENVIRONMENT_OPTIONS` | 11 | environments.registry(1) |

## `environments.registry.codespace.github_codespaces` (scripts/gar_lib/environments/registry/codespace/github_codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GitHubCodespacesEnvironment` | 10 | environments.registry.codespace(1), tests.test_gar_discovery(7) |

## `environments.registry.codespace.local_docker` (scripts/gar_lib/environments/registry/codespace/local_docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalDockerDevelopmentSetup` | 7 | environments.registry.codespace(1) |

## `environments.registry.simulator` (scripts/gar_lib/environments/registry/simulator/__init__.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ENVIRONMENT_OPTIONS` | 16 | environments.registry(1) |

## `environments.registry.simulator.aws_ssm` (scripts/gar_lib/environments/registry/simulator/aws_ssm.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsSsmEnvironment` | 12 | environments.registry.simulator(1), tests.test_gar_discovery(3) |

## `environments.registry.simulator.esp32_qemu` (scripts/gar_lib/environments/registry/simulator/esp32_qemu.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32QemuFirmwareEnvironment` | 13 | environments.registry.simulator(1) |

## `environments.registry.simulator.local_docker` (scripts/gar_lib/environments/registry/simulator/local_docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalDockerSimulationSetup` | 7 | environments.registry.simulator(1) |

## `environments.registry.simulator.mujoco` (scripts/gar_lib/environments/registry/simulator/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `MujocoEnvironment` | 14 | environments.registry.simulator(1), tests.test_gar_discovery(1) |

## `environments.registry.simulator.renode_mcu` (scripts/gar_lib/environments/registry/simulator/renode_mcu.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RenodeMcuEnvironment` | 16 | environments.registry.simulator(1), tests.test_gar_discovery(1) |

## `environments.registry.simulator.ssh_remote` (scripts/gar_lib/environments/registry/simulator/ssh_remote.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SshRemoteEnvironment` | 6 | environments.registry.simulator(1) |

## `environments.registry.simulator.wokwi` (scripts/gar_lib/environments/registry/simulator/wokwi.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `WokwiEnvironment` | 15 | environments.registry.simulator(1), tests.test_gar_discovery(4) |

## `environments.registry.target` (scripts/gar_lib/environments/registry/target/__init__.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ENVIRONMENT_OPTIONS` | 11 | environments.registry(1) |

## `environments.registry.target.adb_usb` (scripts/gar_lib/environments/registry/target/adb_usb.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AdbUsbEnvironment` | 10 | environments.registry.target(1), tests.test_gar_discovery(2) |

## `environments.registry.target.adb_win` (scripts/gar_lib/environments/registry/target/adb_win.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `WINGET_PACKAGE_ID` | 26 | _(外部参照なし)_ |
| `AdbWinEnvironment` | 29 | environments.registry.target(1), tests.test_gar_config_context(1) |

## `environments.registry.target.esp32_esptool` (scripts/gar_lib/environments/registry/target/esp32_esptool.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32EsptoolEnvironment` | 17 | environments.registry.target(1), tests.test_gar_discovery(4) |

## `environments.registry.target.ssh_scp` (scripts/gar_lib/environments/registry/target/ssh_scp.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SshScpEnvironment` | 6 | environments.registry.target(1) |

## `environments.setup_option` (scripts/gar_lib/environments/setup_option.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DependencyStatus` | 10 | environments.installers.renode(3), environments.registry.simulator.mujoco(2), environments.registry.simulator.renode_mcu(1), environments.registry.simulator.wokwi(2), environments.registry.target.esp32_esptool(2) |
| `EnvironmentSetupOption` | 19 | commands.setup.command(3), commands.setup.environment_setup(1), environments.discovery(3), environments.registry(1), environments.registry.codespace(1), environments.registry.simulator(1), environments.registry.target(1), target.manifest(2), tests.support.gar_cli_test_support(6), tests.test_gar_config_context(1), tests.test_gar_discovery(1) |
| `DevelopmentEnvironmentSetupOption` | 62 | environments.registry.codespace.github_codespaces(1), environments.registry.codespace.local_docker(1), tests.test_gar_target_manifest(1) |
| `SimulationEnvironmentSetupOption` | 70 | environments.registry.simulator.aws_ssm(1), environments.registry.simulator.esp32_qemu(1), environments.registry.simulator.local_docker(1), environments.registry.simulator.mujoco(1), environments.registry.simulator.renode_mcu(1), environments.registry.simulator.ssh_remote(1), environments.registry.simulator.wokwi(1), tests.test_gar_target_manifest(1) |
| `TargetEnvironmentSetupOption` | 78 | environments.registry.target.adb_usb(1), environments.registry.target.adb_win(1), environments.registry.target.esp32_esptool(1), environments.registry.target.ssh_scp(1), tests.test_gar_target_manifest(1) |

## `simulation.composition` (scripts/gar_lib/simulation/composition.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LOCAL_DOCKER` | 49 | _(外部参照なし)_ |
| `EC2_HOST_SIMULATORS` | 50 | _(外部参照なし)_ |
| `HOSTLESS_SIMULATORS` | 51 | _(外部参照なし)_ |
| `selected_simulator` | 54 | _(外部参照なし)_ |
| `simulation_environment_for` | 58 | api(9), tests.test_gar_docker_simulation_host(1), tests.test_gar_pending_simulation_environments(2), tests.test_gar_simulation_host(1), tests.test_gar_wokwi_environment(1) |
| `simulation_host_for` | 99 | api(3), tests.test_gar_docker_simulation_host(5), tests.test_gar_simulation_host(3), tests.test_gar_wokwi_environment(1) |
| `hardware_control_for` | 144 | api(2), tests.test_gar_docker_simulation_host(1) |
| `docker_spec_for` | 171 | _(外部参照なし)_ |

## `simulation.diagnostics.model` (scripts/gar_lib/simulation/diagnostics/model.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationDiagnosticReport` | 13 | api(1), commands.sim(1), simulation.runtime.contract(1), simulation.runtime.pending(1) |
| `PayloadSimulationDiagnostic` | 21 | simulation.runtime.mujoco(2), simulation.runtime.wokwi(2) |
| `SimulationDiagnostic` | 34 | simulation.runtime.linux_systemd(2), tests.test_gar_sim_lifecycle(1) |

## `simulation.diagnostics.parse` (scripts/gar_lib/simulation/diagnostics/parse.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `parse_sim_diag` | 8 | simulation.diagnostics.model(1), tests.test_gar_sim_io(2) |
| `parse_gpio_runtime_status` | 62 | simulation.hardware.control(1), tests.test_gar_sim_io(1) |
| `parse_gpio_sim_check` | 111 | simulation.hardware.control(1), tests.test_gar_sim_io(1) |

## `simulation.hardware.control` (scripts/gar_lib/simulation/hardware/control.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HardwareControlResult` | 15 | api(12), commands.sim(1), simulation.hardware.mujoco(6) |
| `SimulationHardwareControl` | 22 | simulation.composition(1) |
| `LinuxBridgeHardwareControl` | 32 | simulation.composition(2), tests.test_gar_docker_simulation_host(1), tests.test_gar_hardware_control(5) |

## `simulation.hardware.io_actions` (scripts/gar_lib/simulation/hardware/io_actions.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `STATE_PATH` | 16 | scripts.run_scenario(1) |
| `DEFAULT_BUTTON_LINE` | 18 | _(外部参照なし)_ |
| `DEFAULT_PRESS_DURATION_MS` | 19 | _(外部参照なし)_ |
| `BUTTON_LINE_ALIASES` | 21 | _(外部参照なし)_ |
| `IO_ACTIONS` | 30 | scripts.run_scenario(2), tests.test_gar_sim_io(1) |
| `IO_DEVICES` | 31 | _(外部参照なし)_ |
| `IoRequest` | 35 | _(外部参照なし)_ |
| `resolve_button_line` | 43 | _(外部参照なし)_ |
| `resolve` | 53 | simulation.runtime.linux_commands(1), scripts.run_scenario(2), tests.test_gar_sim_io(1) |

## `simulation.hardware.mujoco` (scripts/gar_lib/simulation/hardware/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_BRIDGE_URL` | 12 | simulation.runtime.mujoco(1) |
| `MujocoBridgeHardwareControl` | 15 | simulation.composition(1) |
| `bridge_state` | 56 | simulation.runtime.mujoco(1) |

## `simulation.host.aws_ec2` (scripts/gar_lib/simulation/host/aws_ec2.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsEc2SimulationHostController` | 14 | simulation.composition(1), tests.test_gar_simulation_host(4) |

## `simulation.host.contract` (scripts/gar_lib/simulation/host/contract.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationHostState` | 11 | api(1), commands.sim(1), simulation.host.aws_ec2(2), simulation.host.docker(3), tests.test_gar_sim_lifecycle(1) |
| `SimulationHostStartResult` | 39 | api(1), commands.sim(1), simulation.host.aws_ec2(2), simulation.host.docker(2) |
| `SimulationHostController` | 46 | simulation.composition(1) |

## `simulation.host.docker` (scripts/gar_lib/simulation/host/docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `BACKEND_ID` | 17 | simulation.composition(1) |
| `DEFAULT_CONTAINER` | 19 | simulation.composition(1) |
| `DEFAULT_ADDRESS` | 20 | _(外部参照なし)_ |
| `ABSENT_STATE` | 22 | tests.test_gar_docker_simulation_host(1) |
| `SPEC_FINGERPRINT_LABEL` | 23 | _(外部参照なし)_ |
| `DockerPortBinding` | 27 | _(外部参照なし)_ |
| `DockerContainerInspection` | 39 | _(外部参照なし)_ |
| `DockerSimulationHostController` | 70 | simulation.composition(1), tests.test_gar_docker_simulation_host(7) |

## `simulation.host.docker_spec` (scripts/gar_lib/simulation/host/docker_spec.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_BRIDGE_PORT` | 13 | _(外部参照なし)_ |
| `DEFAULT_PUBLISHED_HOST` | 14 | _(外部参照なし)_ |
| `DockerHostSpec` | 20 | simulation.composition(3), simulation.host.docker(1), tests.test_gar_docker_simulation_host(4) |
| `docker_host_spec` | 55 | simulation.composition(1), tests.test_gar_docker_simulation_host(19) |

## `simulation.host.ssh_config` (scripts/gar_lib/simulation/host/ssh_config.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HostAddressUpdater` | 10 | simulation.host.aws_ec2(1) |
| `SshConfigHostAddressUpdater` | 14 | commands.infra(1), simulation.composition(1), tests.test_gar_sim_infra(2), tests.test_gar_simulation_host(1) |

## `simulation.runtime.aws_ssm` (scripts/gar_lib/simulation/runtime/aws_ssm.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsSsmSimulationEnvironment` | 9 | simulation.composition(1), tests.test_gar_pending_simulation_environments(1) |

## `simulation.runtime.contract` (scripts/gar_lib/simulation/runtime/contract.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationEnvironment` | 11 | simulation.composition(1) |

## `simulation.runtime.esp32_qemu` (scripts/gar_lib/simulation/runtime/esp32_qemu.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32QemuSimulationEnvironment` | 9 | simulation.composition(1), tests.test_gar_pending_simulation_environments(1) |

## `simulation.runtime.linux_commands` (scripts/gar_lib/simulation/runtime/linux_commands.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SIM_DIAG_DEVICES` | 16 | _(外部参照なし)_ |
| `GAR_ETC_DIR` | 17 | _(外部参照なし)_ |
| `GAR_HARDWARE_DIR` | 18 | _(外部参照なし)_ |
| `GAR_SBIN_DIR` | 19 | _(外部参照なし)_ |
| `GAR_LIB_DIR` | 20 | _(外部参照なし)_ |
| `GAR_RUN_DIR` | 21 | _(外部参照なし)_ |
| `GAR_HW_SIM_SOCK` | 22 | _(外部参照なし)_ |
| `GAR_BRIDGE_DIR` | 23 | _(外部参照なし)_ |
| `GAR_BRIDGE_START` | 24 | _(外部参照なし)_ |
| `GAR_GPIO_SIM_START` | 25 | _(外部参照なし)_ |
| `GAR_GPIO_SIM_STOP` | 26 | _(外部参照なし)_ |
| `GAR_CUSE_I2C` | 27 | _(外部参照なし)_ |
| `GAR_CUSE_SPI` | 28 | _(外部参照なし)_ |
| `GAR_V4L2_CAMERA_SERVICE` | 29 | _(外部参照なし)_ |
| `GAR_SIM_APP_SERVICE` | 30 | _(外部参照なし)_ |
| `PANEL_BASE_URL` | 31 | _(外部参照なし)_ |
| `CURL_OPTIONS` | 32 | _(外部参照なし)_ |
| `SIM_RUNTIME_PROCESS_PATTERN` | 33 | _(外部参照なし)_ |
| `SIM_GPIO_SIM_CHECK_COMMAND` | 35 | _(外部参照なし)_ |
| `gpio_sim_plan` | 237 | simulation.hardware.control(1), tests.test_gar_sim_io(1) |
| `LinuxSystemdCommandBuilder` | 266 | simulation.composition(4), simulation.hardware.control(1), simulation.runtime.linux_systemd(1), tests.test_gar_linux_systemd_environment(1), tests.test_gar_sim_io(9) |

## `simulation.runtime.linux_systemd` (scripts/gar_lib/simulation/runtime/linux_systemd.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LinuxSystemdSimulationEnvironment` | 17 | simulation.composition(2), tests.test_gar_docker_simulation_host(1), tests.test_gar_linux_systemd_environment(6) |

## `simulation.runtime.mujoco` (scripts/gar_lib/simulation/runtime/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_MODEL_PATH` | 25 | _(外部参照なし)_ |
| `DEFAULT_WORKSPACE_DIR` | 26 | _(外部参照なし)_ |
| `MujocoSimulationEnvironment` | 29 | simulation.composition(1), tests.test_gar_discovery(1), tests.test_gar_mujoco_environment(2) |

## `simulation.runtime.pending` (scripts/gar_lib/simulation/runtime/pending.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `PendingSimulationEnvironment` | 12 | simulation.runtime.aws_ssm(1), simulation.runtime.esp32_qemu(1), simulation.runtime.renode(1) |

## `simulation.runtime.process` (scripts/gar_lib/simulation/runtime/process.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ManagedProcess` | 20 | simulation.runtime.mujoco(3), simulation.runtime.wokwi(3), tests.test_gar_discovery(1), tests.test_gar_simulation_process(3), tests.test_gar_wokwi_environment(2) |
| `ProcessChannel` | 50 | simulation.runtime.esp32_qemu(1), simulation.runtime.mujoco(1), simulation.runtime.renode(1), simulation.runtime.wokwi(1) |
| `ProcessStateStore` | 67 | simulation.runtime.mujoco(1), simulation.runtime.wokwi(1), tests.test_gar_simulation_process(2) |
| `LocalProcessChannel` | 112 | simulation.composition(4), simulation.runtime.mujoco(1), tests.test_gar_simulation_process(4) |

## `simulation.runtime.renode` (scripts/gar_lib/simulation/runtime/renode.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RenodeSimulationEnvironment` | 9 | simulation.composition(1), tests.test_gar_pending_simulation_environments(1) |

## `simulation.runtime.wokwi` (scripts/gar_lib/simulation/runtime/wokwi.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_TIMEOUT_MS` | 20 | _(外部参照なし)_ |
| `WokwiSimulationEnvironment` | 23 | simulation.composition(1), tests.test_gar_wokwi_environment(9) |

## `simulation.session.manager` (scripts/gar_lib/simulation/session/manager.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationSessionManager` | 15 | _(外部参照なし)_ |
| `VsCodeSimulationSessionManager` | 31 | api(3) |

## `simulation.session.remote` (scripts/gar_lib/simulation/session/remote.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `start_sim_port_forward` | 14 | simulation.session.manager(1) |
| `stop_sim_port_forward` | 18 | simulation.session.manager(1) |
| `status_sim_port_forward` | 22 | simulation.session.manager(1) |
| `write_sim_terminal_profile` | 34 | simulation.session.manager(1) |
| `sim_terminal_script` | 61 | _(外部参照なし)_ |

## `target.composition` (scripts/gar_lib/target/composition.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `target_environment_for` | 18 | api(1), tests.test_gar_target_architecture(3) |

## `target.environment` (scripts/gar_lib/target/environment.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TargetEnvironment` | 10 | target.composition(1), target.file_transfer(1) |

## `target.esp32` (scripts/gar_lib/target/esp32.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32TargetEnvironment` | 14 | target.composition(1), tests.test_gar_target_architecture(2) |

## `target.esp32_firmware` (scripts/gar_lib/target/esp32_firmware.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `FLASH_LAYOUT` | 7 | target.esp32(1), target.esptool(2) |
| `resolve_esp32_artifact_dir` | 15 | target.esptool(1) |

## `target.esptool` (scripts/gar_lib/target/esptool.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ESPTOOL_VENV` | 20 | _(外部参照なし)_ |
| `normalize_esp32_serial_port` | 23 | tests.test_gar_target_cli(2) |
| `validate_esp32_artifact` | 35 | _(外部参照なし)_ |
| `esp32_serial_port_access_error` | 49 | _(外部参照なし)_ |
| `esp32_serial_failure_hint` | 80 | _(外部参照なし)_ |
| `verify_esp32_artifact_checksums` | 93 | _(外部参照なし)_ |
| `ensure_esptool_python` | 131 | _(外部参照なし)_ |
| `run_esp32_flash_command` | 153 | target.esp32(1), tests.test_gar_target_cli(3) |

## `target.file_transfer` (scripts/gar_lib/target/file_transfer.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `FileTransferTargetEnvironment` | 19 | target.composition(3), tests.test_gar_target_architecture(1) |

## `target.manifest` (scripts/gar_lib/target/manifest.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TargetManifest` | 18 | commands.setup.command(4), commands.setup.target_setup(12), tests.test_gar_docker_simulation_host(3), tests.test_gar_setup_config(15) |
| `TargetManifestValidationIssue` | 32 | tests.test_gar_target_manifest(2) |
| `TargetManifestValidationError` | 44 | commands.setup.command(1), tests.test_gar_target_manifest(3) |
| `discover_target_manifests` | 51 | commands.setup.command(1), simulation.composition(1), tests.test_gar_setup_config(2), tests.test_gar_target_manifest(3) |
| `target_by_id` | 90 | commands.setup.target_setup(1), simulation.composition(1) |

## `vscode.profile_manage` (scripts/gar_lib/vscode/profile_manage.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `write_vscode_terminal_profile` | 10 | commands.code(1), simulation.session.remote(1) |
| `remove_vscode_terminal_profile` | 25 | commands.code(1) |

## `vscode.terminal_bridge` (scripts/gar_lib/vscode/terminal_bridge.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `installed_vscode_terminal_bridge_path` | 15 | commands.setup.command(1) |
| `install_vscode_terminal_bridge` | 29 | commands.setup.command(1) |

## `vscode.terminal_requests` (scripts/gar_lib/vscode/terminal_requests.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `MAX_COMMAND_LENGTH` | 20 | _(外部参照なし)_ |
| `MAX_TITLE_LENGTH` | 21 | _(外部参照なし)_ |
| `SAFE_REQUEST_ID` | 22 | _(外部参照なし)_ |
| `TerminalRequest` | 26 | _(外部参照なし)_ |
| `TerminalRequestStore` | 84 | commands.terminal(1), environments.install(1), tests.test_gar_terminal_requests(3) |

## `vscode.terminal_ui` (scripts/gar_lib/vscode/terminal_ui.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RESET` | 8 | _(外部参照なし)_ |
| `BOLD` | 9 | commands.setup.command(7), commands.setup.environment_setup(17), commands.setup.target_setup(23), commands.setup.workspace_setup(2) |
| `DIM` | 10 | commands.setup.command(7), commands.setup.environment_setup(6), commands.setup.target_setup(15), commands.setup.workspace_setup(2) |
| `GREEN` | 11 | commands.setup.command(5), commands.setup.environment_setup(6), commands.setup.target_setup(8), commands.setup.workspace_setup(5) |
| `YELLOW` | 12 | commands.setup.command(4), commands.setup.environment_setup(11), commands.setup.target_setup(7), commands.setup.workspace_setup(7) |
| `RED` | 13 | commands.setup.command(4), commands.setup.environment_setup(3), commands.setup.workspace_setup(5) |
| `CYAN` | 14 | commands.setup.command(1), commands.setup.environment_setup(3), commands.setup.target_setup(2) |
| `BLUE` | 15 | commands.setup.command(2), commands.setup.environment_setup(3), commands.setup.target_setup(6), commands.setup.workspace_setup(1) |
| `style` | 22 | commands.setup.command(23), commands.setup.environment_setup(39), commands.setup.target_setup(50), commands.setup.workspace_setup(21) |
| `safe_input` | 28 | commands.setup.command(1), commands.setup.environment_setup(5), commands.setup.target_setup(4), commands.setup.workspace_setup(12) |

## 外部未参照の公開メンバ一覧

同一module内でしか使われていない (または全く未使用の) 公開メンバ。 private化 (`_`prefix) や整理の候補。

| module | メンバ | 行 |
|---|---|---:|
| `access.channel` | `ConsoleChannel` | 37 |
| `access.docker` | `CONTAINER_FAILURE_MARKERS` | 20 |
| `access.docker` | `DAEMON_FAILURE_MARKERS` | 13 |
| `access.docker` | `connection_reason` | 35 |
| `access.docker` | `docker_executable` | 28 |
| `access.ssh` | `SSH_CONNECTION_OPTIONS` | 11 |
| `api` | `Simulation` | 32 |
| `api` | `SimulationApp` | 43 |
| `api` | `SimulationGpio` | 148 |
| `api` | `SimulationHost` | 126 |
| `api` | `SimulationIo` | 177 |
| `api` | `SimulationRuntime` | 61 |
| `api` | `Target` | 202 |
| `artifacts.manifest` | `ArtifactManifest` | 69 |
| `artifacts.manifest` | `ArtifactManifestError` | 30 |
| `artifacts.manifest` | `DEFAULT_CODESPACE_ARTIFACT_ROOT` | 27 |
| `artifacts.manifest` | `DeployFile` | 35 |
| `artifacts.manifest` | `DeploySection` | 50 |
| `artifacts.manifest` | `artifact_deploy_files` | 316 |
| `artifacts.manifest` | `artifact_manifest_deploy_sources` | 187 |
| `artifacts.manifest` | `default_artifacts_dir` | 151 |
| `artifacts.manifest` | `default_codespace_artifact_root` | 155 |
| `artifacts.manifest` | `find_artifact_manifest` | 284 |
| `artifacts.manifest` | `gh_codespace_cp` | 270 |
| `artifacts.manifest` | `gh_env` | 181 |
| `artifacts.manifest` | `load_artifact_manifest` | 295 |
| `artifacts.manifest` | `select_codespace` | 159 |
| `artifacts.store` | `ArtifactStore` | 21 |
| `build.environment` | `BuildEnvironment` | 15 |
| `build.spec` | `BuildSpec` | 18 |
| `build.spec` | `DEFAULT_REMOTE_SIM_ARCH` | 14 |
| `build.spec` | `compiler_for_architecture` | 23 |
| `build.spec` | `simulation_build_variables` | 31 |
| `cli` | `CliParserBundle` | 20 |
| `cli` | `enable_argcomplete` | 38 |
| `cli` | `run_cli_command` | 71 |
| `commands.code` | `CodeStartOptions` | 44 |
| `commands.code` | `DEFAULT_CODESPACE_REMOTE_PATH` | 40 |
| `commands.code` | `boot_code_codespace` | 246 |
| `commands.code` | `configure_codespace_ssh` | 458 |
| `commands.code` | `configure_vscode_codespace` | 508 |
| `commands.code` | `default_codespaces_mount_dir` | 731 |
| `commands.code` | `load_codespace_state` | 725 |
| `commands.code` | `report_codespace_start` | 521 |
| `commands.code` | `resolve_code_start_options` | 380 |
| `commands.code` | `resolve_codespace_remote_path` | 488 |
| `commands.code` | `run_local_code_command` | 229 |
| `commands.code` | `select_code_codespace` | 690 |
| `commands.code` | `status_code_codespace` | 637 |
| `commands.code` | `validate_code_start_options` | 426 |
| `commands.code_connection` | `DEFAULT_GH_TIMEOUT_SECONDS` | 13 |
| `commands.code_connection` | `SSH_CONFIG_INCLUDE` | 14 |
| `commands.code_connection` | `run_codespace_remote` | 137 |
| `commands.completion` | `completion_bash_script` | 42 |
| `commands.completion` | `parser_completion_words` | 56 |
| `commands.hw` | `run_hw_command` | 53 |
| `commands.infra` | `TERRAFORM_DIR` | 26 |
| `commands.recovery` | `RecoveryAction` | 16 |
| `commands.setup.command` | `add_setup_parser` | 64 |
| `commands.setup.command` | `clear_setup_screen` | 384 |
| `commands.setup.command` | `ensure_gar_tools_for_setup` | 371 |
| `commands.setup.command` | `print_terminal_bridge_status` | 390 |
| `commands.setup.command` | `run_setup` | 97 |
| `commands.setup.command` | `run_setup_cli` | 89 |
| `commands.setup.environment_setup` | `EnvironmentCategory` | 33 |
| `commands.setup.environment_setup` | `EnvironmentSelection` | 53 |
| `commands.setup.environment_setup` | `environment_by_id` | 424 |
| `commands.setup.environment_setup` | `first_unconfigured_category_index` | 370 |
| `commands.setup.environment_setup` | `grouped_environments` | 401 |
| `commands.setup.target_setup` | `detect_esp32_serial_port_candidates` | 273 |
| `commands.setup.target_setup` | `ensure_selected_target_ready` | 56 |
| `commands.setup.target_setup` | `managed_backend_categories` | 74 |
| `commands.setup.target_setup` | `print_selected_target_summary` | 126 |
| `commands.setup.target_setup` | `print_target_summary` | 113 |
| `commands.setup.target_setup` | `prune_removed_target_backends` | 63 |
| `commands.setup.target_setup` | `removable_target_backend_categories` | 70 |
| `commands.setup.workspace_setup` | `default_workspace_name` | 190 |
| `commands.setup.workspace_setup` | `default_workspace_product_name` | 201 |
| `commands.setup.workspace_setup` | `print_codespace_candidates` | 327 |
| `commands.setup.workspace_setup` | `print_workspace_entry` | 157 |
| `commands.setup.workspace_setup` | `probe_git_workspace` | 342 |
| `commands.setup.workspace_setup` | `prompt_workspace_entry` | 209 |
| `commands.setup.workspace_setup` | `workspace_duplicate` | 168 |
| `commands.sim` | `SIM_ACTIONS` | 28 |
| `commands.target` | `TARGET_ACTIONS` | 17 |
| `commands.usb` | `ANDROID_HINTS` | 32 |
| `commands.usb` | `ANDROID_VIDS` | 34 |
| `commands.usb` | `UsbDevice` | 92 |
| `commands.usb` | `UsbipdCommandError` | 118 |
| `commands.usb` | `list_usb_devices` | 297 |
| `core.command` | `SIM_RUNTIME_LOG` | 36 |
| `core.command` | `SIM_RUNTIME_STATUS` | 35 |
| `core.command` | `SIM_RUNTIME_STOP` | 34 |
| `core.config` | `DEFAULT_EC2_INSTANCE_ID` | 22 |
| `core.config` | `DEFAULT_EC2_REGION` | 23 |
| `core.config` | `RUNTIME_HOST_PATTERN` | 24 |
| `core.config` | `ec2_repo_dir` | 330 |
| `core.hardware` | `DEFAULT_HW_TARGET` | 47 |
| `core.hardware` | `HW_DIR` | 46 |
| `core.hardware` | `TARGET_ID_PATTERN` | 48 |
| `core.tools_repository` | `DEFAULT_GAR_TOOLS_REPO` | 11 |
| `core.tools_repository` | `find_gar_tools_root` | 21 |
| `core.tools_repository` | `gar_tools_root_candidates` | 28 |
| `core.workspace_settings` | `SettingsMapping` | 10 |
| `environments.discovery` | `EnvironmentDiscoveryError` | 7 |
| `environments.docker_install` | `DOCKER_INSTALL_COMMANDS` | 12 |
| `environments.docker_install` | `GROUP_REFRESH_NOTE` | 20 |
| `environments.docker_install` | `is_wsl_or_linux` | 23 |
| `environments.install` | `create_visible_terminal_request` | 59 |
| `environments.installers.renode` | `BIN_DIR` | 36 |
| `environments.installers.renode` | `INSTALL_ROOT` | 34 |
| `environments.installers.renode` | `LAUNCHER` | 37 |
| `environments.installers.renode` | `RENODE_DOCS` | 32 |
| `environments.installers.renode` | `RENODE_RELEASES_API` | 30 |
| `environments.installers.renode` | `RENODE_RELEASES_PAGE` | 31 |
| `environments.installers.renode` | `TEST_LAUNCHER` | 38 |
| `environments.installers.renode` | `TEST_VENV` | 35 |
| `environments.registry.target.adb_win` | `WINGET_PACKAGE_ID` | 26 |
| `simulation.composition` | `EC2_HOST_SIMULATORS` | 50 |
| `simulation.composition` | `HOSTLESS_SIMULATORS` | 51 |
| `simulation.composition` | `LOCAL_DOCKER` | 49 |
| `simulation.composition` | `docker_spec_for` | 171 |
| `simulation.composition` | `selected_simulator` | 54 |
| `simulation.hardware.io_actions` | `BUTTON_LINE_ALIASES` | 21 |
| `simulation.hardware.io_actions` | `DEFAULT_BUTTON_LINE` | 18 |
| `simulation.hardware.io_actions` | `DEFAULT_PRESS_DURATION_MS` | 19 |
| `simulation.hardware.io_actions` | `IO_DEVICES` | 31 |
| `simulation.hardware.io_actions` | `IoRequest` | 35 |
| `simulation.hardware.io_actions` | `resolve_button_line` | 43 |
| `simulation.host.docker` | `DEFAULT_ADDRESS` | 20 |
| `simulation.host.docker` | `DockerContainerInspection` | 39 |
| `simulation.host.docker` | `DockerPortBinding` | 27 |
| `simulation.host.docker` | `SPEC_FINGERPRINT_LABEL` | 23 |
| `simulation.host.docker_spec` | `DEFAULT_BRIDGE_PORT` | 13 |
| `simulation.host.docker_spec` | `DEFAULT_PUBLISHED_HOST` | 14 |
| `simulation.runtime.linux_commands` | `CURL_OPTIONS` | 32 |
| `simulation.runtime.linux_commands` | `GAR_BRIDGE_DIR` | 23 |
| `simulation.runtime.linux_commands` | `GAR_BRIDGE_START` | 24 |
| `simulation.runtime.linux_commands` | `GAR_CUSE_I2C` | 27 |
| `simulation.runtime.linux_commands` | `GAR_CUSE_SPI` | 28 |
| `simulation.runtime.linux_commands` | `GAR_ETC_DIR` | 17 |
| `simulation.runtime.linux_commands` | `GAR_GPIO_SIM_START` | 25 |
| `simulation.runtime.linux_commands` | `GAR_GPIO_SIM_STOP` | 26 |
| `simulation.runtime.linux_commands` | `GAR_HARDWARE_DIR` | 18 |
| `simulation.runtime.linux_commands` | `GAR_HW_SIM_SOCK` | 22 |
| `simulation.runtime.linux_commands` | `GAR_LIB_DIR` | 20 |
| `simulation.runtime.linux_commands` | `GAR_RUN_DIR` | 21 |
| `simulation.runtime.linux_commands` | `GAR_SBIN_DIR` | 19 |
| `simulation.runtime.linux_commands` | `GAR_SIM_APP_SERVICE` | 30 |
| `simulation.runtime.linux_commands` | `GAR_V4L2_CAMERA_SERVICE` | 29 |
| `simulation.runtime.linux_commands` | `PANEL_BASE_URL` | 31 |
| `simulation.runtime.linux_commands` | `SIM_DIAG_DEVICES` | 16 |
| `simulation.runtime.linux_commands` | `SIM_GPIO_SIM_CHECK_COMMAND` | 35 |
| `simulation.runtime.linux_commands` | `SIM_RUNTIME_PROCESS_PATTERN` | 33 |
| `simulation.runtime.mujoco` | `DEFAULT_MODEL_PATH` | 25 |
| `simulation.runtime.mujoco` | `DEFAULT_WORKSPACE_DIR` | 26 |
| `simulation.runtime.wokwi` | `DEFAULT_TIMEOUT_MS` | 20 |
| `simulation.session.manager` | `SimulationSessionManager` | 15 |
| `simulation.session.remote` | `sim_terminal_script` | 61 |
| `target.esptool` | `ESPTOOL_VENV` | 20 |
| `target.esptool` | `ensure_esptool_python` | 131 |
| `target.esptool` | `esp32_serial_failure_hint` | 80 |
| `target.esptool` | `esp32_serial_port_access_error` | 49 |
| `target.esptool` | `validate_esp32_artifact` | 35 |
| `target.esptool` | `verify_esp32_artifact_checksums` | 93 |
| `vscode.terminal_requests` | `MAX_COMMAND_LENGTH` | 20 |
| `vscode.terminal_requests` | `MAX_TITLE_LENGTH` | 21 |
| `vscode.terminal_requests` | `SAFE_REQUEST_ID` | 22 |
| `vscode.terminal_requests` | `TerminalRequest` | 26 |
| `vscode.terminal_ui` | `RESET` | 8 |

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
| `AccessResult` | 13 | access.adb(4), access.aws(2), access.docker(6), access.ssh(4), simulation.diagnostics.model(1), simulation.hardware.control(1), simulation.host.aws_ec2(1), tests.test_gar_docker_simulation_host(16), tests.test_gar_hardware_control(3), tests.test_gar_linux_systemd_environment(5), tests.test_gar_simulation_host(6) |
| `ConsoleSession` | 23 | access.serial(2) |
| `CommandChannel` | 27 | simulation.hardware.control(1), simulation.host.aws_ec2(1), simulation.host.docker(1), simulation.runtime.linux_systemd(1), target.file_transfer(1) |
| `FileChannel` | 31 | simulation.runtime.linux_systemd(1), target.file_transfer(1) |
| `ConsoleChannel` | 37 | _(外部参照なし)_ |
| `run_cli` | 44 | access.adb(2), access.aws(1), access.docker(3), access.ssh(2) |

## `access.codespaces` (scripts/gar_lib/access/codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `select_codespace_from_list` | 6 | artifacts.manifest(1), commands.code(3), tests.test_gar_access_codespaces(2) |
| `codespace_list_rows` | 17 | commands.code(1), tests.test_gar_access_codespaces(1) |

## `access.docker` (scripts/gar_lib/access/docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DAEMON_FAILURE_MARKERS` | 13 | _(外部参照なし)_ |
| `CONTAINER_FAILURE_MARKERS` | 20 | _(外部参照なし)_ |
| `docker_executable` | 28 | _(外部参照なし)_ |
| `connection_reason` | 37 | _(外部参照なし)_ |
| `DockerCliCommandChannel` | 46 | simulation.host.docker(1) |
| `DockerCliChannel` | 50 | simulation.composition(1), tests.test_gar_docker_simulation_host(2) |
| `DockerCommandChannel` | 66 | simulation.composition(3), tests.test_gar_docker_simulation_host(4) |
| `DockerFileChannel` | 95 | simulation.composition(1), tests.test_gar_docker_simulation_host(2) |

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
| `Gar` | 22 | commands.sim(1), commands.target(1), tests.test_gar_sim_architecture(4), tests.test_gar_sim_lifecycle(5), tests.test_gar_target_architecture(2) |
| `Simulation` | 29 | _(外部参照なし)_ |
| `SimulationApp` | 40 | _(外部参照なし)_ |
| `SimulationRuntime` | 65 | _(外部参照なし)_ |
| `SimulationHost` | 138 | _(外部参照なし)_ |
| `SimulationGpio` | 182 | _(外部参照なし)_ |
| `SimulationIo` | 210 | _(外部参照なし)_ |
| `Target` | 255 | _(外部参照なし)_ |

## `artifacts.manifest` (scripts/gar_lib/artifacts/manifest.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_CODESPACE_ARTIFACT_ROOT` | 25 | _(外部参照なし)_ |
| `default_artifacts_dir` | 28 | _(外部参照なし)_ |
| `default_codespace_artifact_root` | 32 | _(外部参照なし)_ |
| `select_codespace` | 36 | _(外部参照なし)_ |
| `gh_env` | 58 | target.esp32_firmware(2) |
| `artifact_manifest_deploy_sources` | 64 | _(外部参照なし)_ |
| `fetch_codespace_artifacts` | 87 | artifacts.store(1), tests.test_gar_cli(1) |
| `gh_codespace_cp` | 158 | _(外部参照なし)_ |
| `find_artifact_manifest` | 172 | _(外部参照なし)_ |
| `load_artifact_manifest` | 183 | _(外部参照なし)_ |
| `artifact_deploy_files` | 202 | _(外部参照なし)_ |
| `resolve_artifact_src` | 240 | simulation.runtime.linux_systemd(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1) |
| `load_deploy_files` | 255 | artifacts.store(1), simulation.runtime.linux_systemd(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1) |
| `target_dest_path` | 268 | target.file_transfer(1) |

## `artifacts.store` (scripts/gar_lib/artifacts/store.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ArtifactStore` | 15 | api(5), build.environment(1), build.local(1) |
| `LocalArtifactStore` | 19 | api(1), build.codespaces(1), build.esp32(1), tests.test_gar_sim_architecture(2), tests.test_gar_target_architecture(1) |

## `build.codespaces` (scripts/gar_lib/build/codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `CodespacesBuildEnvironment` | 16 | build.environment(1), tests.test_gar_build_variables(1), tests.test_gar_sim_architecture(1) |

## `build.environment` (scripts/gar_lib/build/environment.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `BuildEnvironment` | 16 | _(外部参照なし)_ |
| `build_environment_for` | 24 | api(5) |

## `build.esp32` (scripts/gar_lib/build/esp32.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32BuildEnvironment` | 33 | build.environment(1) |

## `build.local` (scripts/gar_lib/build/local.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalBuildEnvironment` | 15 | build.environment(1), tests.test_gar_build_variables(1), tests.test_gar_sim_architecture(1), tests.test_gar_target_architecture(1) |

## `build.spec` (scripts/gar_lib/build/spec.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_REMOTE_SIM_ARCH` | 14 | _(外部参照なし)_ |
| `BuildSpec` | 18 | _(外部参照なし)_ |
| `compiler_for_architecture` | 23 | _(外部参照なし)_ |
| `simulation_build_variables` | 31 | _(外部参照なし)_ |
| `ProductBuildSpecResolver` | 51 | build.codespaces(2), build.local(2), tests.test_gar_build_variables(1) |

## `cli` (scripts/gar_lib/cli.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `CODE_COMMAND_MAP` | 29 | _(外部参照なし)_ |
| `normalize_question_help` | 38 | tests.test_gar_cli(2) |
| `completion_bash_script` | 49 | tests.test_gar_cli(1) |
| `enable_argcomplete` | 63 | _(外部参照なし)_ |
| `parser_completion_words` | 85 | _(外部参照なし)_ |
| `add_code_start_arguments` | 115 | _(外部参照なし)_ |
| `build_parser` | 135 | tests.test_gar_cli(1) |
| `main` | 342 | scripts.gar(entrypoint)(1), __main__(1), tests.test_gar_cli(21), tests.test_gar_sim_lifecycle(1), tests.test_gar_target_architecture(1) |

## `commands.code` (scripts/gar_lib/commands/code.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_GH_TIMEOUT_SECONDS` | 19 | _(外部参照なし)_ |
| `DEFAULT_CODESPACE_REMOTE_PATH` | 20 | _(外部参照なし)_ |
| `run_code_command` | 23 | cli(1), tests.test_gar_cli(2) |
| `run_local_code_command` | 86 | _(外部参照なし)_ |
| `boot_code_codespace` | 102 | _(外部参照なし)_ |
| `start_code_codespace` | 140 | tests.test_gar_cli(4) |
| `stop_code_codespace` | 288 | tests.test_gar_cli(2) |
| `shutdown_code_codespace` | 344 | tests.test_gar_cli(1) |
| `status_code_codespace` | 392 | _(外部参照なし)_ |
| `select_code_codespace` | 446 | _(外部参照なし)_ |
| `load_codespace_state` | 481 | _(外部参照なし)_ |
| `default_codespaces_mount_dir` | 501 | _(外部参照なし)_ |
| `gh_timeout_seconds` | 505 | _(外部参照なし)_ |
| `run_gh_captured` | 521 | _(外部参照なし)_ |
| `print_completed_stderr` | 549 | _(外部参照なし)_ |
| `first_ssh_host` | 555 | _(外部参照なし)_ |
| `remote_path_exists` | 563 | _(外部参照なし)_ |
| `detect_codespace_workspace` | 572 | _(外部参照なし)_ |
| `run_codespace_remote` | 584 | _(外部参照なし)_ |
| `mount_codespace_code` | 598 | _(外部参照なし)_ |
| `unmount_codespace_code` | 646 | _(外部参照なし)_ |
| `codespace_terminal_script` | 695 | _(外部参照なし)_ |

## `commands.hw` (scripts/gar_lib/commands/hw.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `run_hw_command` | 8 | cli(1) |

## `commands.infra` (scripts/gar_lib/commands/infra.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TERRAFORM_DIR` | 24 | _(外部参照なし)_ |
| `run_sim_infra_command` | 111 | commands.sim(1), tests.test_gar_cli(2) |

## `commands.recovery` (scripts/gar_lib/commands/recovery.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RecoveryAction` | 16 | _(外部参照なし)_ |
| `report_access_failure` | 22 | commands.sim(1), commands.target(1), tests.test_gar_access_recovery(1) |
| `plan_access_recovery` | 53 | tests.test_gar_access_recovery(3) |

## `commands.setup` (scripts/gar_lib/commands/setup.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SKIP_CATEGORY` | 51 | _(外部参照なし)_ |
| `TARGET_MENU_ENTRY` | 52 | _(外部参照なし)_ |
| `run_setup` | 55 | cli(1), tests.test_gar_cli(13) |
| `ensure_gar_tools_for_setup` | 166 | _(外部参照なし)_ |
| `clear_setup_screen` | 176 | _(外部参照なし)_ |
| `print_terminal_bridge_status` | 182 | _(外部参照なし)_ |
| `configure_default_ec2_host` | 211 | tests.test_gar_cli(2) |
| `configure_esp32_serial_port` | 251 | _(外部参照なし)_ |
| `configure_target_connection` | 296 | tests.test_gar_target_architecture(1) |
| `configure_workspace_root` | 339 | _(外部参照なし)_ |
| `print_workspace_entry` | 435 | _(外部参照なし)_ |
| `workspace_duplicate` | 447 | _(外部参照なし)_ |
| `default_workspace_name` | 469 | tests.test_gar_cli(3) |
| `default_workspace_product_name` | 475 | tests.test_gar_cli(2) |
| `prompt_workspace_entry` | 482 | _(外部参照なし)_ |
| `print_codespace_candidates` | 562 | _(外部参照なし)_ |
| `probe_git_workspace` | 572 | _(外部参照なし)_ |
| `detect_esp32_serial_port_candidates` | 594 | _(外部参照なし)_ |
| `print_target_next_steps` | 604 | _(外部参照なし)_ |
| `configure_target` | 622 | _(外部参照なし)_ |
| `save_selected_target` | 646 | _(外部参照なし)_ |
| `ensure_selected_target_ready` | 653 | _(外部参照なし)_ |
| `prune_removed_target_backends` | 660 | _(外部参照なし)_ |
| `removable_target_backend_categories` | 666 | _(外部参照なし)_ |
| `managed_backend_categories` | 674 | _(外部参照なし)_ |
| `prepare_target_backend` | 685 | _(外部参照なし)_ |
| `select_target` | 694 | _(外部参照なし)_ |
| `print_target_summary` | 713 | _(外部参照なし)_ |
| `print_selected_target_summary` | 730 | _(外部参照なし)_ |
| `selected_target_manifest` | 744 | _(外部参照なし)_ |
| `optional_setup_categories` | 748 | _(外部参照なし)_ |
| `ensure_environment_dependencies` | 778 | tests.test_gar_cli(1) |
| `print_environment_overview` | 831 | _(外部参照なし)_ |
| `select_setup_category` | 871 | _(外部参照なし)_ |
| `select_environment_for_category` | 924 | _(外部参照なし)_ |
| `unconfigured_categories` | 977 | _(外部参照なし)_ |
| `first_unconfigured_category_index` | 1000 | tests.test_gar_cli(1) |
| `grouped_environments` | 1026 | _(外部参照なし)_ |
| `environment_by_id` | 1040 | _(外部参照なし)_ |

## `commands.sim` (scripts/gar_lib/commands/sim.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `IO_PARAMETERS` | 18 | _(外部参照なし)_ |
| `SIM_ACTIONS` | 22 | _(外部参照なし)_ |
| `add_sim_parser` | 122 | cli(1) |
| `run_sim_command` | 286 | cli(1) |

## `commands.target` (scripts/gar_lib/commands/target.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TARGET_ACTIONS` | 17 | _(外部参照なし)_ |
| `add_target_parser` | 24 | cli(1) |
| `run_target_command` | 52 | cli(1) |

## `commands.terminal` (scripts/gar_lib/commands/terminal.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `run_terminal_run_command` | 15 | cli(1), commands.sim(1), commands.target(1), tests.test_gar_cli(1) |
| `run_terminal_gc_command` | 51 | cli(1), tests.test_gar_cli(1) |

## `commands.usb` (scripts/gar_lib/commands/usb.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ANDROID_HINTS` | 30 | _(外部参照なし)_ |
| `ANDROID_VIDS` | 32 | _(外部参照なし)_ |
| `UsbDevice` | 36 | _(外部参照なし)_ |
| `parse_usbipd_list` | 184 | tests.test_gar_cli(6) |
| `list_usb_devices` | 235 | _(外部参照なし)_ |
| `run_usb_command` | 243 | cli(1), tests.test_gar_cli(5) |

## `commands.workspace_resolver` (scripts/gar_lib/commands/workspace_resolver.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `resolve_workspace` | 46 | commands.sim(1), commands.target(1), tests.test_gar_cli(1), tests.test_gar_sim_architecture(2) |

## `core.artifact` (scripts/gar_lib/core/artifact.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ArtifactKind` | 12 | api(7), artifacts.store(5), build.codespaces(2), build.environment(2), build.esp32(4), build.local(2), build.spec(6), simulation.runtime.linux_systemd(2), simulation.runtime.mujoco(1), simulation.runtime.wokwi(1), target.esp32(1), target.file_transfer(1), tests.test_gar_build_variables(8), tests.test_gar_linux_systemd_environment(1), tests.test_gar_pending_simulation_environments(1), tests.test_gar_sim_architecture(6), tests.test_gar_target_architecture(7), tests.test_gar_wokwi_environment(2) |
| `Artifact` | 19 | artifacts.store(3), build.codespaces(1), build.environment(1), build.esp32(2), build.local(1), simulation.runtime.contract(1), simulation.runtime.linux_systemd(1), simulation.runtime.mujoco(1), simulation.runtime.pending(1), simulation.runtime.wokwi(1), target.environment(1), target.esp32(2), target.file_transfer(1), tests.test_gar_linux_systemd_environment(1), tests.test_gar_pending_simulation_environments(1), tests.test_gar_target_architecture(2), tests.test_gar_wokwi_environment(2) |

## `core.command` (scripts/gar_lib/core/command.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GarCommand` | 10 | commands.sim(3), commands.target(2), tests.test_gar_cli(4) |
| `SIM_APP_BUILD` | 28 | tests.test_gar_cli(3) |
| `SIM_APP_CLEAN` | 29 | tests.test_gar_cli(1) |
| `SIM_APP_DEPLOY` | 30 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_BUILD` | 31 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_DEPLOY` | 32 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_START` | 33 | tests.test_gar_cli(1) |
| `SIM_RUNTIME_STOP` | 34 | _(外部参照なし)_ |
| `SIM_RUNTIME_STATUS` | 35 | _(外部参照なし)_ |
| `SIM_RUNTIME_LOG` | 36 | _(外部参照なし)_ |
| `SIM_RUNTIME_DIAG` | 37 | tests.test_gar_cli(1) |
| `SIM_HOST_START` | 38 | tests.test_gar_cli(2) |
| `SIM_HOST_STOP` | 39 | tests.test_gar_cli(1) |
| `SIM_HOST_STATUS` | 40 | tests.test_gar_cli(2) |
| `TARGET_BUILD` | 41 | tests.test_gar_cli(1) |
| `TARGET_DEPLOY` | 42 | tests.test_gar_cli(1) |
| `TARGET_FETCH` | 43 | tests.test_gar_cli(1) |

## `core.config` (scripts/gar_lib/core/config.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `PROJECT_ROOT` | 13 | artifacts.manifest(1), artifacts.store(1), commands.infra(1), core.hardware(1), core.tools_repository(5), environments.registry.target.esp32_esptool(2), simulation.composition(1), simulation.runtime.mujoco(4), simulation.session.remote(1), target.esp32_firmware(1), vscode.terminal_bridge(1), tests.test_gar_cli(3) |
| `CONFIG_PATH` | 17 | commands.terminal(2) |
| `VSCODE_EXT_NAME` | 19 | vscode.terminal_bridge(3) |
| `VSCODE_EXT_VERSION` | 20 | vscode.terminal_bridge(2) |
| `DEFAULT_EC2_HOST` | 22 | _(外部参照なし)_ |
| `DEFAULT_EC2_INSTANCE_ID` | 23 | _(外部参照なし)_ |
| `DEFAULT_EC2_REGION` | 24 | _(外部参照なし)_ |
| `RUNTIME_HOST_PATTERN` | 26 | _(外部参照なし)_ |
| `is_valid_runtime_host` | 29 | commands.setup(1) |
| `set_active_workspace_root` | 33 | commands.setup(1) |
| `load_config` | 111 | commands.code(1), commands.infra(2), commands.setup(2), commands.usb(1), commands.workspace_resolver(1), environments.registry.target.adb_win(1), target.esptool(1), target.manifest(1), tests.test_gar_cli(5) |
| `save_config` | 234 | commands.infra(1), commands.setup(11), commands.usb(1), environments.registry.target.adb_win(1), tests.test_gar_cli(10) |
| `default_config` | 289 | tests.test_gar_cli(2) |
| `default_ec2_host` | 299 | commands.infra(2), commands.setup(1) |
| `default_ec2_instance_id` | 306 | commands.infra(1) |
| `default_ec2_region` | 313 | commands.infra(1) |
| `ec2_repo_dir` | 320 | _(外部参照なし)_ |
| `saved_usb_busid` | 327 | commands.usb(2) |
| `set_saved_usb_busid` | 334 | commands.usb(1) |
| `saved_esp32_serial_port` | 342 | commands.setup(1), target.esptool(1) |
| `set_saved_esp32_serial_port` | 349 | commands.setup(2) |
| `saved_target_setting` | 357 | commands.setup(2) |
| `set_saved_target_setting` | 364 | commands.setup(2) |
| `saved_workspaces` | 372 | commands.setup(1), commands.workspace_resolver(1) |
| `set_saved_workspaces` | 376 | commands.setup(1) |
| `saved_adb_exe` | 387 | environments.registry.target.adb_win(1) |
| `set_saved_adb_exe` | 394 | environments.registry.target.adb_win(1) |
| `set_default_ec2_host` | 404 | commands.setup(3) |
| `set_default_ec2_instance_id` | 412 | commands.infra(1) |
| `set_default_ec2_region` | 420 | commands.infra(1) |

## `core.errors` (scripts/gar_lib/core/errors.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GarDomainError` | 4 | access.aws(1), access.docker(1), artifacts.store(2), build.codespaces(2), build.environment(1), build.esp32(2), build.local(4), build.spec(1), commands.sim(5), commands.target(6), commands.workspace_resolver(1), core.workspace(5), simulation.composition(6), simulation.host.aws_ec2(4), simulation.host.docker(4), simulation.runtime.linux_systemd(5), simulation.runtime.mujoco(5), simulation.runtime.pending(1), simulation.runtime.wokwi(8), target.composition(4), target.esp32(4), target.esp32_firmware(6), target.file_transfer(6), tests.test_gar_docker_simulation_host(4), tests.test_gar_pending_simulation_environments(2), tests.test_gar_sim_architecture(1), tests.test_gar_simulation_host(2), tests.test_gar_wokwi_environment(2) |
| `AccessConnectionError` | 8 | access.adb(1), access.aws(1), access.docker(3), access.ssh(2), commands.recovery(2), commands.sim(1), commands.target(1), tests.test_gar_access_channels(3), tests.test_gar_access_recovery(4), tests.test_gar_docker_simulation_host(2), tests.test_gar_sim_lifecycle(1), tests.test_gar_simulation_host(1), tests.test_gar_target_architecture(1) |

## `core.hardware` (scripts/gar_lib/core/hardware.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HW_TEMPLATE_FILES` | 15 | _(外部参照なし)_ |
| `HW_DIR` | 29 | _(外部参照なし)_ |
| `HW_TEMPLATE_REL` | 30 | _(外部参照なし)_ |
| `load_hw_definition` | 64 | api(5) |
| `write_hw_template` | 77 | commands.hw(1) |

## `core.tools_repository` (scripts/gar_lib/core/tools_repository.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_GAR_TOOLS_REPO` | 11 | _(外部参照なし)_ |
| `gar_tools_root` | 14 | core.hardware(1), simulation.composition(1), target.manifest(1) |
| `find_gar_tools_root` | 21 | _(外部参照なし)_ |
| `gar_tools_root_candidates` | 28 | _(外部参照なし)_ |
| `ensure_gar_tools_available` | 52 | commands.setup(1), tests.test_gar_cli(1) |

## `core.workspace` (scripts/gar_lib/core/workspace.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Workspace` | 14 | api(8), artifacts.store(4), build.codespaces(3), build.environment(4), build.esp32(5), build.local(3), build.spec(2), commands.recovery(2), commands.workspace_resolver(3), core.artifact(1), simulation.composition(8), target.composition(1), tests.test_gar_access_recovery(1), tests.test_gar_build_variables(4), tests.test_gar_cli(3), tests.test_gar_docker_simulation_host(2), tests.test_gar_linux_systemd_environment(1), tests.test_gar_pending_simulation_environments(2), tests.test_gar_sim_architecture(3), tests.test_gar_sim_lifecycle(1), tests.test_gar_simulation_host(2), tests.test_gar_target_architecture(5), tests.test_gar_wokwi_environment(2) |

## `environments.discovery` (scripts/gar_lib/environments/discovery.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `EnvironmentDiscoveryError` | 11 | _(外部参照なし)_ |
| `CATEGORY_METADATA` | 15 | _(外部参照なし)_ |
| `discover_environments` | 31 | commands.setup(1), tests.test_gar_discovery(4) |

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
| `sudo_block_reason` | 13 | environments.docker_install(1), environments.registry.codespace.github_codespaces(1), environments.registry.simulator.aws_ssm(1), environments.registry.target.adb_usb(1) |
| `print_user_terminal_handoff` | 34 | environments.docker_install(1), environments.registry.codespace.github_codespaces(1), environments.registry.simulator.aws_ssm(1), environments.registry.target.adb_usb(1) |
| `create_visible_terminal_request` | 60 | _(外部参照なし)_ |

## `environments.registry.codespace.github_codespaces` (scripts/gar_lib/environments/registry/codespace/github_codespaces.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `GitHubCodespacesEnvironment` | 10 | tests.test_gar_discovery(7) |

## `environments.registry.codespace.local_docker` (scripts/gar_lib/environments/registry/codespace/local_docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalDockerEnvironment` | 7 | tests.test_gar_discovery(4) |

## `environments.registry.simulator.aws_ssm` (scripts/gar_lib/environments/registry/simulator/aws_ssm.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsSsmEnvironment` | 12 | tests.test_gar_discovery(3) |

## `environments.registry.simulator.esp32_qemu` (scripts/gar_lib/environments/registry/simulator/esp32_qemu.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32QemuFirmwareEnvironment` | 13 | _(外部参照なし)_ |

## `environments.registry.simulator.local_docker` (scripts/gar_lib/environments/registry/simulator/local_docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LocalDockerEnvironment` | 7 | tests.test_gar_discovery(2) |

## `environments.registry.simulator.mujoco` (scripts/gar_lib/environments/registry/simulator/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `MujocoEnvironment` | 11 | tests.test_gar_discovery(1) |

## `environments.registry.simulator.renode_mcu` (scripts/gar_lib/environments/registry/simulator/renode_mcu.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RENODE_RELEASES_API` | 32 | _(外部参照なし)_ |
| `RENODE_RELEASES_PAGE` | 33 | _(外部参照なし)_ |
| `RENODE_DOCS` | 34 | _(外部参照なし)_ |
| `INSTALL_ROOT` | 36 | _(外部参照なし)_ |
| `TEST_VENV` | 37 | _(外部参照なし)_ |
| `BIN_DIR` | 38 | _(外部参照なし)_ |
| `LAUNCHER` | 39 | _(外部参照なし)_ |
| `TEST_LAUNCHER` | 40 | _(外部参照なし)_ |
| `RenodeMcuEnvironment` | 43 | tests.test_gar_discovery(1) |

## `environments.registry.simulator.ssh_remote` (scripts/gar_lib/environments/registry/simulator/ssh_remote.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SshRemoteEnvironment` | 6 | _(外部参照なし)_ |

## `environments.registry.simulator.wokwi` (scripts/gar_lib/environments/registry/simulator/wokwi.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `WokwiEnvironment` | 12 | tests.test_gar_discovery(4) |

## `environments.registry.target.adb_usb` (scripts/gar_lib/environments/registry/target/adb_usb.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AdbUsbEnvironment` | 10 | tests.test_gar_discovery(2) |

## `environments.registry.target.adb_win` (scripts/gar_lib/environments/registry/target/adb_win.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `WINGET_PACKAGE_ID` | 27 | _(外部参照なし)_ |
| `AdbWinEnvironment` | 30 | _(外部参照なし)_ |

## `environments.registry.target.esp32_esptool` (scripts/gar_lib/environments/registry/target/esp32_esptool.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `Esp32EsptoolEnvironment` | 13 | tests.test_gar_discovery(4) |

## `environments.registry.target.ssh_scp` (scripts/gar_lib/environments/registry/target/ssh_scp.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SshScpEnvironment` | 6 | _(外部参照なし)_ |

## `environments.setup_option` (scripts/gar_lib/environments/setup_option.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DependencyStatus` | 11 | environments.registry.simulator.mujoco(2), environments.registry.simulator.renode_mcu(3), environments.registry.simulator.wokwi(2), environments.registry.target.esp32_esptool(2) |
| `EnvironmentSetupOption` | 20 | commands.setup(19), environments.discovery(6), environments.registry.codespace.github_codespaces(1), environments.registry.codespace.local_docker(1), environments.registry.simulator.aws_ssm(1), environments.registry.simulator.esp32_qemu(1), environments.registry.simulator.local_docker(1), environments.registry.simulator.mujoco(1), environments.registry.simulator.renode_mcu(1), environments.registry.simulator.ssh_remote(1), environments.registry.simulator.wokwi(1), environments.registry.target.adb_usb(1), environments.registry.target.adb_win(1), environments.registry.target.esp32_esptool(1), environments.registry.target.ssh_scp(1), tests.test_gar_cli(6), tests.test_gar_discovery(1) |

## `simulation.composition` (scripts/gar_lib/simulation/composition.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LOCAL_DOCKER` | 50 | _(外部参照なし)_ |
| `selected_simulator` | 53 | _(外部参照なし)_ |
| `simulation_environment_for` | 57 | api(8), tests.test_gar_docker_simulation_host(1), tests.test_gar_pending_simulation_environments(2), tests.test_gar_wokwi_environment(1) |
| `simulation_host_for` | 99 | api(3), tests.test_gar_docker_simulation_host(4), tests.test_gar_simulation_host(2), tests.test_gar_wokwi_environment(1) |
| `hardware_control_for` | 139 | api(2), tests.test_gar_docker_simulation_host(1) |
| `docker_spec_for` | 168 | _(外部参照なし)_ |

## `simulation.diagnostics.model` (scripts/gar_lib/simulation/diagnostics/model.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationDiagnosticReport` | 13 | simulation.runtime.contract(1), simulation.runtime.pending(1) |
| `PayloadSimulationDiagnostic` | 21 | simulation.runtime.mujoco(2), simulation.runtime.wokwi(2) |
| `SimulationDiagnostic` | 34 | simulation.runtime.linux_systemd(2), tests.test_gar_sim_lifecycle(1) |

## `simulation.diagnostics.parse` (scripts/gar_lib/simulation/diagnostics/parse.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `parse_sim_diag` | 7 | simulation.diagnostics.model(1), tests.test_gar_cli(2) |
| `parse_gpio_runtime_status` | 60 | simulation.hardware.control(1), tests.test_gar_cli(1) |
| `parse_gpio_sim_check` | 108 | simulation.hardware.control(1), tests.test_gar_cli(1) |

## `simulation.hardware.control` (scripts/gar_lib/simulation/hardware/control.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HardwareControlResult` | 15 | simulation.hardware.mujoco(6) |
| `SimulationHardwareControl` | 34 | simulation.composition(1) |
| `LinuxBridgeHardwareControl` | 44 | simulation.composition(2), tests.test_gar_docker_simulation_host(1), tests.test_gar_hardware_control(4) |

## `simulation.hardware.io_actions` (scripts/gar_lib/simulation/hardware/io_actions.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `STATE_PATH` | 16 | _(外部参照なし)_ |
| `DEFAULT_BUTTON_LINE` | 18 | _(外部参照なし)_ |
| `DEFAULT_PRESS_DURATION_MS` | 19 | _(外部参照なし)_ |
| `BUTTON_LINE_ALIASES` | 21 | _(外部参照なし)_ |
| `IO_ACTIONS` | 30 | tests.test_gar_cli(1) |
| `IO_DEVICES` | 31 | _(外部参照なし)_ |
| `IoRequest` | 35 | _(外部参照なし)_ |
| `resolve_button_line` | 43 | _(外部参照なし)_ |
| `resolve` | 53 | simulation.runtime.linux_commands(1), tests.test_gar_cli(1) |

## `simulation.hardware.mujoco` (scripts/gar_lib/simulation/hardware/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_BRIDGE_URL` | 12 | simulation.runtime.mujoco(1) |
| `MujocoBridgeHardwareControl` | 15 | simulation.composition(1) |
| `bridge_state` | 58 | simulation.runtime.mujoco(1) |

## `simulation.host.aws_ec2` (scripts/gar_lib/simulation/host/aws_ec2.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `AwsEc2SimulationHostController` | 14 | simulation.composition(1), tests.test_gar_simulation_host(3) |

## `simulation.host.contract` (scripts/gar_lib/simulation/host/contract.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `SimulationHostState` | 11 | simulation.host.aws_ec2(2), simulation.host.docker(2), tests.test_gar_sim_lifecycle(1) |
| `SimulationHostStartResult` | 39 | simulation.host.aws_ec2(2), simulation.host.docker(2) |
| `SimulationHostController` | 46 | simulation.composition(1) |

## `simulation.host.docker` (scripts/gar_lib/simulation/host/docker.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `BACKEND_ID` | 13 | simulation.composition(1) |
| `DEFAULT_CONTAINER` | 15 | simulation.composition(1) |
| `DEFAULT_ADDRESS` | 16 | _(外部参照なし)_ |
| `ABSENT_STATE` | 18 | tests.test_gar_docker_simulation_host(1) |
| `DockerSimulationHostController` | 21 | simulation.composition(1), tests.test_gar_docker_simulation_host(4) |

## `simulation.host.docker_spec` (scripts/gar_lib/simulation/host/docker_spec.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_BRIDGE_PORT` | 10 | _(外部参照なし)_ |
| `DockerHostSpec` | 14 | simulation.composition(3), simulation.host.docker(1), tests.test_gar_docker_simulation_host(1) |
| `docker_host_spec` | 24 | simulation.composition(1), tests.test_gar_docker_simulation_host(1) |

## `simulation.host.ssh_config` (scripts/gar_lib/simulation/host/ssh_config.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `HostAddressUpdater` | 10 | simulation.host.aws_ec2(1) |
| `SshConfigHostAddressUpdater` | 14 | commands.infra(1), simulation.composition(1), tests.test_gar_cli(2), tests.test_gar_simulation_host(1) |

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
| `SIM_DIAG_DEVICES` | 13 | _(外部参照なし)_ |
| `GAR_ETC_DIR` | 14 | _(外部参照なし)_ |
| `GAR_HARDWARE_DIR` | 15 | _(外部参照なし)_ |
| `GAR_SBIN_DIR` | 16 | _(外部参照なし)_ |
| `GAR_LIB_DIR` | 17 | _(外部参照なし)_ |
| `GAR_RUN_DIR` | 18 | _(外部参照なし)_ |
| `GAR_HW_SIM_SOCK` | 19 | _(外部参照なし)_ |
| `GAR_BRIDGE_DIR` | 20 | _(外部参照なし)_ |
| `GAR_BRIDGE_START` | 21 | _(外部参照なし)_ |
| `GAR_GPIO_SIM_START` | 22 | _(外部参照なし)_ |
| `GAR_GPIO_SIM_STOP` | 23 | _(外部参照なし)_ |
| `GAR_CUSE_I2C` | 24 | _(外部参照なし)_ |
| `GAR_CUSE_SPI` | 25 | _(外部参照なし)_ |
| `PANEL_BASE_URL` | 26 | _(外部参照なし)_ |
| `SIM_GPIO_SIM_CHECK_COMMAND` | 28 | _(外部参照なし)_ |
| `gpio_sim_plan` | 141 | simulation.hardware.control(1), tests.test_gar_cli(1) |
| `LinuxSystemdCommandBuilder` | 168 | simulation.composition(4), simulation.hardware.control(1), simulation.runtime.linux_systemd(1), tests.test_gar_cli(9) |

## `simulation.runtime.linux_systemd` (scripts/gar_lib/simulation/runtime/linux_systemd.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `LinuxSystemdSimulationEnvironment` | 16 | simulation.composition(2), tests.test_gar_docker_simulation_host(1), tests.test_gar_linux_systemd_environment(5) |

## `simulation.runtime.mujoco` (scripts/gar_lib/simulation/runtime/mujoco.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_MODEL_PATH` | 19 | _(外部参照なし)_ |
| `DEFAULT_WORKSPACE_DIR` | 20 | _(外部参照なし)_ |
| `MujocoSimulationEnvironment` | 21 | simulation.composition(1), tests.test_gar_discovery(1) |

## `simulation.runtime.pending` (scripts/gar_lib/simulation/runtime/pending.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `PendingSimulationEnvironment` | 12 | simulation.runtime.aws_ssm(1), simulation.runtime.esp32_qemu(1), simulation.runtime.renode(1) |

## `simulation.runtime.process` (scripts/gar_lib/simulation/runtime/process.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ProcessLaunchResult` | 15 | tests.test_gar_wokwi_environment(1) |
| `ProcessChannel` | 20 | simulation.runtime.esp32_qemu(1), simulation.runtime.mujoco(1), simulation.runtime.renode(1), simulation.runtime.wokwi(1) |
| `LocalProcessChannel` | 36 | simulation.composition(4), simulation.runtime.mujoco(1), tests.test_gar_simulation_process(1) |

## `simulation.runtime.renode` (scripts/gar_lib/simulation/runtime/renode.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RenodeSimulationEnvironment` | 9 | simulation.composition(1), tests.test_gar_pending_simulation_environments(1) |

## `simulation.runtime.wokwi` (scripts/gar_lib/simulation/runtime/wokwi.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `DEFAULT_TIMEOUT_MS` | 17 | _(外部参照なし)_ |
| `WokwiSimulationEnvironment` | 20 | simulation.composition(1), tests.test_gar_wokwi_environment(6) |

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
| `write_sim_terminal_profile` | 33 | simulation.session.manager(1) |
| `sim_terminal_script` | 60 | _(外部参照なし)_ |

## `target.composition` (scripts/gar_lib/target/composition.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `target_environment_for` | 20 | api(1), tests.test_gar_target_architecture(3) |

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
| `DEFAULT_ESP32_ARTIFACT_ROOT` | 18 | target.esptool(1) |
| `DEFAULT_ESP32_CODESPACE_PROJECT_ROOT` | 21 | build.esp32(1) |
| `DEFAULT_ESP32_LOCAL_PROJECT_ROOT` | 24 | _(外部参照なし)_ |
| `DEFAULT_ESP32_PIO_ENV` | 25 | build.esp32(1) |
| `FLASH_LAYOUT` | 26 | build.esp32(1), target.esp32(1), target.esptool(2) |
| `find_latest_esp32_artifact` | 34 | _(外部参照なし)_ |
| `resolve_esp32_artifact_dir` | 47 | target.esptool(1) |
| `parse_esp32_build_artifact_path` | 54 | tests.test_gar_cli(1) |
| `run_streaming_command` | 62 | _(外部参照なし)_ |
| `fetch_esp32_codespace_artifact` | 96 | _(外部参照なし)_ |
| `build_esp32_firmware_codespace` | 145 | build.esp32(1), tests.test_gar_cli(1) |
| `build_esp32_firmware_local` | 183 | build.esp32(1) |

## `target.esptool` (scripts/gar_lib/target/esptool.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `ESPTOOL_VENV` | 22 | _(外部参照なし)_ |
| `normalize_esp32_serial_port` | 25 | tests.test_gar_cli(2) |
| `validate_esp32_artifact` | 37 | _(外部参照なし)_ |
| `esp32_serial_port_access_error` | 51 | _(外部参照なし)_ |
| `esp32_serial_failure_hint` | 82 | _(外部参照なし)_ |
| `verify_esp32_artifact_checksums` | 95 | _(外部参照なし)_ |
| `ensure_esptool_python` | 133 | _(外部参照なし)_ |
| `run_esp32_flash_command` | 155 | target.esp32(1), tests.test_gar_cli(3) |

## `target.file_transfer` (scripts/gar_lib/target/file_transfer.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `FileTransferTargetEnvironment` | 19 | target.composition(3), tests.test_gar_target_architecture(1) |

## `target.manifest` (scripts/gar_lib/target/manifest.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `TargetManifest` | 16 | commands.setup(12), tests.test_gar_cli(14), tests.test_gar_docker_simulation_host(3) |
| `discover_target_manifests` | 29 | commands.setup(1), tests.test_gar_cli(2) |
| `active_target_manifest` | 40 | simulation.composition(1) |
| `target_by_id` | 44 | commands.setup(2) |

## `vscode.profile_manage` (scripts/gar_lib/vscode/profile_manage.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `write_vscode_terminal_profile` | 10 | commands.code(1), simulation.session.remote(1) |
| `remove_vscode_terminal_profile` | 25 | commands.code(1) |

## `vscode.terminal_bridge` (scripts/gar_lib/vscode/terminal_bridge.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `installed_vscode_terminal_bridge_path` | 15 | commands.setup(1) |
| `install_vscode_terminal_bridge` | 29 | commands.setup(1) |

## `vscode.terminal_ui` (scripts/gar_lib/vscode/terminal_ui.py)

| メンバ | 行 | 参照元module (回数) |
|---|---:|---|
| `RESET` | 8 | _(外部参照なし)_ |
| `BOLD` | 9 | commands.setup(48) |
| `DIM` | 10 | commands.setup(30) |
| `GREEN` | 11 | commands.setup(24) |
| `YELLOW` | 12 | commands.setup(31) |
| `RED` | 13 | commands.setup(11) |
| `CYAN` | 14 | commands.setup(6) |
| `BLUE` | 15 | commands.setup(12) |
| `style` | 22 | commands.setup(133) |
| `safe_input` | 28 | commands.setup(22) |

## 外部未参照の公開メンバ一覧

同一module内でしか使われていない (または全く未使用の) 公開メンバ。 private化 (`_`prefix) や整理の候補。

| module | メンバ | 行 |
|---|---|---:|
| `access.channel` | `ConsoleChannel` | 37 |
| `access.docker` | `CONTAINER_FAILURE_MARKERS` | 20 |
| `access.docker` | `DAEMON_FAILURE_MARKERS` | 13 |
| `access.docker` | `connection_reason` | 37 |
| `access.docker` | `docker_executable` | 28 |
| `access.ssh` | `SSH_CONNECTION_OPTIONS` | 11 |
| `api` | `Simulation` | 29 |
| `api` | `SimulationApp` | 40 |
| `api` | `SimulationGpio` | 182 |
| `api` | `SimulationHost` | 138 |
| `api` | `SimulationIo` | 210 |
| `api` | `SimulationRuntime` | 65 |
| `api` | `Target` | 255 |
| `artifacts.manifest` | `DEFAULT_CODESPACE_ARTIFACT_ROOT` | 25 |
| `artifacts.manifest` | `artifact_deploy_files` | 202 |
| `artifacts.manifest` | `artifact_manifest_deploy_sources` | 64 |
| `artifacts.manifest` | `default_artifacts_dir` | 28 |
| `artifacts.manifest` | `default_codespace_artifact_root` | 32 |
| `artifacts.manifest` | `find_artifact_manifest` | 172 |
| `artifacts.manifest` | `gh_codespace_cp` | 158 |
| `artifacts.manifest` | `load_artifact_manifest` | 183 |
| `artifacts.manifest` | `select_codespace` | 36 |
| `build.environment` | `BuildEnvironment` | 16 |
| `build.spec` | `BuildSpec` | 18 |
| `build.spec` | `DEFAULT_REMOTE_SIM_ARCH` | 14 |
| `build.spec` | `compiler_for_architecture` | 23 |
| `build.spec` | `simulation_build_variables` | 31 |
| `cli` | `CODE_COMMAND_MAP` | 29 |
| `cli` | `add_code_start_arguments` | 115 |
| `cli` | `enable_argcomplete` | 63 |
| `cli` | `parser_completion_words` | 85 |
| `commands.code` | `DEFAULT_CODESPACE_REMOTE_PATH` | 20 |
| `commands.code` | `DEFAULT_GH_TIMEOUT_SECONDS` | 19 |
| `commands.code` | `boot_code_codespace` | 102 |
| `commands.code` | `codespace_terminal_script` | 695 |
| `commands.code` | `default_codespaces_mount_dir` | 501 |
| `commands.code` | `detect_codespace_workspace` | 572 |
| `commands.code` | `first_ssh_host` | 555 |
| `commands.code` | `gh_timeout_seconds` | 505 |
| `commands.code` | `load_codespace_state` | 481 |
| `commands.code` | `mount_codespace_code` | 598 |
| `commands.code` | `print_completed_stderr` | 549 |
| `commands.code` | `remote_path_exists` | 563 |
| `commands.code` | `run_codespace_remote` | 584 |
| `commands.code` | `run_gh_captured` | 521 |
| `commands.code` | `run_local_code_command` | 86 |
| `commands.code` | `select_code_codespace` | 446 |
| `commands.code` | `status_code_codespace` | 392 |
| `commands.code` | `unmount_codespace_code` | 646 |
| `commands.infra` | `TERRAFORM_DIR` | 24 |
| `commands.recovery` | `RecoveryAction` | 16 |
| `commands.setup` | `SKIP_CATEGORY` | 51 |
| `commands.setup` | `TARGET_MENU_ENTRY` | 52 |
| `commands.setup` | `clear_setup_screen` | 176 |
| `commands.setup` | `configure_esp32_serial_port` | 251 |
| `commands.setup` | `configure_target` | 622 |
| `commands.setup` | `configure_workspace_root` | 339 |
| `commands.setup` | `detect_esp32_serial_port_candidates` | 594 |
| `commands.setup` | `ensure_gar_tools_for_setup` | 166 |
| `commands.setup` | `ensure_selected_target_ready` | 653 |
| `commands.setup` | `environment_by_id` | 1040 |
| `commands.setup` | `grouped_environments` | 1026 |
| `commands.setup` | `managed_backend_categories` | 674 |
| `commands.setup` | `optional_setup_categories` | 748 |
| `commands.setup` | `prepare_target_backend` | 685 |
| `commands.setup` | `print_codespace_candidates` | 562 |
| `commands.setup` | `print_environment_overview` | 831 |
| `commands.setup` | `print_selected_target_summary` | 730 |
| `commands.setup` | `print_target_next_steps` | 604 |
| `commands.setup` | `print_target_summary` | 713 |
| `commands.setup` | `print_terminal_bridge_status` | 182 |
| `commands.setup` | `print_workspace_entry` | 435 |
| `commands.setup` | `probe_git_workspace` | 572 |
| `commands.setup` | `prompt_workspace_entry` | 482 |
| `commands.setup` | `prune_removed_target_backends` | 660 |
| `commands.setup` | `removable_target_backend_categories` | 666 |
| `commands.setup` | `save_selected_target` | 646 |
| `commands.setup` | `select_environment_for_category` | 924 |
| `commands.setup` | `select_setup_category` | 871 |
| `commands.setup` | `select_target` | 694 |
| `commands.setup` | `selected_target_manifest` | 744 |
| `commands.setup` | `unconfigured_categories` | 977 |
| `commands.setup` | `workspace_duplicate` | 447 |
| `commands.sim` | `IO_PARAMETERS` | 18 |
| `commands.sim` | `SIM_ACTIONS` | 22 |
| `commands.target` | `TARGET_ACTIONS` | 17 |
| `commands.usb` | `ANDROID_HINTS` | 30 |
| `commands.usb` | `ANDROID_VIDS` | 32 |
| `commands.usb` | `UsbDevice` | 36 |
| `commands.usb` | `list_usb_devices` | 235 |
| `core.command` | `SIM_RUNTIME_LOG` | 36 |
| `core.command` | `SIM_RUNTIME_STATUS` | 35 |
| `core.command` | `SIM_RUNTIME_STOP` | 34 |
| `core.config` | `DEFAULT_EC2_HOST` | 22 |
| `core.config` | `DEFAULT_EC2_INSTANCE_ID` | 23 |
| `core.config` | `DEFAULT_EC2_REGION` | 24 |
| `core.config` | `RUNTIME_HOST_PATTERN` | 26 |
| `core.config` | `ec2_repo_dir` | 320 |
| `core.hardware` | `HW_DIR` | 29 |
| `core.hardware` | `HW_TEMPLATE_FILES` | 15 |
| `core.hardware` | `HW_TEMPLATE_REL` | 30 |
| `core.tools_repository` | `DEFAULT_GAR_TOOLS_REPO` | 11 |
| `core.tools_repository` | `find_gar_tools_root` | 21 |
| `core.tools_repository` | `gar_tools_root_candidates` | 28 |
| `environments.discovery` | `CATEGORY_METADATA` | 15 |
| `environments.discovery` | `EnvironmentDiscoveryError` | 11 |
| `environments.docker_install` | `DOCKER_INSTALL_COMMANDS` | 12 |
| `environments.docker_install` | `GROUP_REFRESH_NOTE` | 20 |
| `environments.docker_install` | `is_wsl_or_linux` | 23 |
| `environments.install` | `create_visible_terminal_request` | 60 |
| `environments.registry.simulator.esp32_qemu` | `Esp32QemuFirmwareEnvironment` | 13 |
| `environments.registry.simulator.renode_mcu` | `BIN_DIR` | 38 |
| `environments.registry.simulator.renode_mcu` | `INSTALL_ROOT` | 36 |
| `environments.registry.simulator.renode_mcu` | `LAUNCHER` | 39 |
| `environments.registry.simulator.renode_mcu` | `RENODE_DOCS` | 34 |
| `environments.registry.simulator.renode_mcu` | `RENODE_RELEASES_API` | 32 |
| `environments.registry.simulator.renode_mcu` | `RENODE_RELEASES_PAGE` | 33 |
| `environments.registry.simulator.renode_mcu` | `TEST_LAUNCHER` | 40 |
| `environments.registry.simulator.renode_mcu` | `TEST_VENV` | 37 |
| `environments.registry.simulator.ssh_remote` | `SshRemoteEnvironment` | 6 |
| `environments.registry.target.adb_win` | `AdbWinEnvironment` | 30 |
| `environments.registry.target.adb_win` | `WINGET_PACKAGE_ID` | 27 |
| `environments.registry.target.ssh_scp` | `SshScpEnvironment` | 6 |
| `simulation.composition` | `LOCAL_DOCKER` | 50 |
| `simulation.composition` | `docker_spec_for` | 168 |
| `simulation.composition` | `selected_simulator` | 53 |
| `simulation.hardware.io_actions` | `BUTTON_LINE_ALIASES` | 21 |
| `simulation.hardware.io_actions` | `DEFAULT_BUTTON_LINE` | 18 |
| `simulation.hardware.io_actions` | `DEFAULT_PRESS_DURATION_MS` | 19 |
| `simulation.hardware.io_actions` | `IO_DEVICES` | 31 |
| `simulation.hardware.io_actions` | `IoRequest` | 35 |
| `simulation.hardware.io_actions` | `STATE_PATH` | 16 |
| `simulation.hardware.io_actions` | `resolve_button_line` | 43 |
| `simulation.host.docker` | `DEFAULT_ADDRESS` | 16 |
| `simulation.host.docker_spec` | `DEFAULT_BRIDGE_PORT` | 10 |
| `simulation.runtime.linux_commands` | `GAR_BRIDGE_DIR` | 20 |
| `simulation.runtime.linux_commands` | `GAR_BRIDGE_START` | 21 |
| `simulation.runtime.linux_commands` | `GAR_CUSE_I2C` | 24 |
| `simulation.runtime.linux_commands` | `GAR_CUSE_SPI` | 25 |
| `simulation.runtime.linux_commands` | `GAR_ETC_DIR` | 14 |
| `simulation.runtime.linux_commands` | `GAR_GPIO_SIM_START` | 22 |
| `simulation.runtime.linux_commands` | `GAR_GPIO_SIM_STOP` | 23 |
| `simulation.runtime.linux_commands` | `GAR_HARDWARE_DIR` | 15 |
| `simulation.runtime.linux_commands` | `GAR_HW_SIM_SOCK` | 19 |
| `simulation.runtime.linux_commands` | `GAR_LIB_DIR` | 17 |
| `simulation.runtime.linux_commands` | `GAR_RUN_DIR` | 18 |
| `simulation.runtime.linux_commands` | `GAR_SBIN_DIR` | 16 |
| `simulation.runtime.linux_commands` | `PANEL_BASE_URL` | 26 |
| `simulation.runtime.linux_commands` | `SIM_DIAG_DEVICES` | 13 |
| `simulation.runtime.linux_commands` | `SIM_GPIO_SIM_CHECK_COMMAND` | 28 |
| `simulation.runtime.mujoco` | `DEFAULT_MODEL_PATH` | 19 |
| `simulation.runtime.mujoco` | `DEFAULT_WORKSPACE_DIR` | 20 |
| `simulation.runtime.wokwi` | `DEFAULT_TIMEOUT_MS` | 17 |
| `simulation.session.manager` | `SimulationSessionManager` | 15 |
| `simulation.session.remote` | `sim_terminal_script` | 60 |
| `target.esp32_firmware` | `DEFAULT_ESP32_LOCAL_PROJECT_ROOT` | 24 |
| `target.esp32_firmware` | `fetch_esp32_codespace_artifact` | 96 |
| `target.esp32_firmware` | `find_latest_esp32_artifact` | 34 |
| `target.esp32_firmware` | `run_streaming_command` | 62 |
| `target.esptool` | `ESPTOOL_VENV` | 22 |
| `target.esptool` | `ensure_esptool_python` | 133 |
| `target.esptool` | `esp32_serial_failure_hint` | 82 |
| `target.esptool` | `esp32_serial_port_access_error` | 51 |
| `target.esptool` | `validate_esp32_artifact` | 37 |
| `target.esptool` | `verify_esp32_artifact_checksums` | 95 |
| `vscode.terminal_ui` | `RESET` | 8 |

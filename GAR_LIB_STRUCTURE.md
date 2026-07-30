# `scripts/gar_lib` 構成と責務

この文書は、2026-07-31時点の実装に基づく`gar_lib`の責務表です。
CLI、programmatic API、build、artifact、simulation、target、setupを別の境界として扱います。

## 用語

- **Workspace**: product code、branch、接続先、選択target・environmentをまとめた実行context。
- **BuildEnvironment**: product hookをlocalまたはCodespacesで実行するobject。
- **ArtifactStore**: build stagingをworkspace・artifact種別ごとの不変snapshotへ保存するobject。
- **SimulationEnvironment**: simulation artifactの配置とruntime lifecycleを担当するobject。
- **SimulationHostController**: runtimeを載せるDocker containerまたはEC2 hostを操作するobject。
- **SimulationHardwareControl**: GPIOやvirtual I/Oのcontrol planeを操作するobject。
- **TargetEnvironment**: artifactを物理targetへ転送・flashするobject。
- **EnvironmentSetupOption**: `gar setup`に表示する選択肢と依存導入情報。runtime操作は持たない。
- **TargetManifest**: `gar-tools/targets/*/target.json`から読むboard・backend定義。

`selected_target`はboard定義、`selected_environments.target`はADB・SSH・esptool等の
接続方式です。似た名前ですが別の概念です。

## ファイル構成

主な実装だけを示します。`__init__.py`はpackage APIを提供する場合を除いて省略します。

```text
scripts/gar_lib/
├─ cli.py                         root parserの合成、入力正規化、top-level dispatch
├─ api.py                         Gar(workspace).sim / target programmatic API
│
├─ commands/                      commandごとのparser、CLI adapter、表示
│  ├─ sim.py                      gar simのparserと明示的action dispatch
│  ├─ target.py                   gar targetのparserと明示的action dispatch
│  ├─ code.py                     gar codeのresolve→validate→接続→表示flow
│  ├─ code_connection.py          Codespaces検出、SSH config、sshfs操作
│  ├─ code_state.py               接続状態JSONとterminal script
│  ├─ completion.py               shell completion
│  ├─ terminal.py                 visible terminal request CLI
│  ├─ usb.py                      usbipd-winを介したWSL USB操作
│  ├─ hw.py                       hardware CSV初期化
│  ├─ infra.py                    Terraform補助
│  ├─ recovery.py                 接続失敗を復旧手順へ変換
│  ├─ workspace_resolver.py       config entryをtyped Workspaceへ変換
│  └─ setup/
│     ├─ command.py               setup phaseの順序
│     ├─ workspace_setup.py       product workspace登録
│     ├─ target_setup.py          target選択・backend整合性・接続設定
│     └─ environment_setup.py     environment選択・依存確認
│
├─ core/                          domain横断の値とlocal repository
│  ├─ workspace.py                typed Workspace
│  ├─ workspace_settings.py       connection/ec2/docker/target/adb/esp32設定型
│  ├─ artifact.py                 Artifact / ArtifactKind
│  ├─ config.py                   .gar/config.jsonのload/save
│  ├─ hardware.py                 hardware CSV load/init
│  ├─ archive.py                  archive展開時のpath安全性
│  ├─ tools_repository.py         gar-tools探索・取得
│  ├─ command.py                  GarCommand
│  └─ errors.py                   domain/access error
│
├─ artifacts/
│  ├─ manifest.py                 typed artifact.json解析とCodespaces取得
│  └─ store.py                    ArtifactStore / BuildArtifactStore / snapshot管理
│
├─ build/
│  ├─ environment.py              BuildEnvironment protocolとcomposition
│  ├─ spec.py                     ArtifactKind→product hookとbuild変数
│  ├─ local.py                    local hook実行
│  └─ codespaces.py               gh codespace sshでhook実行・artifact同期
│
├─ access/                        再利用可能な接続capability
│  ├─ channel.py                  command/file resultとprotocol
│  ├─ ssh.py                      SSH/scp
│  ├─ docker.py                   docker exec/cp
│  ├─ adb.py                      ADB shell/push
│  ├─ aws.py                      AWS CLI
│  ├─ serial.py                   serial console
│  └─ codespaces.py               gh codespace listの解析
│
├─ environments/                  setup選択肢とinstaller
│  ├─ setup_option.py             category別setup option base
│  ├─ discovery.py                明示registryの検証と表示順整列
│  ├─ install.py                  visible terminal handoff
│  ├─ installers/                 Renode / AWS SSM等の導入実装
│  └─ registry/                   categoryごとのENVIRONMENT_OPTIONS
│     ├─ codespace/
│     ├─ simulator/
│     └─ target/
│
├─ simulation/
│  ├─ composition.py              Workspaceからruntime/host/controlを構成
│  ├─ runtime/
│  │  ├─ contract.py              SimulationEnvironment protocol
│  │  ├─ linux_systemd.py         Linux/systemd runtime
│  │  ├─ linux_commands.py        lifecycle commandとGPIO plan
│  │  ├─ wokwi.py                 Wokwi workspace/process lifecycle
│  │  ├─ mujoco.py                MuJoCo artifact materializeとprocess lifecycle
│  │  ├─ process.py               process identity、atomic state、file lock
│  │  └─ pending.py               未実装backendの明示的domain error
│  ├─ host/                       Docker/EC2 lifecycleとSSH config
│  ├─ hardware/                   Linux/MuJoCo control planeとI/O action
│  ├─ diagnostics/                構造化diagnostic modelとparser
│  └─ session/                    VS Code terminal profileとport forward
│
├─ target/
│  ├─ manifest.py                 target.json探索・検証
│  ├─ composition.py              Workspaceからtarget environmentを構成
│  ├─ environment.py              TargetEnvironment protocol
│  ├─ file_transfer.py            ADB/SSH file transfer adapter
│  ├─ esp32.py                    ESP32 TargetEnvironment
│  ├─ esp32_firmware.py           flash artifact layout
│  └─ esptool.py                  artifact検証とserial flash
│
└─ vscode/
   ├─ terminal_requests.py        typed request store、atomic publish、GC
   ├─ terminal_ui.py              ANSI表示とsafe_input
   ├─ profile_manage.py           terminal profile追加・削除
   └─ terminal_bridge.py          VS Code extension検出・導入
```

ESP32専用のbuild moduleは廃止済みです。ESP32もLinux targetも、選択された
`LocalBuildEnvironment`または`CodespacesBuildEnvironment`が同じ
`scripts/product-target-build.sh`を実行します。PlatformIO等のproduct固有処理は
product hookが担当し、GARのtarget層はartifactの検証とdeploy/flashを担当します。

## CLIとprogrammatic API

各command moduleがparserと`argparse.Namespace`からの変換を所有します。`cli.py`は
それらを組み立て、`normalize_question_help()`、argcomplete、top-level dispatchだけを
担当します。argparseのprivate属性には依存しません。

```text
cli.main(argv)
  → build_parser_bundle()
  → parser.parse_args()
  → run_cli_command()
  → commands/<group>.pyの明示adapter
  → resolve_workspace(--workspace)
  → Gar(workspace).sim / target
  → composition + concrete environment
```

`api.py`はterminal表示を行わず、`Artifact`、`SimulationDiagnosticReport`、
`SimulationHostState`、`SimulationHostStartResult`、`HardwareControlResult`等を返します。
人間向け表示とJSON表示は`commands/sim.py` / `commands/target.py`に置きます。

`sim.py`と`target.py`はmethod名を動的に引くのではなく、`match`で許可済みactionを
明示的に呼びます。`gar sim io`もactionごとのparserで必須引数とdevice種別を表現します。

## Workspaceと設定境界

`.gar/config.json`はJSON mappingですが、`resolve_workspace()`で次の具象型へ変換します。

configは常にGaplessAgentRuntime直下の`.gar/config.json`を読みます。workspace選択は
`load_config(workspace_selector=...)`の呼び出し単位で行い、module globalへ保持しません。
selectorはID・表示名・local pathを受け付け、省略時は現在directoryを内包する最も近い
local workspace、または登録が1件だけならそのworkspaceを選びます。

| 設定 | Workspace上の型 | 主な利用先 |
|---|---|---|
| `connection` | `WorkspaceConnection` | local/Codespaces rootと接続名 |
| `selected_environments` | `SelectedEnvironments` | build/simulation/target composition |
| `selected_target` | `str | None` | target manifest、Docker spec、hardware |
| `hardware.path`または探索結果 | `Path | None` | runtime/controlへ渡すCSV |
| `ec2` | `Ec2Settings` | EC2 hostとSSH runtime |
| `docker` | `DockerSettings` | local Docker host上書き |
| `target` | `TargetSettings` | SSH deploy先 |
| `adb` | `AdbSettings` | ADB接続 |
| `esp32` | `Esp32Settings` | serial port |

runtime用hardwareは、明示path、product直下`hardware/`、product内`gar-tools` target、
共有`gar-tools` targetの順に解決します。`gar hw init`は現在のdirectoryの`hardware/`へ
選択中targetのテンプレートを生成します。target未選択時は`linux-device`を使い、
`--target`で明示的に切り替えられます。

## Buildとartifactの流れ

```text
ArtifactKind
  → ProductBuildSpecResolver
      SIM_APP     → scripts/product-sim-build.sh
      SIM_RUNTIME → scripts/product-sim-env-build.sh
      TARGET_APP  → scripts/product-target-build.sh
  → LocalBuildEnvironment または CodespacesBuildEnvironment
  → product staging: artifacts/from-codespace
  → LocalArtifactStore.capture/sync_from_codespaces
  → .gar/artifacts/<workspace-id>/<kind>/<build-id>/
  → latest.json
  → simulation/target deploy
```

`artifact.json`はtyped parserで一度検証します。`files` sectionとproductの`artifact`
sectionを受け付け、path traversalを拒否します。`SIM_APP`、`SIM_RUNTIME`、
`TARGET_APP`は別snapshotなので、一方のbuildが他方のlatestを上書きしません。

`build`はhook実行後にsnapshotを作り、`fetch`はCodespaces stagingを取得して指定kindを
snapshot化します。`deploy`はbuild/fetchを暗黙実行せず、該当kindのlatestを使います。

## Setup registryとruntime composition

setup optionは次のcategory baseに分かれます。

- `DevelopmentEnvironmentSetupOption`
- `SimulationEnvironmentSetupOption`
- `TargetEnvironmentSetupOption`

各registry packageの`ENVIRONMENT_OPTIONS`が選択肢を明示し、root registryが結合します。
`discovery.py`はreflectionやclass属性の書き換えを行わず、ID重複とmetadataを検証して
表示順に並べます。installerの大きな実装は`environments/installers/`へ分離します。

| category | 選択ID | 実行時の解決先 |
|---|---|---|
| development | `local`, `github_codespaces` | `commands/code.py`, `build/environment.py` |
| simulation | `local_docker`, `ssh_remote`, `wokwi`, `mujoco` | concrete runtime/host/control |
| simulation | `renode_mcu`, `esp32_qemu_firmware`, `aws_ssm` | error-only runtime（未実装を明示） |
| target | `adb_usb`, `adb_win`, `ssh_scp`, `esp32_esptool` | `target/composition.py` |

setupは`commands/setup/command.py`がphase順を管理し、workspace、target、environmentの
詳細処理は別moduleへ委譲します。target manifestはpath・backend対応も検証し、利用者が
選択した時点で不整合を表示します。

## Simulationの役割分離

| package | 責務 |
|---|---|
| `runtime/` | artifact配置とruntime lifecycle |
| `host/` | Docker container / EC2 instance lifecycle |
| `hardware/` | GPIOとBridge I/Oの操作 |
| `diagnostics/` | 構造化診断結果 |
| `session/` | remote terminal profileとport forward |

`session_host`はremote SSH runtimeだけが返します。local Docker、Wokwi、MuJoCoを
EC2 hostとして扱うfallbackはありません。Linux lifecycle commandはfail-fastで実行し、
systemd unitの`RuntimeDirectory`は`gar`へ統一されています。Wokwi/MuJoCoは共通の
`ProcessStateStore`でstateをatomic writeし、start/stopをfile lockで直列化します。
PIDだけでなく`/proc`の開始時刻とcommandを照合し、stale PIDで無関係なprocessを停止しません。
MuJoCoのapp deployはmanifestのfile/directoryを`.gar/mujoco/`へmaterializeし、absolute path、
`~`、`..`を含むdestinationを拒否してmodelを検証します。

Docker hostはtarget manifestのcontainer portとhostのpublished portを分けて扱います。
`docker inspect`の実際のimage・port binding・spec fingerprintをstatusへ返し、既存containerが
現在specと異なる場合は暗黙に再利用せず、削除して作り直す手順を明示します。

## フォルダ境界

| フォルダ | 担当 | 担当しないこと |
|---|---|---|
| `core/` | domain横断の値・設定型・安全なlocal処理 | CLI表示、backend固有lifecycle |
| `commands/` | parser、入力変換、表示、対話、復旧案内 | transportの低レベル実装 |
| `api.py` | programmatic use caseの協調 | argparse、人間向けprint |
| `build/` | product hook実行 | target固有compile手順、deploy |
| `artifacts/` | manifest検証、snapshot、同期 | simulation/targetの選択 |
| `access/` | SSH/ADB/Docker/AWS等の接続capability | setup UI、use case順序 |
| `environments/` | setup選択肢と依存導入 | runtime command実行 |
| `simulation/` | runtime/host/control/session | argparse、setup画面 |
| `target/` | physical target deploy/flash | product build |
| `vscode/` | terminal request/profile/extension I/O | domain判断 |

## 現在の制約

- `renode_mcu`、`esp32_qemu_firmware`、`aws_ssm`は選択と依存確認まで接続済みですが、
  runtime操作は未実装を明示するerror-only environmentです。
- `network` workspaceをBuildEnvironmentとして直接実行する実装はありません。
  buildは`local`または`github_codespaces`を選びます。
- `ssh_remote`はworkspaceごとのEC2 SSH host設定が必須です。個人名を含む既定hostへ
  fallbackしません。低レベルport-forward Make targetも`EC2=HOST`を必須とします。
- Wokwi scenarioはenvironment固有形式で、共通Bridge JSON scenarioへの統一途中です。
- setupの`.gar/config.json`自体は互換性のためmappingで保存し、typed objectへの変換は
  workspace解決境界で行います。

## 依存方向

```text
cli.py
  → commands/*
  → api.py
  → build/environment.py または simulation/target composition
  → concrete implementation
  → access capability
  → external system

commands/setup/*
  → environments registry / installers
  → config・target manifest
```

setup registryはruntime依存列とは別です。setup classをそのまま実行objectとして使わず、
保存したIDをcompositionで具象objectへ変換します。

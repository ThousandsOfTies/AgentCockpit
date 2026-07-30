# `scripts/gar_lib` 構成と責務

この文書は、2026-07-30時点の `scripts/gar_lib` の実ファイルと参照関係を確認してまとめたものです。
理想だけではなく、現在接続されている経路、補助経路、error-only stubとして接続されたsetup選択肢も区別して記載します。

## 用語

- **Workspace**: 1つの製品コードベースと、そのbranch・接続先・選択環境をまとめた実行コンテキスト。
- **BuildEnvironment**: `TARGET_APP`、`SIM_APP`、`SIM_RUNTIME`をどこでbuildするかを表す実行オブジェクト。
- **SimulationEnvironment**: simulation artifactの配置とruntimeのstart / stop / status / diag / logを担当する実行オブジェクト。
- **SimulationHostController**: simulation runtimeを載せるEC2等のhost自体を起動・停止する実行オブジェクト。
- **SimulationHardwareControl**: GPIOやvirtual H/W I/Oなど、simulation runtimeのhardware control planeを担当する実行オブジェクト。
- **TargetEnvironment**: artifactを物理targetへ配置・書き込みする実行オブジェクト。
- **EnvironmentSetupOption**: `gar setup`に表示する選択肢、依存確認、導入方法だけを持つメタデータ。runtime操作は持たない。
- **TargetManifest**: `gar-tools/targets/*/target.json`から読むboard / target定義。`TargetEnvironment`とは別概念。

設定ファイルの `selected_environments` は、runtime側では `Workspace.selected_environments`
として扱います。旧名 `selected_providers` は読み込み時のみ後方互換で受け付けます。
この文書では、setupのクラスを「setup選択肢」、実行時に生成されるオブジェクトを
「environment」と呼び分けます。

## 現在のファイル構成

各packageの `__init__.py` は省略しています。主にpackage markerまたは一部型のre-exportです。

```text
scripts/gar_lib/
├─ __main__.py                 python -m scripts.gar_lib の入口
├─ cli.py                      CLI引数定義・解析、top-level command runnerの選択、shell補完候補生成
├─ api.py                      Gar(workspace).sim / target の内部API
│
├─ access/                     接続手段ごとの小さなcapability
│  ├─ channel.py               共通result / CLI実行 / capability protocol
│  ├─ ssh.py                   SSH command / scp file channel
│  ├─ docker.py                docker exec command / docker cp file channelと失敗分類
│  ├─ adb.py                   ADB shell / file channel
│  ├─ aws.py                   AWS CLI command channelと認証失敗分類
│  ├─ serial.py                serial console channel
│  └─ codespaces.py            gh codespace list出力の解析だけを共有
│
├─ artifacts/                  artifact bundleの検証・保管・同期
│  ├─ store.py                 ArtifactStore / LocalArtifactStore
│  └─ manifest.py              artifact.json解析とCodespaces artifact取得
│
├─ build/                      product buildの実行環境
│  ├─ spec.py                  BuildSpecとProductBuildSpecResolver
│  ├─ environment.py           BuildEnvironment protocolとbuild_environment_for()
│  ├─ local.py                 local product hook実行
│  ├─ codespaces.py            Codespaces上のhook実行とartifact同期
│  └─ esp32.py                 ESP32 firmware buildとartifact materialize
│
├─ commands/                   command groupごとのCLI定義とadapter
│  ├─ sim.py                   gar simのparser定義・action解決・内部API adapter
│  ├─ target.py                gar targetのparser定義・action解決・内部API adapter
│  ├─ workspace_resolver.py    --workspaceから実行対象を一意に解決
│  ├─ recovery.py              接続失敗を利用者向け復旧操作へ変換
│  ├─ setup.py                 workspace / target / setup選択肢の対話設定
│  ├─ code.py                  Local / Codespacesのboot・mount・terminal管理
│  ├─ infra.py                 Terraformによるsimulation host作成・破棄
│  ├─ usb.py                   usbipd-winによるWSL USB接続
│  ├─ terminal.py              Terminal Bridge request作成・GC
│  └─ hw.py                    hardware template初期化のCLI adapter
│
├─ core/                       複数domainから参照する基盤モデルとrepository
│  ├─ workspace.py             Workspace
│  ├─ artifact.py              Artifact / ArtifactKind
│  ├─ command.py               GarCommandと標準command定数（retry文字列・help表示用）
│  ├─ errors.py                GarDomainError / AccessConnectionError
│  ├─ config.py                .gar/config.jsonの読み書きとworkspace単位設定の正規化
│  ├─ hardware.py              hardware CSV読込とtemplate生成
│  └─ tools_repository.py      gar-tools repositoryの探索・取得
│
├─ environments/               setup用選択肢の発見・依存導入
│  ├─ setup_option.py          EnvironmentSetupOption / DependencyStatus
│  ├─ discovery.py             registry packageの自動走査とcategory付与
│  ├─ docker_install.py        dockerを必要とするsetup選択肢共通のapt-get導入
│  ├─ install.py               sudo判定とvisible terminalへのhandoff
│  └─ registry/
│     ├─ codespace/
│     │  ├─ local_docker.py    Local Dockerの依存確認・導入
│     │  └─ github_codespaces.py  gh / sshfsの依存確認・導入
│     ├─ simulator/
│     │  ├─ local_docker.py    Local Docker simulation hostの依存情報
│     │  ├─ ssh_remote.py      SSH Remoteの依存情報
│     │  ├─ wokwi.py           Wokwi CLIの依存確認・導入
│     │  ├─ mujoco.py          MuJoCo Python packageの依存確認・導入
│     │  ├─ renode_mcu.py      Renode / renode-testの導入
│     │  ├─ esp32_qemu.py      Espressif QEMUの依存情報
│     │  └─ aws_ssm.py         AWS CLI / SSM pluginの導入（runtimeはstub）
│     └─ target/
│        ├─ adb_usb.py         Linux ADBの依存確認・導入
│        ├─ adb_win.py         Windows ADBの検出・設定
│        ├─ ssh_scp.py         SSH / scpの依存情報
│        └─ esp32_esptool.py   esptoolの依存確認・導入
|
├─ simulation/                 setupで選ばれたsimulation object graphと役割別実装
│  ├─ composition.py           simulator IDからruntime / host / hardwareを組み立てる入口
│  ├─ runtime/                 simulation上でartifactを動かすenvironment
│  │  ├─ contract.py           SimulationEnvironment protocol
│  │  ├─ linux_systemd.py      Linux/systemd runtimeとartifact配置
│  │  ├─ linux_commands.py     Linux runtime command builderとGPIO計画
│  │  ├─ wokwi.py              Wokwi runtime・project配置・process管理
│  │  ├─ mujoco.py             MuJoCo runtime
│  │  ├─ pending.py            未実装操作を明示的なdomain errorにする共通stub
│  │  ├─ renode.py             Renodeのerror-only具体environment
│  │  ├─ esp32_qemu.py         ESP32 QEMUのerror-only具体environment
│  │  ├─ aws_ssm.py            AWS SSMのerror-only具体environment
│  │  └─ process.py            simulator local processの起動・停止capability
│  ├─ host/                    runtimeを載せるcontainer / VMのlifecycle
│  │  ├─ contract.py           SimulationHostController protocolと結果
│  │  ├─ docker.py             local containerのsimulation host lifecycle
│  │  ├─ docker_spec.py        target定義からcontainerの形を組み立てる
│  │  ├─ aws_ec2.py            AWS EC2 host lifecycle
│  │  └─ ssh_config.py         EC2 host用SSH configのHostName更新
│  ├─ hardware/                virtual H/W control plane
│  │  ├─ control.py            control protocolとLinux bridge実装
│  │  ├─ mujoco.py             MuJoCo HTTP bridge hardware control
│  │  └─ io_actions.py         共通の操作語彙とBridge API解決
│  ├─ diagnostics/
│  │  ├─ model.py              構造化diagnostic結果
│  │  └─ parse.py              Linux diagnostic / GPIO出力parser
│  └─ session/
│     ├─ manager.py            SimulationSessionManager protocolとVS Code adapter
│     └─ remote.py             SSH port forwardとterminal profileの実処理
│
├─ target/                     物理target domainと具体environment
│  ├─ manifest.py              gar-toolsのtarget.json読込み・TargetManifest検索
│  ├─ environment.py           TargetEnvironment protocol
│  ├─ composition.py           target_environment_for(): ADB / SSH / ESP32実装を組み立てる
│  ├─ file_transfer.py         command + file channelによるartifact配置
│  ├─ esp32.py                 esptool書込みを行うESP32 TargetEnvironment
│  ├─ esp32_firmware.py        明示的build-esp32とartifact取得の補助経路
│  └─ esptool.py               ESP32 artifact検証とesptool書込み
└─ vscode/                     VS Code固有I/O
   ├─ terminal_ui.py           ANSI表示とsafe_input
   ├─ profile_manage.py        integrated terminal profileの追加・削除
   └─ terminal_bridge.py       VS Code extensionの検出・導入
```

## コマンド1本が通る経路

`cli.py` は root CLI を組み立て、引数解析の結果から呼び出す command runner を決定します。
`sim` と `target` のparser定義・実行判断・workspace解決・接続失敗のrecoveryは、
それぞれの `commands/<command>.py` に置きます。leaf parserが保持する実行情報は
`GarCommand(group, subject, action)` だけです。`sim infra` も `sim` runnerが扱います。
`setup`、`code`、`terminal`、`usb`、`hw` は、`main()` から対応する `commands/`
モジュールのrunnerへ直接渡します。

`cli.py` が担うのは次の4点です。

- root parserの作成とcommand moduleが提供するparserの合成
- `main()` における引数解析と top-level command runner の選択
- `?` を文脈に応じた `--help` に正規化する処理
- bash completion script と、argparse構造からの補完候補生成

```text
cli.py: main()
  ├─ parser.parse_args() → args.command と args.gar_command が決まる
  └─ args.command に対応する runner を呼ぶ
          ├─ sim    → commands/sim.py: run_sim_command(args)
          └─ target → commands/target.py: run_target_command(args)
          ↓
commands/sim.py: run_sim_command(args)
  ├─ resolve_workspace(--workspace) で Workspace を1つ選ぶ
  ├─ Gar(workspace).sim からsubject objectを選ぶ
  ├─ SIM_ACTIONSで検証したGarCommand.actionからAPI methodを選ぶ
  ├─ AccessConnectionError → commands/recovery.py: report_access_failure()
  └─ CLI optionを内部APIの明示引数へ変換する
          ↓
api.py: Gar(workspace).sim.runtime.start(...)
  ├─ simulation_environment_for(workspace)      ← simulation/composition.py
  ├─ environment.start(load_hw_definition())    ← 実処理
  └─ 結果をその場でprint、exit codeをreturn
          ↓
access channel / external process
```

`gar sim runtime <action>` の action は `SimulationEnvironment` protocol の
method名と1:1です（deploy / start / stop / status / diag / log）。

```text
target build:
  Workspace → BuildEnvironment → TARGET_APP Artifact

target deploy:
  Workspace → latest TARGET_APP Artifact → TargetEnvironment.deploy

sim build:
  Workspace → BuildEnvironment → SIM_APP Artifact

sim deploy:
  Workspace → latest SIM_APP Artifact → SimulationEnvironment.deploy

sim runtime start:
  Workspace → SimulationEnvironment.start → SimulationSessionManager.start

sim host start:
  Workspace → SimulationHostController.start
```

`setup`、`code`、`infra`、`usb`、`terminal`、`hw`は Workspace を必要としないため、
`main()` から直接呼びます。

## 設定から実行オブジェクトへの対応

| 保存項目 | 読込み先 | 実行時の用途 |
|---|---|---|
| `workspaces[].id/name/branch/connection` | `commands/workspace_resolver.py: resolve_workspace()` | Workspaceの識別とlocal / Codespaces / network接続情報 |
| `selected_environments.codespace` | `Workspace.selected_environments["codespace"]` | `build_environment_for()`と`gar code` |
| `selected_environments.simulator` | `Workspace.selected_environments["simulator"]` | `simulation_environment_for()` / `hardware_control_for()` |
| `selected_environments.target` | `Workspace.selected_environments["target"]` | `target_environment_for()` |
| `selected_target` | `commands/setup.py` / `simulation/composition.py: docker_spec_for()` | TargetManifest選択とsetup表示、`local_docker`のcontainer形状 |
| `ec2` | Workspace / config helper | simulation host、SSH runtime host、repository更新 |
| `target` / `adb` / `esp32` | Workspace / config helper | physical targetのhost・dest・serial・port |

`selected_target`は `Workspace` modelには含まれません。`simulation/composition.py`の
`docker_spec_for()`が`active_target_manifest()`経由でTargetManifestを引き、containerの
image・device・mountを決めます。他のbackendは依然として参照しません。

## 現在の実装対応表

### BuildEnvironment

| setup ID | 実装 | 備考 |
|---|---:|---|
| `local` | 対応 | workspaceのlocal pathでproduct build hookを実行 |
| `github_codespaces` | 対応 | `gh codespace ssh`でhookを実行しartifactをlocalへ同期 |
| network workspace | 未対応 | workspace登録はできるが、専用のNetworkBuildEnvironmentはない |

### SimulationEnvironment

| setup ID | setup/導入 | runtime | hardware control | 備考 |
|---|---:|---:|---:|---|
| `local_docker` | 対応 | 対応 | 対応 | `docker exec` / `docker cp` でLinux/systemd runtimeを操作。GPIOはhost kernel 5.17+が必要 |
| `ssh_remote` | 対応 | 対応 | 対応 | Linux/systemd runtime。EC2の場合もこのIDを使う |
| `wokwi` | 対応 | 対応 | 未対応 | runtimeとartifact配置は実装済み。GPIO/io backendはない |
| `mujoco` | 対応 | 対応 | 対応 | local processとHTTP bridgeを使用 |
| `renode_mcu` | 対応 | stub接続 | 未接続 | 具体environmentを生成し、runtime操作時は明示的な未実装エラー |
| `esp32_qemu_firmware` | 依存情報のみ | stub接続 | 未接続 | 具体environmentを生成し、runtime操作時は明示的な未実装エラー |
| `aws_ssm` | 対応 | stub接続 | 未接続 | AWS channelまで組み立てるが、runtime操作は明示的な未実装エラー |

`SimulationHostController`はAWS EC2とDockerの2実装です。これは`SimulationEnvironment`とは
別軸で、`local_docker`はtarget定義の`simulation.docker`（workspaceの`docker`で上書き）から、
それ以外は`ec2.host / instance_id / region`から生成されます。

### TargetEnvironment

| setup ID | runtime | 具体実装 |
|---|---:|---|
| `adb_usb` | 対応 | ADB shell + file transfer |
| `adb_win` | 対応 | WSLからWindows `adb.exe`を使用 |
| `ssh_scp` | 対応 | SSH command + scp file transfer |
| `esp32_esptool` | 対応 | Esp32TargetEnvironment |

## フォルダ境界

| フォルダ | 担当すること | 担当しないこと |
|---|---|---|
| `core/` | 複数domainで共有する値、設定、repository、domain error | subprocess、CLI表示、domain固有実行 |
| `commands/workspace_resolver.py` | configからWorkspaceを一意に解決 | buildや接続の実行 |
| `build/` | product hookを指定場所で実行 | runtimeへのdeploy |
| `artifacts/` | artifact manifest検証、bundle選択・同期 | simulation/target固有判断 |
| `access/` | SSH、ADB、AWS等の複数domainで使える接続capability | ユースケース順序、setup UI |
| `simulation/` | simulation runtime / host / controlと専用process capability | argparse、setup選択画面 |
| `target/` | physical targetへのdeploy/write | setup選択画面 |
| `environments/` | setup候補の発見、依存確認・導入 | runtime commandの実行 |
| `commands/` | CLI表示・対話・復旧案内・補助command・Application境界 | 標準sim/targetのdomainシーケンス |
| `vscode/` | VS Code terminal UI/profile/extension I/O | simulationやtargetの判断 |

## 似た名前の区別

| 名前 | 役割 |
|---|---|
| `environments/registry/simulator` | setup画面の選択肢と依存導入。runtime実装ではない |
| `simulation/` | 選択後にApplicationから操作されるruntime / host / control実装 |
| `commands/infra.py` | TerraformでEC2 resourceを作成・破棄するprovisioning |
| `SimulationHostController` | 既に存在するEC2 instanceのstart / stop / status |
| `TargetManifest` / `selected_target` | board・target定義と利用可能backendのsetup情報 |
| `TargetEnvironment` / `selected_environments.target` | artifactを物理targetへ運ぶアクセス方式 |
| `SimulationEnvironment` | simulation runtime本体 |
| `SimulationSessionManager` | runtimeへ入るterminal profileとport forward |
| `target/esp32.py` | 標準TargetEnvironmentへesptoolを適合させるinstaller |
| `target/esp32_firmware.py` | `Esp32BuildEnvironment`が使うPlatformIO build・artifact取得helper |
| `target/esptool.py` | artifact検証と実際のflash command |

## 確認できた課題

### 優先度: 高

1. **setup選択肢ごとのruntime成熟度を機械的に判定できない**
   - `renode_mcu`、`esp32_qemu_firmware`、`aws_ssm`も`simulation_environment_for()`から固有のerror-only componentとして生成できるようになった。
   - ただしsetup metadataから「実装済み」「stub接続」「非対応」を判定できず、現在は説明文と実装クラスに分散している。
   - setup項目に `runtime_maturity` のような明示的capabilityを持たせ、表示と`*_for()`の対応を検証できるようにする余地がある。

2. **workspaceの接続種別とBuildEnvironment選択が独立しており、矛盾を作れる**
   - `connection.type`は `local / codespaces / network`、build側の設定は `selected_environments.codespace`の `local / github_codespaces`。
   - network workspaceは登録できるがNetworkBuildEnvironmentがなく、localまたはCodespacesを選ぶと必要property取得時に失敗する。
   - simulationの`ssh_remote`も`connection.host`ではなく`workspace.ec2.host`を読むため、「任意のnetwork workspace」と「EC2用SSH設定」の境界が曖昧。
   - Workspace接続とBuildEnvironmentの関係を`build_environment_for()`で検証する必要がある。

3. **Terminal Bridge requestの保存実装が二重化している**
   - `commands/terminal.py`はGAR runtime直下の `CONFIG_PATH.parent/terminal-requests`へ保存する。
   - `environments/install.py`は `cwd/.gar/terminal-requests`へ直接保存する。
   - product workspaceからsetupを実行すると別の `.gar` を作る可能性があるため、単一のTerminalRequesterへ統合すべき。

4. **`selected_target`と`selected_environments.target`の関係がruntimeに表現されていない**
   - 前者はboard/TargetManifest、後者はアクセス方式だが、名前が近く利用者・実装者の双方に分かりにくい。
   - `local_docker`のhost生成は`active_target_manifest()`でTargetManifestを参照するようになったが、
     他のbackendはsetup時の制約しか受け取らない。WorkspaceとTargetManifestの紐づけも暗黙のまま。
   - `TargetDefinition`と`TargetEnvironment`を明示的に別モデルとして結合する余地がある。

5. **product固有のEC2 host既定値がconfig層に残っている**
   - `config.py`の `load_config()` / `default_config()` / `default_ec2_host()`は、未設定時に `DEFAULT_EC2_HOST = "vibecode-graviton"`を返す。
   - `resolve_workspace()`はraw entryを使う一方、setupや補助commandはこのfallbackを使うため、同じ未設定状態の扱いも経路で異なる。
   - 複数workspace構成ではhost未設定を明示的に扱い、setupで入力させる方が一貫する。

### 優先度: 中

6. **Codespacesのアクセス実装が複数層へ分散している**
   - list解析は `access/codespaces.py`、VM/mount操作は `commands/code.py`、buildは `build/codespaces.py`、artifact取得は `artifacts/manifest.py`、ESP32補助取得は `target/esp32_firmware.py`。
   - `gh codespace`実行・認証・timeout・転送をまとめるCodespaces access channel/controllerがない。

7. **ESP32 build helperのpackage境界と既定値がtarget固有のまま**
   - 標準経路は`BuildEnvironment.build(TARGET_APP)` → `Esp32BuildEnvironment` → `TargetEnvironment.deploy`へ統合済み。
   - ただし`build/esp32.py`が`target/esp32_firmware.py`のPlatformIO helperを参照し、既定project pathとPIO environmentもVibe Remote向けの値を持つ。
   - helperをbuild側へ移し、target manifestまたはworkspace設定を必須化すると依存方向と汎用性が明確になる。

8. **esptoolの導入先が二重化している**
   - setup選択肢はGARの `.venv`へinstallする。
   - `target/esptool.py`は見つからない場合に `~/.local/share/gar/esptool-venv`を新規作成する。
   - 依存導入をsetupへ集約するか、managed tool environmentを1つに決める必要がある。

9. **session実装が薄い二層になっている**
   - `simulation/session/manager.py`の`VsCodeSimulationSessionManager`は、ほぼそのまま`session/remote.py`のfree functionへ委譲する。
   - protocol境界は有用だが、具体実装を1ファイルにまとめるか、`session/remote.py`をaccess/vscode側へ移すと責務が明確になる。

10. **表示責務がCLI境界へ完全には集約されていない**
    - `api.py`、`HardwareControlResult.render`、Wokwi、MuJoCo、Linux systemd、target/esptool、artifact manifestがそれぞれ直接`print`する。
    - domain結果を構造化してCLI境界で表示する方針をどこまで適用するか決める必要がある。

11. **hardware定義とtemplate生成が同居している**
    - `core/hardware.py`はApplication用Repository、CSV parser、`gar hw init`用writerを同時に持つ。
    - fallbackも選択TargetManifestではなく固定の `gar-tools/targets/linux-device/hardware`を参照する。
    - repositoryとtemplate initializer、target別hardware sourceの分離余地がある。

### 優先度: 低 / 整理候補

12. **大きなCLI実装が残っている**
    - `cli.py` 約426行、`commands/setup.py` 約1072行、`commands/code.py` 約720行、`simulation/runtime/linux_commands.py` 約562行、`commands/usb.py` 約382行。
    - 標準Application経路は分離済みだが、parser定義、setupのworkspace/target/environment設定、Codespaces mount処理、Linux command builderはさらに分割可能。

13. **package re-exportの方針がpackageごとに異なる**
    - `core/__init__.py`やsimulation配下の`__init__.py`はpackage markerだが、`build/__init__.py`は主要型をre-exportしている。
    - 内部実装は具体moduleを直接importしており、re-exportを正式APIとして維持するか、すべてpackage markerへ揃えるかを決める余地がある。

14. **setup discoveryに不要な明示importが残る**
    - `commands/setup.py`は自動discoveryを使いながら`WokwiEnvironment`を`# noqa: F401`付きで明示importしている。
    - discoveryに必要でないことを確認して削除できる。

## 今後の依存方向

```text
cli.py（root parserの合成とtop-level dispatch）
        ↓
commands/sim.py, commands/target.py
（group parser定義・action解決・workspace解決・引数変換・error recovery）
        ↓
api.py（Gar(workspace).sim / target のprogrammatic API）
        ↓
build/environment.py または */composition.py の *_for(workspace)（設定 → 具体オブジェクト）
        ↓
concrete build / simulation / target implementations
        ↓
access capabilities
        ↓
external systems
```

`environments/registry`はこのruntime依存列とは別に、setup時の選択肢と依存導入だけを
提供します。全setup IDは`*_for()`から具体environmentへ接続されましたが、実装済みか
error-only stubかという成熟度は、今後明示的な登録表またはcapabilityで検証できるようにするのが
次の整理点です。

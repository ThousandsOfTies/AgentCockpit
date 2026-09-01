# コマンドリファレンス

GARの公開コマンド、構文、主要optionを一覧する。環境の準備手順は
[0から実機まで](00_ZERO_TO_TARGET_TUTORIAL.md)、実行場所と設定データの説明は
[開発環境](03_DEVELOPMENT_ENVIRONMENT.md)、simulationの運用手順は
[シミュレーション](06_SIMULATION.md)を参照する。

## 呼び出し方

初回だけGAR repositoryをCWDにしてlauncherを明示する。

```powershell
# Windows
.\scripts\gar.cmd setup
.\scripts\gar.cmd config
```

```bash
# Linux / macOS
./scripts/gar setup
./scripts/gar config
```

`gar setup`で`scripts`をPATHへ登録した後は、新しいterminalからOSにかかわらず`gar <command>`と呼び出せる。<br>
個別commandの正確なusageは`gar <command> --help`、
さらに下位groupがある場合は`gar <command> <subject> --help`で確認する。

複数workspaceを登録している場合は`--workspace NAME`で対象を指定する。登録が1件だけなら
多くのcommandで省略でき、Product workspace内からの実行時はそのpathに一致する設定が優先される。
`--json`対応commandはAI／CI向けにstdoutへ機械可読結果を出力する。

## 1. Runtime準備と設定

| コマンド | 内容 |
|---|---|
| `gar setup` | repositoryの`.venv`と`requirements-gar.txt`を準備し、未登録なら`scripts`のユーザーPATH登録を`[Y/n]`で確認 |
| `gar config` | Product workspace、Target、Build、Simulation、Sim Host、Target接続を対話設定 |
| `gar config --no-install` | environment固有toolを導入せず、不足内容だけを表示 |
| `gar config --ec2-host HOST` | AWS互換用のSSH config Host aliasを保存 |
| `gar config --esp32-port PORT` | esptoolが使うserial portを保存（例: `COM3`、`/dev/ttyUSB0`） |

`setup`はlauncherだけが処理し、workspaceや接続先を設定しない。非対話実行ではPATHを変更しない。
PATHが現在または永続設定に既に含まれる場合は登録をSKIPする。設定は`config`が
GAR repository直下の`.gar/config.json`へworkspace単位で保存する。

## 2. Build workspace接続 (`gar code`)

| コマンド | 内容 |
|---|---|
| `gar code boot [--workspace NAME] [--target TARGET]` | Codespacesのdevelopment targetを起動 |
| `gar code start [--workspace NAME] [--target TARGET]` | CodespaceへのSSH設定とVS Code terminal profileを作成 |
| `gar code stop [--workspace NAME] [--target TARGET] [--shutdown]` | local接続を解除し、必要ならCodespace VMも停止 |
| `gar code shutdown [--workspace NAME] [--target TARGET]` | Codespace VMを停止 |
| `gar code status [--workspace NAME] [--target TARGET]` | VMとlocal接続の状態を表示 |

`--codespace TARGET`は`--target TARGET`の互換aliasである。`start`は`--remote-path`、
`--mount-dir`、`--settings`、`--profile-name`、`--no-mount`、`stop`は`--mount-dir`、
`--settings`、`--profile-name`、`status`は`--mount-dir`にも対応する。
Windowsの`start`は常にno-mountで、POSIX hostだけが既定でsshfs mountを使う。

## 3. シミュレーション (`gar sim`)

構文は`gar sim <subject> <action> [options]`である。

### Host (`gar sim host`)

| コマンド | 内容 |
|---|---|
| `gar sim host start [--workspace NAME] [--pull] [--no-update-ssh]` | 選択したVirtualBox／AWS／legacy Docker hostを起動 |
| `gar sim host stop [--workspace NAME]` | 選択hostを停止 |
| `gar sim host status [--workspace NAME] [--json]` | providerの実状態を表示 |

### Runtime (`gar sim runtime`)

| コマンド | 内容 |
|---|---|
| `gar sim runtime build [--workspace NAME]` | device stubやBridge等のruntime artifactをbuild |
| `gar sim runtime deploy [--workspace NAME]` | runtime artifactをSim Hostへ配置 |
| `gar sim runtime start [--workspace NAME]` | runtimeを起動し、既定ではHardware Panelのport forwardも開始 |
| `gar sim runtime stop [--workspace NAME]` | runtimeを停止し、既定ではport forwardも停止 |
| `gar sim runtime status [--workspace NAME]` | runtimeの状態を表示 |
| `gar sim runtime log [--workspace NAME]` | runtime logを表示 |
| `gar sim runtime diag [--workspace NAME] [--json]` | process、virtual device、APIを診断 |

`runtime start`は`--settings PATH`、`--profile-name NAME`、`--panel-port PORT`、
`--no-port-forward`、`runtime stop`は`--keep-port-forward`にも対応する。

### Application (`gar sim app`)

| コマンド | 内容 |
|---|---|
| `gar sim app build [--workspace NAME]` | `product-sim-build.sh`を選択BuildEnvironmentで実行 |
| `gar sim app clean [--workspace NAME]` | Product workspaceのsimulation build artifactを削除 |
| `gar sim app deploy [--workspace NAME]` | 最新のSIM_APP artifactをruntimeへ配置 |

### GPIO (`gar sim gpio`)

| コマンド | 内容 |
|---|---|
| `gar sim gpio plan [--workspace NAME] [--json]` | hardware定義から生成するGPIO runtimeを表示 |
| `gar sim gpio install [--workspace NAME]` | GPIO dummy runtimeをhostへ配置 |
| `gar sim gpio start [--workspace NAME]` | GPIO dummy runtimeを起動 |
| `gar sim gpio stop [--workspace NAME]` | GPIO dummy runtimeを停止 |
| `gar sim gpio status [--workspace NAME] [--json]` | GPIO runtimeの状態を表示 |
| `gar sim gpio check [--workspace NAME] [--json]` | kernel側の前提条件を確認 |

### Virtual H/W (`gar sim io`)

| コマンド | 内容 |
|---|---|
| `gar sim io state [--workspace NAME] [--json]` | Bridgeからvirtual H/Wの現在値を取得 |
| `gar sim io press --device button [--button ID] [--line LINE] [--duration-ms N]` | button押下を注入 |
| `gar sim io set --device {button,rfid,range} [--button ID] [--line LINE] [--value VALUE] [--uid UID]` | device値を設定 |
| `gar sim io clear --device rfid` | RFID値を解除 |

`press`、`set`、`clear`も`--workspace NAME`と`--json`に対応する。

### Infrastructure (`gar sim infra`)

| コマンド | 内容 |
|---|---|
| `gar sim infra setup` | AWS Sim HostのTerraform作成計画を確認 |
| `gar sim infra apply` | Terraformを適用し、GAR設定とSSH configを更新 |
| `gar sim infra destroy` | Terraform管理resourceを破棄 |

すべてのactionが`--key-name NAME`、`--region REGION`、`--ssh-cidr CIDR`、
`--auto-approve`に対応する。`apply`と`destroy`は外部resourceを変更するため、対象と課金を確認して実行する。

## 4. 複数workspace system (`gar system`)

| コマンド | 内容 |
|---|---|
| `gar system build [--file PATH] [--json]` | topologyの各nodeを宣言順にbuild |
| `gar system deploy [--file PATH] [--json]` | 各nodeへartifactとruntime環境値を配置 |
| `gar system start [--file PATH] [--json]` | 各nodeを起動 |
| `gar system status [--file PATH] [--json]` | 各nodeの状態を取得 |
| `gar system diag [--file PATH] [--json]` | 各nodeを診断 |
| `gar system test [--file PATH] [--scenario PATH] [--bridge NODE=URL]... [--json]` | 診断、artifact確認、Product所有scenarioを実行 |

`--file`の既定値は`gar-system.json`。topologyとscenarioのschemaは
[アーキテクチャ](02_ARCHITECTURE.md#system-topology-v1)、運用例は
[シミュレーション](06_SIMULATION.md#multi-node-scenario)を参照する。

## 5. Hardware contract (`gar hw`)

| コマンド | 内容 |
|---|---|
| `gar hw init [--dir DIR] [--force]` | Product所有の空のhardware CSV schemaを生成 |
| `gar hw validate [--workspace NAME] [--requirements PATH] [--capabilities PATH] [--binding PATH] [--json]` | Product requirements、Target capabilities、Bindingをoffline検証 |

`hw init --target ID`は互換optionでありCSV schemaには影響しない。`validate`はSSHや実機への
書込みを行わず、適合時0、不適合または入力不正時は非0で終了する。

## 6. 実機 (`gar target`)

| コマンド | 内容 |
|---|---|
| `gar target prepare [--workspace NAME]` | recipe-backed SSH TargetへOS recipeを初回適用 |
| `gar target configure [--workspace NAME] --app NAME --file PATH [--json]` | applicationの永続env設定を配置 |
| `gar target build [--workspace NAME]` | `product-target-build.sh`を実行してTARGET_APP artifactを作成 |
| `gar target preflight [--workspace NAME] [--app NAME] [--json]` | artifactとLinux file-transfer Targetの互換性をread-only検証 |
| `gar target deploy [--workspace NAME] [--json]` | ADB、esptool、SSH/SCP、UUU等で最新artifactを配置またはflash |
| `gar target fetch [--workspace NAME]` | BuildEnvironmentからartifact storeへbundleを取得 |
| `gar target status [--workspace NAME] [--app NAME] [--json]` | lifecycle対応Targetの稼働状態を取得 |
| `gar target log [--workspace NAME] [--app NAME] [--lines N] [--json]` | lifecycle対応Targetの末尾logを取得（既定200行） |
| `gar target diag [--workspace NAME] [--app NAME] [--json]` | healthと稼働build IDを診断 |

`prepare`、`preflight`、`status`、`log`、`diag`は対応capabilityを持たないUUU Targetでは使わない。
UUUの標準フローは`target build`、Board／boot mode／USB／書込み先の人間確認、`target deploy`である。
esptool／UUUの`deploy`は既存dataを失い得る。SSH／ADBでも稼働applicationを置換・restartし得る。

## 7. Legacy WSL2 USB passthrough (`gar usb`)

Windows native UUU／COMでは使わず、Linux版しかないUSB toolをWSL2で実行する既存環境向けである。

| コマンド | 内容 |
|---|---|
| `gar usb list [--json]` | usbipd-winが認識するdeviceを一覧 |
| `gar usb bind [--busid ID] [--match TEXT] [--no-remember]` | deviceをusbipd-winへshare登録 |
| `gar usb attach [--busid ID] [--match TEXT] [--no-remember]` | deviceをWSL2へattach |
| `gar usb detach [--busid ID] [--match TEXT]` | deviceをWSL2からdetach |
| `gar usb status [--busid ID] [--match TEXT] [--json]` | deviceの状態を表示 |

attach中のdeviceはWindows native toolから利用できない。対象deviceを確認してから所有権を移す。

## 8. Terminal bridgeと補助command

| コマンド | 内容 |
|---|---|
| `gar terminal run [--title TITLE] [--cwd DIR] -- COMMAND...` | VS Code integrated terminalへ実行要求を作成 |
| `gar terminal run --command "COMMAND"` | 実行要求を1つのcommand文字列で指定 |
| `gar terminal gc [--keep-days N] [--dry-run]` | 古いterminal request／statusを削除（既定7日） |
| `gar completion bash` | bash completion scriptをstdoutへ出力 |

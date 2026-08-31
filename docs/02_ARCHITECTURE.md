# Gapless Agent Runtime アーキテクチャ

システムは以下の5つのレイヤで構成される。

| レイヤ | 実体 | 役割 |
|---|---|---|
| 1. 統合操作面 | Windows + VSCode + `gar` CLI | AI・人間が共有する操作面。artifact、USB／COM、デプロイの起点 |
| 2. ビルド環境 | Local Docker / GitHub Codespaces | Linux上でProduct hookを実行し、Target別toolchainでartifactを生成 |
| 3. シミュレーション環境 | VirtualBox Ubuntu / AWS Ubuntu / Wokwi / MuJoCo | Productに応じた仮想環境を共通Bridge／lifecycleへ接続 |
| 4. デバイス互換 Runtime | CUSE / gpio-sim + Bridge等 | `/dev/*`またはsimulator APIをProductの外部interfaceへ変換 |
| 5. 実機接続環境 | Raspberry Pi 5 / Luckfox RK3506 / ESP32等 | real deviceで実行。OS準備、flash、boot統合はTarget Packが担当 |

ビルド成果物は、選択したBuildEnvironment（Local Docker / Codespaces）→ host側artifact store →
simulation／実機の一方向で流れる。実行先で場当たり的にbuildしない。Target固有のbuild手順は
Product hook、toolchain／sysroot探索はTarget Packへ置く。

WSLはこのレイヤに含めない。Docker Desktopが内部でWSL2 backendを使う場合も、
GARはDocker capabilityだけを利用する。Linux kernelの`gpio_sim`が必要なlocal simulationは
VirtualBox Ubuntu、remote variantはAWS Ubuntuが担う。

---

## コマンドモデル

GARのコマンドは明示的なlifecycle操作として扱う。ユーザーが入力するのは
`gar sim app build` / `gar sim app deploy` / `gar target build` / `gar target deploy` のような
抽象 target であり、個別の実行方法（PlatformIO、Codespaces、esptool、adb、scp など）は
`gar config` で選ばれた target 定義と接続設定から解決する。

現在の`deploy`は、host側artifact storeにある最新bundleを対象runtimeへ反映する操作であり、
buildやfetchを暗黙には実行しない。新しい成果物が必要な場合は先に`build`を実行し、
既存Codespaces bundleだけを取り直す場合は`fetch`を明示的に実行する。

### System topology v1

複数workspaceで構成されるproductは、`gar-system.json`のproduct-neutralなsystem topologyで表す。
schema v1は2件以上のnode、link、全nodeを一度ずつ列挙する実行`order`を持つ。nodeはworkspace、app、role、
`sim`または`target`のenvironmentを宣言し、linkはfrom/to/protocol/portを持つ。GARはこの宣言から
product固有のPnPやmedia protocolを実装しない。

nodeのruntime environment値はliteral、他nodeのprivate IP、link portだけを明示的に参照できる。
private IPはmachine-local bindingであり、buildでは解決もartifactへの埋込みもしない。deploy/start時にだけ
既存workspace resolverでworkspaceを解決し、sim/target adapterの`configure_system_env(app, values)`へ注入する。
system orchestrationは宣言順に既存`Gar` node APIを呼び、各actionのnode結果・link・failure・exit codeを一つの
構造化reportで返す。`test`は診断に加えてnode healthとartifact store正本のbuild ID/checksumを集約し、
product-owned scenario v1を実行できる。scenarioはmachine-local URLを含まず、topology nodeのappから
Bridgeのread-only `/api/metrics/{application}`を解決する。`--bridge node=origin`だけが実行時overrideである。
scenarioの`assert`はbounded polling、`cleanup`は失敗時にも実行するため、途中でsource runtimeを止めても
再起動を残せる。Bridgeのmetrics readerはsafe application名、regular non-symlink、1 MiB上限、JSON objectを
検査し、metrics pathはruntimeの`/run/gar/metrics`としてsystemdが用意する。
linkからはruntime envに加えてingress/egress firewall planとdiagnostic targetを生成する。
coreはplanを機械可読に返し、OS/infra固有のfirewall適用を暗黙の副作用にはしない。

### Hardware contract v1

実機hardwareは、Product所有の`requirements.json`、Target Pack所有の`capabilities.json`、
Product×Target所有のbindingへ分ける。requirementsはBoardのGPIO番号を知らず、capabilitiesは
Product名や用途を知らない。bindingだけが論理signalをdevice resource、GPIO offset、物理pin、
SPI bus/CS、pinmuxへ割り当てる。Target platformのarchitecture、ABI、toolchain、init system、
privilege modelもcapabilityに含め、READMEだけに閉じた知識にしない。

`gar hw validate`はこの3入力だけを読むoffline boundaryで、SSH、deploy、Target probeを行わない。
schemaとidentityを先に検証し、その後にdevice/driver、電圧、GPIO/SPI競合、SPI速度/mode、video FPSを
照合する。machine-readable reportは実機へ触れる前のCI gateとして使い、実deviceの存在確認は
Target probe/HILという別の境界で行う。

Codespace は BuildEnvironment の実装のひとつ。ユーザーは通常 `gar sim app build` /
`gar sim app deploy` / `gar target build` / `gar target deploy` から間接的に使う。
成果物は target graph の artifact node と `artifact.json` に記載されたパスで管理する。
host側ではworkspace ID・artifact種別・build IDごとに不変snapshotを作り、`latest.json`で
最新snapshotを選ぶ。これにより`SIM_APP`、`SIM_RUNTIME`、`TARGET_APP`が互いに上書きされない。

実機操作も make 的な依存 target として扱う。

```text
target.deploy
  depends on target.artifact
  depends on target.access

target.prepare
  applies target.provisioning recipe through target.access
  owns OS packages, service account and boot integration

target.artifact
  depends on target.build
  depends on target.config

target.build
  depends on target.sources
```

`gar config` は、この graph の各 node が何を意味するかを保存する。たとえば ESP32/M5StickC
なら `target.access` は USB serial 接続先、`target.build` はproduct workspaceの
`product-target-build.sh`をlocalまたはCodespacesで実行する処理、
`target.deploy` は最新 firmware artifact の flash になる。RasPi/Linux device なら
`target.prepare`はTarget manifestのOS recipe適用、`target.deploy`はADBまたは
SSH/scpでの配置になる。Target manifestの`defaultBackends.target`で、これらに加えて
IMX91SのUUUフルイメージ書き込みを選択できる。UUU backendはmanifestの
`provisioning.uuu.command`をargvとして実行し、`deploy.image.files`のイメージを
`{image}`へ展開する（シェル経由では実行しない）。

---

## 1. Windows統合操作面

Gapless Agent Runtimeでは、Windows上のVS Codeと`gar` CLIを、開発者とAIエージェントが
共有する統合操作面として使用する。

ここにすべての情報と操作インタフェースを集約することで**AI が開発作業の最初から最後までを自分で実行できる状態**を実現します。

役割分担は次のように変わります。

| 役割 | Before: 従来の開発環境 | After: Gapless Agent Runtime |
|---|---|---|
| 人間 | SSH接続、データ入力、実機/シミュレータ操作、ログ収集、結果確認、次の手順判断 | AI Agentへの指示、結果の確認、判断 |
| AI Agent | ソフトウェア作成、部分的なコード修正支援 | ソフトウェア作成、SSH接続、デプロイ、データ入力、仮想H/W操作、ログ収集、診断、結果整理 |

この役割変更を実現するために、Gapless Agent Runtimeでは`gar` CLI、JSON scenario、metrics、
log、diagnosticを整備し、build、deploy、仮想H/W操作、確認までを再現可能にする。

OS差はcommand名ではなくcapability adapterで吸収する。Product buildはDocker、
NXP flashはhost native UUU、serial verificationはpyserial、Linux simulationはSSH/SCPを使うが、
ユーザーは同じ`gar ...`を実行する。WindowsにSSH serverを立てて同一host内を往復しない。

### Simulation Control Plane — environment をまたぐ不変条件

シミュレータの物理実装（CUSE/gpio-sim、Wokwi、MuJoCo、Renode など）は environment ごとに異なってよい。しかし **操作と観察の入口は Bridge を通す**。Bridge は状態取得と操作命令を JSON で受け、実際の simulator API / SDK / 仮想デバイス操作へ変換する control plane である。

```text
Human panel / AI agent / CI scenario
              │  HTTP + JSON
              ▼
       Simulator Bridge
              │  environment-specific adapter
              ▼
CUSE/gpio-sim / Wokwi / MuJoCo SDK / Renode
```

このため、Web Panel は Linux 仮想デバイス runtime だけの付属機能ではない。人間向け panel と AI / CI 向け scenario は、同じ Bridge のクライアントである。新しい simulator environment を追加するとき、標準 viewer や environment 固有 UI だけで完結させてはならない。必ず Bridge を持つか、environment 固有の操作 API を GAR の JSON command/state 契約へ変換する adapter を実装する。

Wokwi の自動操作を製品が追加する場合、現状は Wokwi CLI 固有 scenario を使う移行中の例外になる。共有 scenario はまだなく、共通 JSON scenario からの起動は長期的な統一対象である。environment 固有 UI を共通 control plane の代わりと見なさない。

---

## 2. ビルド環境

Local DockerとGitHub CodespacesはBuildEnvironmentのproviderである。どちらもProduct workspaceが
所有する`product-*-build.sh`をLinux上で実行し、同じartifact contractへcaptureする。
Local Dockerの既定imageは`infra/build/`から作成する。

### GitHub Codespaces

Gapless Agent Runtime では、開発環境として GitHub Codespaces を採用しています。

Codespaces により、ローカルPCのOSやインストール済みツールに依存せず、セットアップ済みの開発環境を瞬時に起動できます。開発環境を IaC 的に定義しておくことで、チームメンバ全員に同じ依存関係、同じツールチェーン、同じコマンド体系を提供できます。

Gapless Agent Runtime では、その標準化された作業場に AI Agent も参加します。AI は人間のローカルPC固有の環境に依存せず、チームで共有された開発環境の中でビルド、デプロイ、実行、観察を行います。

---

## 3. シミュレーション環境

Linux device simulationは`ssh_remote`というruntime種類と、それを載せるSim Host providerを分ける。

```text
Linux systemd simulation runtime
    ├─ Local Ubuntu (VirtualBox) ── x86_64既定
    └─ Remote Ubuntu (AWS EC2) ── aarch64既定
```

VirtualBoxとAWSは別のsimulatorではない。共通のUbuntu bootstrap、SSH／SCP、systemd runtime、
Bridgeを使う。ローカルで`gpio_sim`が必要な場合はVirtualBox Ubuntuを使い、
AWSは同じruntimeをremoteで実行するvariantである。host lifecycleの差は
`simulation/host/virtualbox.py`と`aws_ec2.py`に閉じる。

### Architectureの契約

Linux ARM64のreference simulationにはAWS EC2 Gravitonを採用している。Raspberry Pi 5と同じ
**ARM64 (aarch64)／glibc** envelopeを満たすProductでは、同一binaryをdeployできる。
x86 CPU emulationを挟まず実速で動かせる一方、kernel、driver、device、timingの同一性は別途検証する。
VirtualBox x86_64とAWS aarch64の間でbinaryを流用せず、artifact metadataのarchitectureと
選択中のSim Hostをdeploy前に照合する。WokwiとMuJoCoは別のSimulationEnvironmentとして
同じ上位操作へ接続する。Dockerは標準ではBuildEnvironmentである。

---

## 4. デバイス互換 Runtime

### 仕組み：アプリを無改造で動かす

アプリ側に `#ifdef SIMULATION` やシミュレーション専用 HAL を持たせない。アプリは実機と同じ `/dev/i2c-1`、`/dev/spidev0.0`、`/dev/gpiochip0` を開くだけにし、差し替えの責務を OS/device layer に閉じ込める。

VirtualBox／AWSのUbuntu Sim Host上では以下の仮想デバイスで`/dev/*`を再現する。

| I/F | 実装 | アプリから見えるもの |
|---|---|---|
| I2C | CUSE で `/dev/i2c-1` を生成 | 実機と同じ i2c-dev |
| SPI | CUSE で `/dev/spidev0.0` を生成 | 実機と同じ spidev |
| GPIO | `gpio-sim` で `/dev/gpiochip0` を提供 | 実機と同じ GPIO chardev v2 |

### 実装パリティ

同一binaryはarchitecture、ABI、libcが一致する場合の強い形である。Raspberry Pi 5とarm64 EC2では
これを利用できる。RK3506のようなarmv7 Targetでは別binaryをbuildし、同じsource、Linux device I/F、
protocol、state behaviorを契約にする。accelerator固有実装では外部behaviorと性能条件で適合を確認する。

CUSE／gpio-simの実装と保守はAIと自動testが担い、実機で得た差分をruntime provider、Target capability、
Bindingへ戻す。

### 仮想 H/W の操作・観察（bridge）

仮想デバイスへの操作・観察は、人間の手動操作と AI / CI の再現操作で入口を分ける。

* **Virtual Hardware Panel**: LED・ボタン・RFID・センサーの状態変化を WebSocket 経由でブラウザパネルにリアルタイム表示。人間が目視で動作確認できる。
* **JSON シナリオ試験**: ボタン押下・RFID タップ・センサー値変更・状態確認を JSON シナリオとして定義し、AI や CI が同じ手順を再現可能なテストとして実行できる。
* **HTTP API（bridge）**: Linux / RasPi-compatible simulation の内部受け口。Web UI と JSON シナリオ実行系が同じ仮想 H/W 操作ロジックを通るため、UI 変更時のメンテ漏れが起きにくい。

物理的な検証実装は simulation environment ごとに分かれるが、上記 control plane の観点では、いずれも Bridge の背後に置く。

| 対象 | 入口 |
|---|---|
| Linux Bridge 手動操作 | Virtual Hardware Panel |
| Linux Bridge 単一nodeシナリオ | `python scripts/run_scenario.py path/to/scenario.json` |
| 複数node Golden scenario | `gar system test --scenario ... --bridge node=origin --json` |
| Wokwi 手動確認 | VS Code Wokwi 拡張 / Diagram Editor |
| Wokwi 自動確認 | 共有scenarioは未提供。製品がscenarioをartifactへ含めた場合だけ`wokwi-cli --scenario`を使用 |
| MuJoCo | `gar sim runtime start --no-port-forward`（start時にmodelを検証） |
| ESP32 QEMU | setup選択肢とerror-only runtimeのみ。`gar-esp32-flash-image` / `gar-esp32-qemu-run`はgar-tools側の手動検証入口 |
| Renode | setup選択肢とerror-only runtimeのみ。`renode` / `renode-test`は手動検証入口 |

WokwiとMuJoCoのlocal processは共通のstate storeを使う。stateはatomicに置換し、
start/stopはfile lockで直列化する。停止時はPIDだけでなくargvと`/proc` start timeを照合し、
PID再利用で無関係なprocessを停止しない。MuJoCoのproduct assetは`gar sim app deploy`で
`.gar/mujoco/`へmaterializeしてからmodelを検証する。

具体的なセットアップ手順と確認手順は [06_SIMULATION.md](06_SIMULATION.md) を参照。

---

## 5. 実機接続環境

Gapless Agent Runtimeでは、AIが実機へ到達する接続経路をTargetごとに選ぶ。
Raspberry Pi 5 / Raspberry Pi OSは**SSH/scp + systemd recipe**、Luckfox Lyra Plus RK3506は
**SSH/scp + Buildroot／BusyBox recipe**をreferenceとする。

ADBはUSBだけで到達したいLinux Target、esptoolはESP32のflashなど、別Target/backendの
選択肢として残します。ADB / serial / SSHの切り替えと接続先はworkspaceごとに保存されるため、
AIも人間も同じ設定で動作します。複数経路を同時に混在させず、選択中backendを正本にします。

### Target/OS provisioningの境界

SSH実機のroot管理領域、package manager、service account、init systemはOSごとに異なる。
そのため`gar target prepare`は共通の操作入口だけを提供し、実処理は
`gar-tools/targets/<id>/target.json`の`provisioning`からTarget所有recipeを解決する。
Runtime本体はdistribution名で分岐しない。

applicationの観測とdeploy後収束も同じ境界に従う。Target manifestが
`gar-app-lifecycle-v1` capabilityを宣言し、recipeが導入するhelperへ
`status / log / health / reload / running-build-id`を委譲する。GAR coreはこの共通語彙と
exit codeだけを扱い、systemdやBusyBox init、product固有health hookの実装を持たない。

実機artifactのschema v2はsource/gar-tools commit、Target recipe version、architecture、
ABI/libc、entrypoint、build ID、file checksumをsnapshotへ固定する。`gar target prepare`は
適用したTarget ID、recipe version、gar-tools commitをroot所有の
`/etc/gar/recipe-version`へ記録する。deploy時はworkspaceでbuildに使ったidentity、現在の
gar-tools copy、実機へ適用済みidentity、実測architecture/ABI/kernelを転送前に比較する。
dirtyなsource/tools、legacyまたはchecksum不一致の実機artifact、いずれかのidentity driftは
再build/prepareが済むまで安全側で拒否する。legacy simulation artifactの読込み互換は維持する。

Raspberry Pi OS/systemdのreference contractでは、recipeが限定sudo installerと
root所有の`gar-app@.service`を導入する。product artifactは
`/opt/gar/apps/<app>/run`を提供し、serviceは非rootの`gar`accountで動く。
永続設定`/etc/gar/<app>.env`、SSH host key、userのauthorized_keysはapplication
artifactの責務外である。`gar target configure`だけがrecipe-backed SSH Targetの限定installerを
通じてenv fileを原子的に更新し、通常deployでは削除・上書きしない。read-only rootfsや
full-image flashingを使うTargetは、同じ上位lifecycleへ別recipe／backendを追加する。

NXP UUU等のUSB recoveryはapplication deployと副作用が異なるため、Target Packがboot mode、
USB identity、image destination、verify、recoveryを明示する独立provisioning classとして扱う。
FRDM-IMX91SではUUUのdownload USB接続とUSB-C debug UARTを別接続として扱い、
`target.serial`にコンソールdeviceを設定すると書き込み後の起動パターン確認を行える。

Windows操作面ではTarget layerがartifact／recipeの判定を持ち、access layerがhost nativeの
`uuu.exe`起動とpyserial `COMn`を担う。標準経路はWindowsがUSBを所有するため、
WSLへのusbipd attach／detachは不要である。`gar usb`はLinux-only USB tool用のlegacy compatibilityとして残す。

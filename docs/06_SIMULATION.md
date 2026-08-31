# シミュレーション環境

GARのSimulationEnvironmentは、実装の異なるsimulatorを共通のartifact、lifecycle、Bridge、
diagnostic契約へ接続する。Product固有の操作や状態遷移はGARへ実装せず、Productが所有する
scenarioから共通control planeを利用する。

## 階層

Linux device simulationでは、runtimeとhost providerを分ける。

```text
BuildEnvironment (Local Docker / Codespaces)
    ├─ SIM_RUNTIME artifact
    └─ SIM_APP artifact
              │ deploy over SSH/SCP
              ▼
SimulationEnvironment: ssh_remote / Linux systemd runtime
              │
              ├─ Sim Host: VirtualBox Ubuntu (local)
              └─ Sim Host: AWS Ubuntu        (remote)
```

VirtualBoxとAWSは異なるsimulatorではない。共通のUbuntu bootstrap、Linux device runtime、
SSH／SCP、Bridge契約を使う。providerの差はVM lifecycle、address解決、architectureだけである。

- VirtualBox: localの`VBoxManage`でVMを起動／停止。Ubuntu x86_64が既定。
- AWS EC2: AWS APIでinstanceを起動／停止しSSH addressを更新。Graviton aarch64が既定。

architectureが異なるため、Sim Hostを切り替えた後は対応するSIM artifactを再buildする。
GARはartifact metadataと選択中のSim Host architectureが不一致なdeployを拒否する。

## 共通契約

```text
SIM_RUNTIME artifact ── deploy ── runtime provider / Bridge
SIM_APP artifact     ── deploy ── Product application
                                      │
Human Panel / AI / CI ── JSON ───────┘
```

Simulation runtimeは次を提供する。

- `build`／`deploy`
- `start`／`stop`／`status`／`log`／`diag`
- remote hostのsession／port forward
- 仮想I/Oの操作と状態観測
- AI／CI向けの機械可読diagnostic

`gar sim app deploy`はProduct application、`gar sim runtime deploy`はdevice providerやBridgeを配置する。
両artifactは別snapshotであり、一方のbuildが他方を上書きしない。

## Backendの現在地

| SimulationEnvironment | Sim Host | 状態 |
|---|---|---|
| `ssh_remote` | `virtualbox` | Linux systemd runtimeとVirtualBox controllerを実装 |
| `ssh_remote` | `aws_ec2` | 同じruntimeとAWS EC2 controllerを実装 |
| `wokwi` | hostless local process | Product所有Wokwi project／firmwareを起動 |
| `mujoco` | hostless local process | Product modelをmaterializeしMuJoCo processを起動 |
| `renode_mcu` | hostless | installer／選択肢とerror-only runtime |
| `esp32_qemu_firmware` | hostless | installer／選択肢とerror-only runtime |
| `aws_ssm` | AWS | installer／選択肢とerror-only runtime |

`local_docker`のSimulationEnvironmentは旧workspace／testとの互換のため残るが、`gar config`の
標準simulation選択肢ではない。Dockerは標準ではBuildEnvironmentであり、`gpio_sim`の
local Sim HostはVirtualBox Ubuntuである。未実装backendを選んだ場合は別backendへfallbackしない。

### Legacy local Docker設定

明示的に`local_docker`を選んだ既存workspaceでは、Target Packの
`gar-tools/targets/<id>/target.json`に`simulation.docker`を宣言する。workspaceの`docker`設定は
machine-localな上書きに限る。

```json
{
  "docker": {
    "container": "gar-sim",
    "image": "gar-linux-device:latest",
    "bridge_port": 18080
  }
}
```

これらはすべて省略でき、指定した値だけがTarget Packの宣言を上書きする。Target Pack側は次の形である。

```json
{
  "simulation": {
    "docker": {
      "image": "gar-linux-device:latest",
      "buildContext": "targets/linux-device",
      "publishedBridgePort": 8080,
      "containerBridgePort": 8080,
      "publishedHost": "127.0.0.1",
      "init": ["/sbin/init"],
      "privileged": true,
      "hostCgroups": true,
      "environment": ["GAR_BRIDGE_HOST=0.0.0.0"],
      "tmpfs": ["/run", "/run/lock"],
      "mounts": ["/sys/kernel/config:/sys/kernel/config"],
      "devices": ["/dev/fuse", "/dev/cuse"]
    }
  }
}
```

`buildContext`があればcontainer作成前にimageをbuildする。`publishedBridgePort`はhost側、
`containerBridgePort`はcontainer内、`publishedHost`の既定値は`127.0.0.1`である。
legacy `bridgePort`は両portへ同じ値を設定する互換形式として読む。containerはhost kernelを
共有するため、`gpio-sim`にはLinux 5.17以降のhost kernelが必要である。

### Simulation artifactのarchitecture

`gar sim app build`と`gar sim runtime build`は、実行先に合わせた値をProduct hookへ渡す。

| Simulation Environment / Host | `GAR_SIM_ARCH` | `CC` |
|---|---|---|
| `local_docker` | host architecture（`docker.arch`で上書き） | `gcc` |
| `ssh_remote` + `virtualbox` | `x86_64`（`simulation_host.arch`で上書き） | `x86_64-linux-gnu-gcc` |
| `ssh_remote` + `aws_ec2` | `aarch64`（`simulation_host.arch`で上書き） | `aarch64-linux-gnu-gcc` |

`GAR_SIM_ENVIRONMENT`にはSimulationEnvironment IDを渡す。`gar target build`にはこれらを渡さない。

## Linux device compatibility runtime

Linux simulationではApplicationへ`#ifdef SIMULATION`を入れず、実機と同じdevice I/Fを提供する。

| I/F | Simulation実装 | Applicationから見えるもの |
|---|---|---|
| GPIO | kernel `gpio-sim` | GPIO chardev v2 `/dev/gpiochip*` |
| I2C | CUSE provider | `/dev/i2c-*` |
| SPI | CUSE provider | `/dev/spidev*` |
| Video input | V4L2-compatible provider | `/dev/video*` |
| UI／操作 | Web Bridge + Panel | HTTP／WebSocket／JSON |

ApplicationはBridgeを直接importしない。device I/FまたはProduct protocolだけを使用し、Bridgeは
仮想deviceの背後から操作と観測を行う。

```text
Application ── ioctl/read/write ── /dev/* provider
                                      │
Browser / scenario ── HTTP/JSON ── Web Bridge
```

runtimeのsystem領域はTarget Packのmanifest／artifactで管理し、Product binaryや設定と混ぜない。
実機にはsimulation providerやPanelをdeployしない。

## Bridge契約

Bridgeは人間向けPanelだけのHTTP serverではない。Human UI、AI、CIが共有するcontrol planeである。

- virtual GPIO／rotary／sensor等の操作
- framebufferやdevice stateの観察
- runtime health
- `/api/metrics/<application>`によるProduct telemetry取得
- scenario assertionの受け口

metrics fileはruntime側の限定directoryに置き、application名、regular file、size、UTF-8、JSON objectを
検証する。scenarioはmachine-local URLを保持せず、実行時の`--bridge node=origin`から解決する。

新しいsimulatorを追加する場合、固有viewerだけで完了にしない。固有APIをGARのJSON
command／stateへ変換するBridge adapterを用意する。

## VirtualBox local Sim Hostの初回準備

人間がmachineごとに一度行う。

1. VirtualBoxへUbuntu VMを作り、host-only networkまたはNAT port forwardでWindowsからSSH可能にする。
2. `infra/simulation-host/ubuntu-bootstrap.sh`をroot権限で実行する。
3. `sudo modprobe gpio-sim`と`/sys/kernel/config`の利用可否を確認する。
4. Windowsの`%USERPROFILE%\.ssh\config`へ固定Host aliasとkeyを登録し、host keyを確認する。
5. `gar config`でSimulation Environmentに`SSH Remote`、Sim Hostに`Local Ubuntu (VirtualBox)`を選ぶ。
6. VM名／UUIDとSSH aliasを保存する。

詳細とSSH config例は[`infra/virtualbox/README.md`](../infra/virtualbox/README.md)を参照する。
VM名、IP、SSH keyはrepositoryへcommitしない。

## 標準操作

VirtualBoxでもAWSでも同じである。

```bash
gar sim host start --workspace Local/Product
gar sim host status --workspace Local/Product
gar sim runtime build --workspace Local/Product
gar sim runtime deploy --workspace Local/Product
gar sim app build --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

停止:

```bash
gar sim runtime stop --workspace Local/Product
gar sim host stop --workspace Local/Product
```

`runtime start`はruntime serviceとport forwardを開始する。port forward不要時は
`--no-port-forward`を使う。VirtualBox providerの`host stop`はACPI shutdownを要求し、
AWS providerはinstance stopを要求する。いずれもOSが停止したことをstatusで確認する。

## AWS hostとTerraform

`gar sim infra`はAWS EC2 provider用のTerraform reference implementationであり、
VirtualBox VMの作成commandではない。

```bash
gar sim infra setup
gar sim infra apply
# 不要になったinfraを明示的に破棄する場合だけ:
gar sim infra destroy
```

infraはVM、network、storage、bootstrapを所有する。Application／runtime artifactの配置とstartは
`gar sim app`／`gar sim runtime`が所有する。cloud login、region、instance type、課金、
`apply`／`destroy`は人間が確認する。

## WokwiとMuJoCo

WokwiはProduct hookがtemplate、firmware、diagram、`wokwi.toml`をSIM_APP artifactへまとめる。
`gar sim app deploy`がruntime workspaceへ展開し、`start`が配置済みprojectを検証して起動する。
現状の自動scenarioはProduct所有のWokwi形式で、Linux Bridge共通scenarioとは統一途中である。

MuJoCo runtimeはProduct artifactに含まれるmodelとassetをlocal workspaceへmaterializeする。
absolute path、`~`、path traversalを拒否し、modelを検証してからprocessを起動する。

Wokwi／MuJoCoのlocal process lifecycleはWindowsとPOSIXの両方でprocess identityを確認する。
PIDだけで無関係なprocessを停止せず、commandとprocess create timeを照合する。

## Multi-node scenario

複数workspaceは`gar-system.json`でnodeとlinkを宣言する。system scenarioはProductが所有し、GARは
node lifecycle、metrics取得、bounded assertion、cleanupを実行する。

```bash
gar system test \
  --file /path/to/gar-system.json \
  --scenario /path/to/scenario.json \
  --bridge node-a=http://127.0.0.1:8081 \
  --bridge node-b=http://127.0.0.1:8080 \
  --json
```

## 診断順序

1. `gar sim host status`
2. `ssh <simulation_host.host> true`
3. `gar sim runtime diag --json`
4. artifact architecture／build ID／checksum
5. runtime serviceとdevice node
6. Bridge health／metrics freshness
7. Application log
8. Product protocol／scenario assertion

| 症状 | 主な確認点 |
|---|---|
| VirtualBox VMが起動しない | `VBoxManage showvminfo`、VM名／UUID、VirtualBox service |
| runtimeへ接続できない | SSH config Host、VM network、host key、AWS address更新 |
| architecture mismatch | VirtualBox／AWS切替後にSIM_RUNTIMEとSIM_APPを再build |
| device nodeがない | bootstrap、kernel module、`gpio_sim`、runtime service／hardware binding |
| Panelだけ更新されない | Bridge WebSocket、device provider、browser cache |
| scenarioが即座に偽PASS | metric初期化、before／after比較、process restart |
| deploy後も古い挙動 | artifactとrunning build ID、service restart |
| 未実装error | 選択backendがerror-onlyか[検証状態](07_VERIFICATION.md)で確認 |

VirtualBox controllerやWindows process adapterがunit testで検証されていても、実VMのnetwork、
kernel module、USB deviceまで自動的に確認済みにはならない。[検証状態](07_VERIFICATION.md)を参照する。

## 低レベルport forward

通常は`gar sim runtime start`／`stop`がHardware Panel用port forwardを管理する。接続だけを
切り分けて診断する場合は、GAR core repositoryで次のMake wrapperを使える。

| コマンド | 内容 |
|---|---|
| `make port-forward SIM_HOST=HOST` | 指定Sim Hostへのport forwardを開始 |
| `make port-forward-stop SIM_HOST=HOST` | port forwardを停止 |
| `make port-forward-status SIM_HOST=HOST` | port forward状態を確認 |

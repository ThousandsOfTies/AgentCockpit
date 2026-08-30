# シミュレーション環境

GARのSimulationEnvironmentは、実装の異なるsimulatorを、共通のartifact、lifecycle、Bridge、
diagnostic契約へ接続する。Product固有の操作や状態遷移はGARへ実装せず、Productが所有する
scenarioから共通control planeを利用する。

## 共通契約

```text
SIM_RUNTIME artifact ── deploy ── runtime provider / Bridge
SIM_APP artifact     ── deploy ── Product application
                                      │
Human Panel / AI / CI ── JSON ────────┘
```

Simulation runtimeは次を提供する。

- `build`／`deploy`
- `start`／`stop`／`status`／`log`／`diag`
- environmentがremote hostを持つ場合のsession／port forward
- 仮想I/Oの操作と状態観測
- AI／CI向けの機械可読diagnostic

`gar sim app deploy`はProduct application、`gar sim runtime deploy`はdevice providerやBridgeを
配置する。両artifactは別snapshotであり、一方のbuildが他方を上書きしない。

## Backendの現在地

| Environment | Runtime | 状態 |
|---|---|---|
| `ssh_remote` | Linux systemd runtimeをSSH hostへ配置 | 実装済み。EC2 Gravitonがreference |
| `wokwi` | Product所有のWokwi project／firmwareをlocal processで実行 | 実装済み |
| `mujoco` | Product modelをmaterializeしMuJoCo processを実行 | 実装済み |
| `renode_mcu` | installerと選択肢 | runtime未実装を明示するerror-only adapter |
| `esp32_qemu_firmware` | installerと選択肢 | runtime未実装を明示するerror-only adapter |
| `aws_ssm` | installerと選択肢 | runtime未実装を明示するerror-only adapter |

`local_docker`の実装とtarget側のDocker設定は、明示的なbuild/UTまたは既存workspaceとの互換性のために
残しています。ただし、`gar setup`のsimulation選択肢には含めません。

未実装backendを選んだ場合、別backendへ暗黙fallbackしない。

## Linux device compatibility runtime

Linux simulationでは、Applicationへ`#ifdef SIMULATION`を入れず、実機と同じdevice I/Fを提供する。

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

新しいsimulatorを追加する場合、固有viewerだけで完了にしない。固有APIをGARのJSON command／stateへ
変換するBridge adapterを用意する。固有UIは人間向けclient、共通scenarioはAI／CI向けclientである。

## 標準操作

```bash
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
```

remote hostを使用する場合:

```bash
gar sim host start --workspace Local/Product
gar sim host status --workspace Local/Product
gar sim host stop --workspace Local/Product
```

Linux runtimeの`start`はruntime serviceとport forwardを開始する。port forward不要時は、対応する
commandの`--no-port-forward`を使用する。正確なoptionは`gar sim ... --help`を正本とする。

## EC2 hostとTerraform

`gar sim infra`はTerraformを使うreference implementationであり、application deployとは別の責務である。

```bash
gar sim infra setup
gar sim infra apply
# 不要になったinfraを明示的に破棄する場合だけ:
gar sim infra destroy
```

infraはVM、network、storage、bootstrapを所有する。Application／runtime artifactの配置とstartは
`gar sim app`／`gar sim runtime`が所有する。

SSH／AWS loginに人間入力が必要な場合、GARは無限再試行せず、Terminal Bridgeへ認証操作を引き渡す。
認証後に元のcommandを再実行する。

## Wokwi

WokwiはProduct hookがtemplate、firmware、diagram、`wokwi.toml`をSIM_APP artifactへまとめる。
`gar sim app deploy`がruntime workspaceへ展開し、`start`が配置済みprojectを検証して起動する。

現状の自動scenarioはProduct所有のWokwi形式であり、Linux Bridgeの共通scenarioとは統一されていない。
この例外を、全backendが対応済みであるかのように扱わない。

## MuJoCo

MuJoCo runtimeはProduct artifactに含まれるmodelとassetをlocal workspaceへmaterializeする。
absolute path、`~`、path traversalを拒否し、modelを検証してからprocessを起動する。

Wokwi／MuJoCoのlocal process lifecycleは、PIDだけでなくcommandとprocess start timeを照合し、
stale stateによって無関係なprocessを停止しない。state更新とstart／stopはatomic／排他的に行う。

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

scenarioは`command`、`observe`、`assert`、`wait`を持ち、失敗時も`cleanup`を実行する。
counterは前回runの値で偽PASSしないよう、process再起動またはbefore／after比較で評価する。

## 診断順序

問題が起きたら、次の順に境界を狭める。

1. `gar sim host status`
2. `gar sim runtime diag --json`
3. artifact build ID／checksum
4. runtime serviceとdevice node
5. Bridge health／metrics freshness
6. Application log
7. Product protocol／scenario assertion

| 症状 | 主な確認点 |
|---|---|
| runtimeへ接続できない | SSH config Host、host状態、認証session |
| device nodeがない | runtime service、kernel module、hardware binding |
| Panelだけ更新されない | Bridge WebSocket、device provider、browser cache |
| scenarioが即座に偽PASSする | metricの初期化、before／after比較、process restart |
| deploy後も古い挙動 | artifactとrunning build ID、service restart |
| 未実装errorが出る | 選択backendがerror-onlyか[検証状態](07_VERIFICATION.md)で確認 |

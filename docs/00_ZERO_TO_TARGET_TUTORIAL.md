# 0から実機動作までのチュートリアル

この文書は、Product workspaceをGARへ登録し、simulationで確認してからPhysical Targetへ
deployする標準経路を示す。個々の引数は[コマンドリファレンス](01_COMMAND_REFERENCE.md)、
環境ごとの差は[開発環境](03_DEVELOPMENT_ENVIRONMENT.md)と[シミュレーション](06_SIMULATION.md)を参照する。

## ゴール

```text
Product workspace
  → build artifact
  → simulation deploy / diag
  → target preflight
  → physical deploy / diag
```

複数node製品では、最後に`gar system test`でE2E scenarioを実行する。

## 前提

- LinuxまたはWSL2からrepositoryを操作できる。
- Python 3、Git、対象environmentに必要なCLIを導入できる。
- Product workspaceにbuild hookとsourceが存在する。
- Target Packは`gar-tools`にあり、Product固有hardware bindingはProduct workspaceにある。
- 実機配線はProductのbinding／配線資料と、Target Packのpin／電圧資料を突き合わせて行う。

GAR本体はProduct固有の配線図を持たない。Board capabilityは`gar-tools/targets/<target-id>/`、
実際の部品と配線はProduct workspaceを正本とする。

## 1. GARを初期化する

```bash
cd /path/to/GaplessAgentRuntime
make init
make start
```

`make init`はlocal venv、`gar` entrypoint、VS Code Terminal Bridge、MCP設定を用意する。
日常操作は`make`ではなく`gar`を使用する。

## 2. Workspaceとenvironmentを設定する

```bash
gar setup
```

対話では次を選択・入力する。

1. Product workspaceのpathと表示名
2. Target Pack
3. BuildEnvironment（LocalまたはGitHub Codespaces）
4. SimulationEnvironment
5. TargetEnvironment
6. SSH config Host、serial port等のmachine-local接続情報

設定はGaplessAgentRuntime直下の`.gar/config.json`へ保存される。秘密鍵そのものやProductの
runtime secretは保存しない。登録後はworkspace名を確認する。

```bash
gar setup --no-install
```

`--no-install`は不足commandを表示するだけで、導入処理を実行しない。

## 3. Hardware contractを検証する

Productにhardware contractがある場合、実機へ触れる前にoffline検証する。

```bash
gar hw validate --workspace Local/Product --json
```

検証対象は次の三つである。

- Product所有の`requirements.json`
- Target Pack所有の`capabilities.json`
- Product×Target所有のbinding

ここではschema、device、driver、電圧、GPIO／SPI競合、速度、video FPS等を確認する。
実Target上のdevice存在確認は後段の`preflight`／`diag`で行う。

## 4. Simulation artifactをbuildする

```bash
gar sim runtime build --workspace Local/Product
gar sim app build --workspace Local/Product
```

選択したBuildEnvironmentがProduct hookを実行し、WSL側artifact storeへsnapshotを作る。

```text
.gar/artifacts/<workspace-id>/sim_runtime/<build-id>/
.gar/artifacts/<workspace-id>/sim_app/<build-id>/
```

buildとdeployは別操作である。deployはbuildやfetchを暗黙に実行しない。

Codespacesを明示的に起動・接続する必要がある場合は次を使う。

```bash
gar code boot --workspace Local/Product
gar code start --workspace Local/Product
gar code status --workspace Local/Product
```

## 5. Simulationを起動する

host lifecycleを持つenvironmentでは先にhostを起動する。

```bash
gar sim host start --workspace Local/Product
gar sim host status --workspace Local/Product
```

runtimeとapplicationを配置する。

```bash
gar sim runtime deploy --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

`diag`の`ok`だけでなく、service、device、Bridge、application health、build IDを確認する。
仮想I/O操作はBridge経由で行う。

```bash
gar sim io press --workspace Local/Product --device button --line 17
gar sim runtime log --workspace Local/Product
```

使用可能なdevice／引数はTarget Packと`gar sim io --help`を参照する。

## 6. 複数node systemを検証する

Productに`gar-system.json`がある場合は、nodeを個別に操作せずsystem単位で実行できる。

```bash
gar system build --file /path/to/gar-system.json --json
gar system deploy --file /path/to/gar-system.json --json
gar system start --file /path/to/gar-system.json --json
gar system diag --file /path/to/gar-system.json --json
gar system test \
  --file /path/to/gar-system.json \
  --scenario /path/to/scenario.json \
  --bridge tx=http://127.0.0.1:8081 \
  --bridge rx=http://127.0.0.1:8080 \
  --json
```

Bridge URLはmachine-local入力なので、system schemaやartifactへ埋め込まない。

## 7. Physical Targetを準備する

初回またはTarget recipe更新時にだけ実行する。

```bash
gar target prepare --workspace Local/Product
```

`prepare`の内容はTarget Packが所有する。Raspberry Pi OSではsystemdと限定sudo、RK3506
BuildrootではBusyBox initとroot helperを設定する。GAR coreはdistribution名で分岐しない。

永続的なProduct設定が必要なら、deployとは分けて明示する。

```bash
gar target configure \
  --workspace Local/Product \
  --app product-app \
  --file /path/to/product-app.env \
  --json
```

通常のapplication deployは`/etc/gar/<app>.env`、SSH鍵、host keyを上書きしない。

## 8. Target artifactをbuildして事前検証する

```bash
gar target build --workspace Local/Product
gar target preflight --workspace Local/Product --json
```

`preflight`はartifactを転送せず、次を読み取り専用で照合する。

- artifact checksumとprovenance
- Target ID、architecture、ABI、libc、toolchain triple
- active gar-toolsと適用済みrecipeのidentity
- deploy／configure／lifecycle capability

不一致を無視してdeployしない。source、gar-tools、recipeのどれを更新すべきか診断結果から判断する。

## 9. 実機へdeployして収束を確認する

```bash
gar target deploy --workspace Local/Product
gar target status --workspace Local/Product --json
gar target diag --workspace Local/Product --json
gar target log --workspace Local/Product
```

deploy成功の基準は転送完了ではない。applicationがhealthを満たし、running build IDが
配置artifactのbuild IDと一致することを確認する。

## 10. USB TargetをWSLへ接続する場合

Windows側USBを必要とするTargetでは、対象を確認してからattachする。

```bash
gar usb list
gar usb attach --busid <busid>
gar usb status
```

USB attachとimage flashは物理状態を変更するため、対象deviceを推測して実行しない。

## 11. 終了

```bash
gar sim runtime stop --workspace Local/Product
gar sim host stop --workspace Local/Product
gar code stop --workspace Local/Product
gar code shutdown --workspace Local/Product
```

Physical Targetの停止はBoard固有であり、GARのapplication lifecycleと電源操作を混同しない。

## よくある失敗

| 症状 | 最初に確認すること |
|---|---|
| workspaceを選べない | `gar setup`の登録pathと現在directory |
| artifactがない | 対応する`build`または`fetch`を実行したか |
| SSH接続に失敗 | `ssh <config-host> true`、host key、認証session |
| `preflight`がidentity drift | source／gar-toolsを同期して再build、recipe更新なら再prepare |
| deploy後も古い挙動 | `gar target diag --json`のexpected／running build ID |
| simulation deviceがない | `gar sim runtime diag --json`のservice／device状態 |
| scenarioが失敗 | node health、Bridge URL、metrics freshness、cleanup結果 |
| 実機I/Oがない | Product binding、pinmux、kernel driver、電源、物理配線 |

検証済み範囲と未実装backendは[検証状態](07_VERIFICATION.md)を参照する。

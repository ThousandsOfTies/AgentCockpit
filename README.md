# Gapless Agent Runtime

**コーディングからシミュレーション、実機稼働までを、AIエージェントが同じ操作面で進めるための組み込み開発基盤。**

Gapless Agent Runtime（GAR）は、Build環境、Simulation環境、Physical Targetを
`gar` CLIから操作し、成果物、診断結果、実行手順を環境間で受け渡します。人間が担当するのは
製品要件、物理作業、認証、危険な操作の承認であり、反復可能なbuild／deploy／observeは
AIとCIが担える形にします。

```text
Product source
    │ product build hook
    ▼
BuildEnvironment（Local / Codespaces）
    │ schema-v2 artifact snapshot
    ▼
WSL control plane
    ├─ SimulationEnvironment ── Bridge / metrics / scenario
    └─ TargetEnvironment     ── preflight / deploy / lifecycle / diag
```

## 実装の中心

- **不変artifact**: workspace、用途、build IDごとにsnapshot化し、source／toolchain／Target recipe／checksumを記録します。
- **Target Pack**: Board／OS／toolchain／provisioning／lifecycleの知識を`gar-tools/targets`へ蓄積します。
- **Hardware contract**: Product requirements、Target capabilities、Product×Target bindingを分離し、実機接続前に検証します。
- **System topology**: 複数workspaceのnodeとlinkを宣言し、build、deploy、start、diag、scenarioを一つのsystemとして実行します。
- **共通観測面**: 人間向けPanelとAI／CI向けJSON scenarioが、同じBridgeとmetricsを利用します。

「同じ実装」はTargetに応じて段階を分けます。同じarchitecture／ABIなら同一binaryを利用できます。
異なるarchitectureでは、同じsource、device interface、protocol、state behaviorを保ち、Target別toolchainでbuildします。

## 現在のreference経路

| 役割 | 実装・確認対象 |
|---|---|
| Control plane | VS Code + WSL2 |
| Build | Local、GitHub Codespaces |
| Linux simulation | Local Docker、AWS EC2 Graviton + CUSE／gpio-sim／Web Bridge |
| Physical Target | Raspberry Pi 5／Raspberry Pi OS、Luckfox Lyra Plus RK3506／Buildroot |
| Firmware flash | ESP32 + esptool backend |
| Multi-node reference | GarStreamTx/Rx topology + Golden scenario |

確認済み範囲と未実装部分は[検証状態](docs/07_VERIFICATION.md)を正本とします。

## 最初の起動

```bash
make init
make start
gar setup
```

Product workspaceには、少なくとも次を置きます。

```text
ProductWorkspace/
  scripts/
    product-sim-build.sh
    product-sim-env-build.sh
    product-target-build.sh
  hardware/
    requirements.json
    bindings/<target-id>.json
  gar-system.json             # 複数node製品の場合
  sources/                    # app／gar-toolsの固定済みsource
```

新しいworkspaceの雛形は、`gar-build-env`にあるstandalone scriptから作成できます。

```bash
scripts/create-product-devspace.sh ProductName \
  https://github.com/example/product-source \
  --destination /path/to/ProductName
```

Target固有資産はGAR本体へ追加せず、`gar-tools`のTarget Packへ置きます。Product固有の
device要件、周辺部品、配線、menuやprotocolはTarget Packへ混ぜず、Product requirements、
Peripheral adapter、bindingへ置きます。

## 標準フロー

Simulation:

```bash
gar sim runtime build --workspace Local/Product
gar sim runtime deploy --workspace Local/Product
gar sim app build --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

Physical Target:

```bash
gar target prepare --workspace Local/Product       # 初回またはrecipe更新時
gar target build --workspace Local/Product
gar target preflight --workspace Local/Product --json
gar target deploy --workspace Local/Product
gar target diag --workspace Local/Product --json
```

Multi-node system:

```bash
gar system build --file /path/to/gar-system.json --json
gar system deploy --file /path/to/gar-system.json --json
gar system start --file /path/to/gar-system.json --json
gar system test --file /path/to/gar-system.json --scenario /path/to/scenario.json --json
```

引数と副作用の正確な定義は[コマンドリファレンス](docs/01_COMMAND_REFERENCE.md)を参照してください。

## ドキュメント

### 操作・設計

- [0から実機まで](docs/00_ZERO_TO_TARGET_TUTORIAL.md) — 初期化、simulation、Target deployの一本道。
- [コマンドリファレンス](docs/01_COMMAND_REFERENCE.md) — `gar` CLIの全操作。
- [アーキテクチャ](docs/02_ARCHITECTURE.md) — artifact、system、hardware、Target lifecycleの契約。
- [開発環境](docs/03_DEVELOPMENT_ENVIRONMENT.md) — WSL、Local、Codespaces、Windowsの役割。
- [Agent Terminal Bridge](docs/04_AGENT_TERMINAL_BRIDGE.md) — 人間入力が必要なterminal操作の橋渡し。
- [シミュレーション](docs/06_SIMULATION.md) — backend、Bridge、runtime、scenario。
- [検証状態](docs/07_VERIFICATION.md) — 検証済み範囲と既知の制約。
- [リポジトリ配置](docs/08_REPOSITORY_LAYOUT.md) — GAR、gar-tools、gar-build-env、Productの責務。

### 背景・方針

- [本質](info/00_ESSENCE.md) — GARが消す環境境界と設計原則。
- [ポジショニング](info/01_POSITIONING.md) — simulation方式、現在のcoverage、差別化。
- [将来構想](info/03_FUTURE_VISION.md) — sim2real／sim2specを先へ進める構想。
- [Target Pack戦略](info/06_TARGET_PACK_STRATEGY.md) — Board知識をApplicationから分離して再利用する方針。

AIエージェント向け運用規約は[AGENT.md](AGENT.md)が正本です。`CLAUDE.md`と
`.github/copilot-instructions.md`は各agent向けの薄い入口だけを担います。

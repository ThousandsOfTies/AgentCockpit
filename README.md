# Gapless Agent Runtime

**コーディングから実機稼働まで、AI エージェントが切れ目なく進める組み込み開発環境。**

従来の組み込みソフトウェア開発では、コーディング・検証・実機展開のフェーズをまたぐたびに、人間が環境の立ち上げや、ビルド成果物を受け渡す作業が発生していました。VM でビルドして転送し、動作確認し、実機に流し込む――この「フェーズ間の受け渡し」が開発のリズムを分断し、都度AIのセッションが途切れてしまい、高い自律性の妨げになっていました。

Gapless Agent Runtime は、この受け渡しを人間ではなく、AI エージェント自身で行えるようにし、これによりAIエージェントが自律的に最後まで開発を行うことを実現しました。

結果として、開発者が集中すべき「何を作るか」「どう使うか」の意思決定に、より多くのエネルギーを向けられます。

<p align="center">
  <img src="docs/images/beforeafter.svg" alt="Gapless Agent Runtime concept diagram" width="900">
</p>

これを支えるのが、**仮想 I/O デバイス層を AI が徹底的に作り込む**という仕組みです。実機と同じデバイスインターフェースを VM 上に再現することは、仕様が膨大でメンテコストも高く、人手では費用対効果が合いませんでした。Gapless Agent Runtime はその実装と継続保守を AI が担える枠組みを提供することで、アプリ側の改修なしに VM と実機で同じバイナリを動かせるバイナリ透過性を実現します。これにより、実機が手元になくても本番相当の検証が回せる——真のシフトレフトを開発プロセスに組み込めます。

---

## 動作確認済み環境

| 役割 | 環境 |
|---|---|
| **操作ハブ** | VS Code + WSL2（Windows PC 上） |
| **ビルド** | GitHub Codespaces（クラウド） |
| **検証** | AWS EC2 Graviton（arm64 VM） |
| **実機ターゲット** | Raspberry Pi 5 |

手元の Windows PC に VS Code と WSL2 があれば、上記すべてを `gar` コマンドひとつで操作できます。

実装上は、product hookをWSL上で実行する`local` BuildEnvironmentと、Docker containerを
simulation hostにする`local_docker`にも対応しています。上表はPoCで実機確認した
Codespaces → EC2 Graviton → Raspberry Pi 5の代表経路です。

## セットアップ資産

Runtime 本体とは別に、target ごとのテンプレート・配線定義・シミュレーション資産は
`gar-tools` で管理します。通常は `GaplessAgentRuntime` を clone して `gar setup` を
実行すれば、必要に応じて `.gar/tools` に自動取得されます。

## 製品 devspace の作成

アプリごとの Codespaces/devcontainer workspace は `gar-build-env` の product branch
として作成します。これは `gar setup` より前の bootstrap 操作なので、GAR の設定に
依存しない standalone script を使います。

```bash
scripts/create-product-devspace.sh GarAdhocApp \
  https://github.com/ThousandsOfTies/gar-adhoc-app \
  --destination /home/user/Yurufuwa/GarAdhocApp

scripts/create-product-devspace.sh GarVibeRemote \
  https://github.com/ThousandsOfTies/gar-vibe-ui \
  --destination /home/user/Yurufuwa/GarVibeRemote
```

この script は `gar-build-env` を clone し、product名と同名のbranch、アプリと
`gar-tools` の submodule、`product-sim-build.sh`と`product-target-build.sh`の
templateを作成します。product固有のsimulation/target build commandを編集した後に、
作成先を指定して`gar setup`を実行してください。リモートbranchまで公開する場合だけ
`--push`を付けます。

target appのソースは`GaplessAgentRuntime/app`ではなく、product workspaceの
`sources/gar-adhoc-app/app`や`sources/gar-vibe-ui/vibe-remote/m5stickc-client`などの
submoduleに置きます。Runtimeはそれらの成果物を
ビルド環境・シミュレーション環境・実機へ運ぶ操作面です。

開発者が `gar-tools` も編集する場合は、`GaplessAgentRuntime` と同じ親ディレクトリに
並べるか、`GAR_TOOLS_ROOT` で明示してください。

## 実機Targetの標準deploy contract

OS管理領域の準備はRuntime本体へdistribution別に直書きせず、選択Targetの
`target.json`が指定するrecipeへ分離します。Raspberry Pi 5 / Raspberry Pi OSの
標準経路は次の通りです。

```bash
gar target prepare --workspace Local/Product  # 初回・recipe更新時
gar target build --workspace Local/Product
gar target deploy --workspace Local/Product
```

`prepare`はreference runtime package、非rootの`gar`service account、device group、
限定sudo installer、共通`gar-app@.service`を導入します。product artifactは
`/opt/gar/apps/<app>/run`をentry pointとして提供し、root管理のservice unitは持ちません。
永続設定は`/etc/gar/<app>.env`へ分離され、通常のapplication再deployでは
上書きされません。実機ではreal `/dev/*`を使用し、simulation dummy deviceやWeb Panelを
導入しません。

シミュレーションの操作は、人間の手動確認と AI / CI の再現確認で入口を分けます。
Linux / RasPi-compatible では Web UI、Wokwi では VS Code Wokwi Simulator / Diagram UI を
人間が操作します。AI / CI の共通JSONシナリオは現在Linux bridgeで利用できます。
Wokwi の共有scenarioはまだなく、製品が追加する場合はWokwi CLI固有形式を使う移行中の例外です。

AIエージェント向けの運用指示は[AGENT.md](AGENT.md)が正本です。`CLAUDE.md`と
`.github/copilot-instructions.md`はagent固有の入口だけを担い、同じ正本を参照します。

## 読者別の入口

| あなたが… | まず読む | 次に読む |
|---|---|---|
| **このプロジェクトを初めて知る** | [02 アーキテクチャ](docs/02_ARCHITECTURE.md)、[info/01 業界動向](info/01_INDUSTRY_TRENDS.md) | [99 PoC 成果](docs/99_RESULTS.md) |
| **実際に動かしたい開発者** | [00 チュートリアル](docs/00_ZERO_TO_TARGET_TUTORIAL.md) | [01 コマンドリファレンス](docs/01_COMMAND_REFERENCE.md)、[06 シミュレーション環境](docs/06_SIMULATION.md) |
| **実機で組みたい** | [00 チュートリアル](docs/00_ZERO_TO_TARGET_TUTORIAL.md)、[05 ハードウェア配線](docs/05_HARDWARE_WIRING.md) | [01 コマンドリファレンス](docs/01_COMMAND_REFERENCE.md)、[02 アーキテクチャ](docs/02_ARCHITECTURE.md) |

## ドキュメント一覧

### docs/ — 運用・手順・リファレンス
* [00 チュートリアル](docs/00_ZERO_TO_TARGET_TUTORIAL.md) — WSL Hub 初期化から Codespace build、EC2 simulation、RasPi5 実機実行までの一本道。
* [01 コマンドリファレンス](docs/01_COMMAND_REFERENCE.md) — `gar` コマンド全一覧。グループがそのままフローになっている。
* [02 アーキテクチャ](docs/02_ARCHITECTURE.md) — 5 レイヤ構成と各環境の役割分担。
* [03 開発環境方針](docs/03_DEVELOPMENT_ENVIRONMENT.md) — WSL2 / Codespaces / devcontainer / Windows の役割分担。
* [04 Agent Terminal Bridge](docs/04_AGENT_TERMINAL_BRIDGE.md) — AI と VSCode terminal をつなぐ bridge の設計。
* [05 ハードウェア配線](docs/05_HARDWARE_WIRING.md) — RasPi5 の LED / ボタン / I2C / SPI 配線図。
* [06 シミュレーション環境](docs/06_SIMULATION.md) — EC2 上の device compatibility runtime の起動・操作・診断。
* [07 引き継ぎ資料](docs/07_HANDOFF.md) — GAR 周辺作業の現状、環境境界、Renode / BT / Local bridge の申し送り。
* [08 リポジトリ配置](docs/08_REPOSITORY_LAYOUT.md) — GaplessAgentRuntime / gar-tools / `.gar/tools` の配置意図。
* [99 PoC 成果まとめ](docs/99_RESULTS.md) — EC2 フルシミュレーションと RasPi5 実機の動作確認結果。

### info/ — 業界情報・設計思想・将来構想
* [00 本質](info/00_ESSENCE.md) — このプロジェクトが本当は何の実証なのか（3層は一例、本質は環境横断の連続化）。
* [01 業界動向と技術的価値](info/01_INDUSTRY_TRENDS.md) — SOAFEE / SDV 等のトレンドとの比較。
* [02 設計思想](info/02_DESIGN_PHILOSOPHY.md) — なぜこの構成になったのかの設計哲学。
* [03 将来構想](info/03_FUTURE_VISION.md) — 宇宙・ロボットへの展開ビジョン。
* [04 製品の核](info/04_PRODUCT_CORE.md) — 何を売るのか、誰のどの往復（ROM 焼き／ログ解析）を消すのか。競合の空白マップ。
* [05 ターゲットとシミュレーション](info/05_TARGET_AND_SIMULATION.md) — 組み込みターゲット×シミュレーション方式の一覧、GAR の実装カバレッジ（できる/できない）、AMP（Linux+RTOS 2CPU）境界の統一 trace という差別化。

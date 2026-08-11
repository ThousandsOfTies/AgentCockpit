# Gapless Agent Runtime アーキテクチャ

システムは以下の5つのレイヤで構成される。

| レイヤ | 実体 | 役割 |
|---|---|---|
| 1. 統合開発環境 | VSCode + `gar` CLI | AI・人間が共有する操作面。ビルド/デプロイ/観察の起点 |
| 2. ビルド環境 | Local / GitHub Codespaces | product hookをローカルまたはクラウドで実行。CodespacesはARM64クロスビルド等に利用 |
| 3. シミュレーション環境 | AWS EC2 Graviton | 実機と同一 ARM64 バイナリを動かす仮想 H/W 実行環境 |
| 4. デバイス互換 Runtime | CUSE / gpio-sim + bridge | `/dev/i2c-*` `/dev/spidev*` `/dev/gpiochip*` を OS レベルで再現しアプリを無改造で動かす |
| 5. 実機接続環境 | RasPi5（SSH/systemd recipe） | 同じapplication成果物をreal `/dev/*`で実行。OS準備とboot統合はTarget recipeが担当 |

ビルド成果物は、選択したBuildEnvironment（local / Codespaces）→ WSL側artifact store → simulation/実機の一方向で流れる。EC2や実機上ではビルドしない。ESP32を含む全targetで同じBuildEnvironmentを使い、target固有のbuild手順はproduct hookに置く。

---

## コマンドモデル

GAR のコマンドは make の target に近い考え方に寄せる。ユーザーが入力するのは
`gar sim app build` / `gar sim app deploy` / `gar target build` / `gar target deploy` のような
抽象 target であり、個別の実行方法（PlatformIO、Codespaces、esptool、adb、scp など）は
`gar setup` で選ばれた target 定義と接続設定から解決する。

現在の`deploy`は、WSL側artifact storeにある最新bundleを対象runtimeへ反映する操作であり、
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
構造化reportで返す。`status`、`diag`、P1-2の`test`はmachine-local値を解決せず診断を集約し、Golden scenarioはP1-4の責務である。
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
WSL側ではworkspace ID・artifact種別・build IDごとに不変snapshotを作り、`latest.json`で
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

`gar setup` は、この graph の各 node が何を意味するかを保存する。たとえば ESP32/M5StickC
なら `target.access` は USB serial 接続先、`target.build` はproduct workspaceの
`product-target-build.sh`をlocalまたはCodespacesで実行する処理、
`target.deploy` は最新 firmware artifact の flash になる。RasPi/Linux device なら
`target.prepare`はTarget manifestのOS recipe適用、`target.deploy`はADBまたは
SSH/scpでの配置になる。

---

## 1. 統合開発環境

Gapless Agent Runtimeでは、VSCodeを、開発者と AI エージェントが共有する統合開発環境として使用します。

ここにすべての情報と操作インタフェースを集約することで**AI が開発作業の最初から最後までを自分で実行できる状態**を実現します。

役割分担は次のように変わります。

| 役割 | Before: 従来の開発環境 | After: Gapless Agent Runtime |
|---|---|---|
| 人間 | SSH接続、データ入力、実機/シミュレータ操作、ログ収集、結果確認、次の手順判断 | AI Agentへの指示、結果の確認、判断 |
| AI Agent | ソフトウェア作成、部分的なコード修正支援 | ソフトウェア作成、SSH接続、デプロイ、データ入力、仮想H/W操作、ログ収集、診断、結果整理 |

この役割変更を実現するために、Gapless Agent Runtime では Make ターゲット、JSON シナリオ、ログ、状態取得を整備し、ビルド、デプロイ、シミュレータ起動、仮想 H/W 操作、ログ確認、診断までを AI が再現可能な手順として実行できる形にします。

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

## 2. クラウド開発環境 (GitHub Codespaces)

Gapless Agent Runtime では、開発環境として GitHub Codespaces を採用しています。

Codespaces により、ローカルPCのOSやインストール済みツールに依存せず、セットアップ済みの開発環境を瞬時に起動できます。開発環境を IaC 的に定義しておくことで、チームメンバ全員に同じ依存関係、同じツールチェーン、同じコマンド体系を提供できます。

Gapless Agent Runtime では、その標準化された作業場に AI Agent も参加します。AI は人間のローカルPC固有の環境に依存せず、チームで共有された開発環境の中でビルド、デプロイ、実行、観察を行います。

---

## 3. シミュレーション環境 (AWS EC2 Graviton)

### VM の選定理由

シミュレーション環境には AWS EC2 Graviton（ARM64）を採用している。実機である Raspberry Pi 5 と同じ **ARM64 (aarch64)** アーキテクチャのため、Codespaces でクロスビルドした成果物をそのまま EC2 にデプロイして動かせる。x86 VM を挟んだエミュレーション実行では見えない ABI 差異やアライメント問題を早期に検出できる点も選定理由のひとつ。

---

## 4. デバイス互換 Runtime

### 仕組み：アプリを無改造で動かす

アプリ側に `#ifdef SIMULATION` やシミュレーション専用 HAL を持たせない。アプリは実機と同じ `/dev/i2c-1`、`/dev/spidev0.0`、`/dev/gpiochip0` を開くだけにし、差し替えの責務を OS/device layer に閉じ込める。

EC2 上では以下の仮想デバイスで `/dev/*` を再現する。

| I/F | 実装 | アプリから見えるもの |
|---|---|---|
| I2C | CUSE で `/dev/i2c-1` を生成 | 実機と同じ i2c-dev |
| SPI | CUSE で `/dev/spidev0.0` を生成 | 実機と同じ spidev |
| GPIO | `gpio-sim` で `/dev/gpiochip0` を提供 | 実機と同じ GPIO chardev v2 |

### バイナリ透過性

この構成により、Codespaces でビルドした同一バイナリが EC2 でも RasPi5 でも動く。CUSE/gpio-sim の実装と保守は AI が担うことで、実機検証フェーズに入ってもシミュレーション環境が陳腐化しない体制を目指す。

### 仮想 H/W の操作・観察（bridge）

仮想デバイスへの操作・観察は、人間の手動操作と AI / CI の再現操作で入口を分ける。

* **Virtual Hardware Panel**: LED・ボタン・RFID・センサーの状態変化を WebSocket 経由でブラウザパネルにリアルタイム表示。人間が目視で動作確認できる。
* **JSON シナリオ試験**: ボタン押下・RFID タップ・センサー値変更・状態確認を JSON シナリオとして定義し、AI や CI が同じ手順を再現可能なテストとして実行できる。
* **HTTP API（bridge）**: Linux / RasPi-compatible simulation の内部受け口。Web UI と JSON シナリオ実行系が同じ仮想 H/W 操作ロジックを通るため、UI 変更時のメンテ漏れが起きにくい。

物理的な検証実装は simulation environment ごとに分かれるが、上記 control plane の観点では、いずれも Bridge の背後に置く。

| 対象 | 入口 |
|---|---|
| Linux Bridge 手動操作 | Virtual Hardware Panel |
| Linux Bridge シナリオ | `python scripts/run_scenario.py path/to/scenario.json` |
| Wokwi 手動確認 | VS Code Wokwi 拡張 / Diagram Editor |
| Wokwi 自動確認 | 共有scenarioは未提供。製品がscenarioをartifactへ含めた場合だけ`wokwi-cli --scenario`を使用 |
| MuJoCo | `gar sim runtime start --no-port-forward`（start時にmodelを検証） |
| ESP32 QEMU | setup選択肢とerror-only runtimeのみ。`gar-esp32-flash-image` / `gar-esp32-qemu-run`はgar-tools側の手動検証入口 |
| Renode | setup選択肢とerror-only runtimeのみ。`renode` / `renode-test`は手動検証入口 |
| Vibe Remote smoke | `npm run smoke:protocol` |

WokwiとMuJoCoのlocal processは共通のstate storeを使う。stateはatomicに置換し、
start/stopはfile lockで直列化する。停止時はPIDだけでなくargvと`/proc` start timeを照合し、
PID再利用で無関係なprocessを停止しない。MuJoCoのproduct assetは`gar sim app deploy`で
`.gar/mujoco/`へmaterializeしてからmodelを検証する。

具体的なセットアップ手順と確認手順は [06_SIMULATION.md](06_SIMULATION.md) を参照。

---

## 5. 実機接続環境

Gapless Agent Runtimeでは、AIが実機へ到達する接続経路をTargetごとに選びます。
Raspberry Pi 5 / Raspberry Pi OSの標準は**SSH/scp**であり、`gar target prepare`による
OS recipe適用と、限定sudo installerによるsystem領域deployを利用します。

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
通じてenv fileを原子的に更新し、通常deployでは削除・上書きしない。read-only rootfsやBuildroot、
image flashingを使うTargetは同じCLIへ別recipe/backendを追加する。

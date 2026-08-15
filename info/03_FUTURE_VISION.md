# 将来構想 — SimulationからHardware要求を発見する

この文書は実装計画やTODOではなく、GARを将来どこへ拡張できるかを記録する。
現在の実装範囲は[検証状態](../docs/07_VERIFICATION.md)、直近のBoard戦略は
[Target Pack戦略](06_TARGET_PACK_STRATEGY.md)を正本とする。

## 出発点

GARの基礎機能は、Build、Simulation、Physical Targetという性質の異なる環境を、
一つの操作・観測契約へ載せ替えることである。

```text
Product source
  ├─ BuildEnvironment
  ├─ SimulationEnvironment
  └─ TargetEnvironment
          ↑
   artifact / lifecycle / diagnostics / scenario
```

GarStreamTx/Rxでは、複数nodeをsimulationと実機へ展開し、Product protocol、映像、
GPIO、SPI display、rotary encoderを同じsourceとinterfaceで検証した。この実績を
「既存Hardwareを模倣する」用途だけで終わらせず、まだ存在しないHardwareを探索する
基盤へ発展させる。

## Sim2spec

一般的なsim2realは、先にある実機をSimulationで再現する。この構想では矢印を逆にする。

| 一般的なsim2real | sim2spec |
|---|---|
| 実機をSimulationで模倣する | 仮想deviceを先に定義する |
| 出力は検証済み制御 | 出力はHardware要求仕様 |
| 実機との差を小さくする | 役立つdeviceの特性を探索する |

```text
仮想device仕様
      ↓
Bridge / provider / physics model
      ↓
Productまたはagentによるtask実行
      ↓
性能・安全・面白さ・実現可能性を評価
      └───────────────→ 仕様を更新
```

収束時の成果は「このsensor／actuatorを作るとtask性能が上がる」という、測定条件付きの
要求仕様である。

## GAR資産との接続

| 現在の契約 | 探索での役割 |
|---|---|
| Hardware requirements | Productが必要とする論理deviceを表す |
| Target capabilities | 現実のBoardが提供できるresourceを表す |
| Binding | 論理deviceと物理resourceの対応を表す |
| Simulation provider／Bridge | 架空deviceのbehaviorと操作面を表す |
| System topology | 複数nodeとlinkを表す |
| Golden scenario／metrics | 候補仕様を比較する評価関数になる |
| Artifact provenance | どのsource・model・Targetで得た結果かを固定する |

特定のprovider filenameや一時的なPoC構成は構想の前提にしない。新しいdevice modelは
上記契約に従い、Product固有の要求とBoard固有の実装を分離する。

## 最初の実験サイズ

いきなり高価・危険な実機を対象にせず、10〜20 cm程度の小型robotを実験室にする。

- 安価で壊しても復旧しやすい。
- Simulationと実機の反復を短くできる。
- 3D printと市販部品で候補仕様を実装できる。
- latency、消費電力、noise、重量も測定可能な制約として入れられる。

機体は万能にしない。「あと少し足りない」という良い欠乏が、新しいsensorやactuatorを
要求する動機になる。たとえば少ない自由度で立つ・運ぶ・歩くtaskを順に与え、
追加deviceの効果をmetricsで比較する。

## 探索を現実へ戻す条件

架空deviceを無制限に許すと、結果は実装不能な願望になる。最低限、次をcontractに含める。

- 応答時間、sampling rate、noise、packet loss。
- 電圧、消費電力、熱、重量、寸法。
- GPIO／I2C／SPI／network等のinterface。
- 部品価格と調達可能性。
- failure modeと安全停止。
- Simulation結果と実測値の誤差。

候補が収束したらHardware requirementsとTarget bindingへ落とし、実機HILで同じscenarioを
再実行する。この往復が成立して初めてsim2specの成果とする。

## 適用先

同じ三層構造はrobotics、製造、車載、宇宙にも存在する。特に実機が高価、危険、
復旧困難な領域ほど「Simulationで試してからTargetへ反映する」価値が大きい。
ただし、適用分野を増やす前に、小型robotで要求発見から実機検証までの一周を
machine-verifiableに完走する。

## 着手条件

次の条件が揃うまでは構想として保持する。

1. Target PackからApplication固有資産を分離できている。
2. Physical HILでGolden scenarioを無人判定できる。
3. timing／電気特性をHardware contractとmetricsへ表現できる。
4. candidate間の比較結果をartifact provenanceと共に保存できる。

この構想の価値は対応device数ではなく、Simulationで得た知見を再利用可能なHardware仕様へ
戻し、実機で反証できる閉ループにある。

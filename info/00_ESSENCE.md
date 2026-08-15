# GARの本質と設計原則

## 一言で

Gapless Agent Runtimeの本質は、特定のシミュレータではない。

> **開発、仮想検証、実機運用の境界を同じ操作と観測の契約へ畳み、AIが文脈を失わずに反復できるようにする。**

WSL、Codespaces、EC2、Raspberry Pi、Buildroot Boardは、その契約を実証するための具体例である。
環境数や製品分野は本質ではない。

## 消す二つの往復

組み込み開発では、次の二つの往復に人間の時間が使われる。

1. **物理の往復**: build、媒体への保存、書き込み、再起動、目視、再build。
2. **認知の往復**: log取得、AIへの貼り付け、解析、別terminalでの再操作、結果の再説明。

GARは、実機を不要にすることだけを目的にしない。実機が必要な工程も同じ操作面に接続し、
反復可能なbuild、deploy、observe、diagnoseをAIとCIへ移す。人間は、要件、配線、認証、
危険操作の承認、結果の価値判断に集中する。

## 売り物

売り物はCUSE、Terraform、SSH、Web Panelのどれか一つではない。これらは差し替え可能な実装である。

売り物は次の共通契約と、それを使って蓄積される運用資産である。

- environmentに依存しない`gar`の操作語彙
- provenance付きの不変artifact
- Board／OS差を閉じ込めたTarget Pack
- Product requirementsとTarget capabilitiesをつなぐBinding
- 人間向けUIとAI／CIが共有するBridge、metrics、scenario
- deploy後のhealthとrunning build IDまで確認する収束契約

技術要素は模倣できる。再利用可能なTarget Pack、故障分類、診断、Golden scenarioを
積み重ねた厚みが、GAR固有の価値になる。

## 設計原則

### WhatとHowを分ける

Productは「何が必要か」を宣言し、Target Packは「Boardが何を提供できるか」を宣言する。
SSH、ADB、esptool、UUU、systemd、BusyBoxは実現方法であり、Productの意味へ混ぜない。

### ApplicationへSimulation分岐を持ち込まない

Linux Productは実機と同じ`/dev/*`、network protocol、process contractを使う。
simulation差分はdevice provider、Bridge、Target adapterへ閉じ込める。architectureが違う場合でも、
sourceと外部interface、state behaviorを共通化する。

### Artifactは一方向に流す

BuildEnvironmentが生成したartifactをWSL側で不変snapshotにし、Simulation／Targetへ配布する。
実行先で場当たり的にcompileせず、source commit、toolchain、recipe、checksum、build IDを追跡する。

### 転送成功を完了と呼ばない

deployは、配置、reload／restart、health、running build ID一致まで収束して初めて成功とする。
状態は人間向け文字列ではなく、exit codeとJSONで判断できるようにする。

### 実機知見を共通資産へ戻す

pinmux、init system、root権限、SDK、SPI速度、encoderのbounceなど、実機で得た知識を
READMEだけに残さない。Target capability、recipe、Binding、testへ戻し、次のProductとBoardが再利用する。

### 不可逆操作は人間へ返す

cloud認証、sudo password、物理配線、電源、USB recovery、image flash、秘密情報の登録は、
自動化できても勝手に実行しない。AIは対象と影響を示し、人間が見えるterminalまたは承認境界で実行する。

## 「同じ実装」の三段階

| 段階 | 意味 |
|---|---|
| Exact binary | architecture、ABI、libcが一致し、同じbytesを実行する |
| Same source and interfaces | Target別にbuildするが、同じsourceとdevice／protocol契約を使う |
| Behavioral conformance | acceleratorや内部実装が異なっても、外から見える状態遷移と性能契約を満たす |

Raspberry Pi 5とarm64 EC2はExact binaryを狙える。armv7のRK3506とはSame source and interfacesを狙う。
将来のmedia accelerator利用ではBehavioral conformanceが現実的な契約になる。

## 成功の測り方

「AIがコマンドを実行できた」だけでは不十分である。次を測る。

- fresh cloneからの再現性
- 人間の入力回数と物理往復回数
- artifactから稼働processまでのidentity一致
- failure時に原因をJSONで特定できる割合
- 同じTarget Packを別Productが変更なしで利用できるか
- 同じProductを別BoardへBinding中心で移せるか
- system E2Eを無人でPASS／FAIL判定できるか

遠い展開は[将来構想](03_FUTURE_VISION.md)、Board知識の蓄積方法は
[Target Pack戦略](06_TARGET_PACK_STRATEGY.md)に分ける。

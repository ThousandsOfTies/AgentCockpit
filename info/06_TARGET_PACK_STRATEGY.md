# Target Pack 戦略 — ボード探索を実行可能なノウハウへ変える

## 0. この文書の位置付け

GarStreamTx/RxをRaspberry Pi 5、Luckfox Lyra、EC2 simulationへ展開した過程と、
次の廉価ボード候補を検討した会話から得られた設計上の結論をまとめる。

最も重要な発見は、新しいボードを動かすために得た知識を
`gar-tools/targets`へ実装として戻すことが、GARの継続的な価値になるという点である。

> **Target Packとは、一度成功したボード立ち上げを、別のProductと別の開発者が
> 再実行できる形にした「実行可能な実機ノウハウ」である。**

単なる対応ボード一覧やshell script集ではない。互換性、provisioning、deploy、
lifecycle、診断、復旧、テストまでを共通契約に載せた再利用可能な資産を指す。

---

## 1. ボードを複数試して初めて見えたもの

Raspberry Pi 5だけで完了していた場合、GARは「SSHでLinux機へapplicationを
deployする仕組み」に見えた可能性がある。Luckfox Lyraを実機化したことで、
次の差異が実際の問題として露出した。

- `aarch64`と`armv7l`
- native buildとcross build
- Raspberry Pi OSとBuildroot
- systemdとBusyBox init
- 限定sudoを使う一般userと、root SSHしか持たない小型Target
- package managerを持つOSと、rootfs buildが前提のOS
- 同じLinux `/dev/*` APIの背後にあるDevice Tree、pinmux、GPIO番号の差
- application deployと、OS image／boot設定／永続設定の責務境界
- ファイル転送成功と、実際に新しいbuildが稼働していることの違い

この差をGAR Coreへ個別条件分岐として追加するのではなく、Target所有recipeと
capabilityへ分離したことが今回の主要成果である。

現在のRaspberry Pi 5/systemd recipeとRK3506/BusyBox recipeは、異なるinit systemの
上で同じapplication lifecycle語彙を提供する方向へ進んでいる。

- `status`
- `log`
- `health`
- `reload`
- `running-build-id`

GAR Coreはこの共通語彙と結果だけを扱い、`systemctl`や`/etc/init.d`の詳細は
Target Packへ委譲する。

---

## 2. Target Packが持つべき知識

実機立ち上げで人が調査する情報を、次の実行可能な構成要素として保持する。

| 領域 | Target Packが保持する内容 |
|---|---|
| 識別・互換性 | Target ID、CPU architecture、ABI、libc、toolchain triple、kernel／OS条件 |
| build支援 | SDK、toolchain、sysrootの解決方法と事前診断 |
| provisioning | service account、限定sudo／root helper、init integration、必要package |
| deploy | SSH／ADB／USB flash／UUU等の転送方式、atomic置換、再起動と収束確認 |
| lifecycle | start、stop、reload、status、log、health、稼働build ID |
| hardware capability | 使用可能なGPIO、SPI、I2C、camera、display、pinmux、電圧等 |
| recovery | boot失敗、image破損、接続不能時の復旧経路 |
| verification | manifest検証、recipe unit test、実機acceptance test、`--json`結果 |
| documentation | 電源、boot switch、debug UART、配線上の注意点 |

特に重要なのは、作業手順をREADMEだけに残さないことである。READMEは人間向け説明、
manifestとrecipeはGARが実行する正本、testはその知識が古びていないことを確認する契約とする。

---

## 3. ProductとTargetの掛け算

Target Packを正しく分離すると、ProductとBoardを一対一で移植する必要がなくなる。

```text
Product requirements
        │
        ▼
     Binding
        │
        ▼
Target capabilities ── Target recipe
```

- 新しいTarget Packを追加すると、要件が適合する既存ProductがそのTargetを利用できる。
- 新しいProductを追加すると、capabilityが適合する既存Target Pack群から実行先を選べる。
- GAR CoreはTarget数、Product数に比例した個別実装を持たない。

この掛け算が成立すれば、`gar-tools/targets`は補助script置き場ではなく、GARの利用に伴って
価値が累積するTarget知識ライブラリになる。

---

## 4. 混ぜてはいけない5つの層

今回の実装はTarget recipeの価値を証明した一方で、Product固有hardwareがTargetへ
入り込みやすいことも示した。責務を次の5層へ分ける。

### 4.1 Platform

SoC、architecture、ABI、OS、init、toolchain、image形式など、同系統Boardで共有できる知識。

例:

- Rockchip RK3506 + armv7 hard-float
- Buildroot + BusyBox init
- RK3506 SDK／sysroot

### 4.2 Board Profile

具体的な基板が外部へ出しているcapability。

例:

- Luckfox Lyra Plus
- Luckfox Lyra Zero W
- 搭載RAM／storage
- Ethernet／Wi-Fi
- GPIO header、SPI controller、USB Host、DSI等

### 4.3 Product Requirements

Productが必要とする機能を、特定Boardのpin番号を使わずに宣言する。

GarStreamTxの例:

- V4L2 camera source
- SPI display
- rotary encoder A/B/switch
- network送信

GarStreamRxの例:

- RTP受信
- SPI display
- rotary encoder A/B/switch

### 4.4 Binding

Productの論理信号を、選択Boardのdevice node、GPIO line、bus、pinmuxへ対応付ける。

例:

```text
display.spi       -> /dev/spidev0.0
display.dc        -> /dev/gpiochip0 line N
encoder.phase_a   -> /dev/gpiochip0 line M
camera.input      -> /dev/video0
```

ILI9341やKY-040の存在、`lcd_dc`等のProduct内の役割、実配線はこの層またはProduct側に属する。
Target共通定義へGarStreamRx専用構成を埋め込まない。

### 4.5 Target Instance

個体や利用者の環境によって変わる情報。

- SSH config Host名
- IP address
- credential／鍵
- 選択した物理device node
- 現場固有の永続設定

これらはrepositoryのTarget Packへ固定せず、workspace設定またはTarget上の
`/etc/gar/<app>.env`等に保持する。

### 4.6 最優先で解消する依存の逆流

この分離で最も重要なのは、**Board／Platform資産へApplicationの都合を染み出させないこと**である。

Target Packが知ってよいのは、たとえば次の情報までとする。

- 利用可能なSPI controller、chip select、最大clock
- GPIO chip／line、割り込み、pull-up、電圧
- V4L2 device、camera interface、media accelerator
- Device Tree／pinmuxを有効化するBoard固有手順
- init system、ABI、toolchain、deploy／lifecycle方式

一方、次はTarget Packへ置かない。

- `GarStreamTx`／`GarStreamRx`というProduct名や役割
- TX／RXのmenu構成、Profile、Source選択、rotaryの状態遷移
- GarStream専用のservice名、環境変数、既定path
- ILI9341を「GarStreamのDISPLAY」として使う定義
- KY-040を「GarStreamのmenu操作」として使う定義
- Product固有の配線、device node、GPIO lineの決め打ち

ILI9341やKY-040自体のdriver／protocol実装を複数Productで再利用するなら、独立した
Peripheral／Device Adapter資産として切り出せる。しかし、それをどのProductの論理的な
`display`や`encoder`へ割り当て、どのBoard pinへ接続するかはBindingの責務である。

依存方向は次に固定する。

```text
Platform knowledge ──> Board capabilities
                              ▲
                              │ 適合・割り当て
Product requirements ─────> Binding
```

PlatformとBoard ProfileはProductをimportしない。BindingだけがProduct requirementsと
Board capabilitiesの両方を参照する。この規則により、新しいApplicationを載せるたびに
`gar-tools/targets/<target>`を書き換える状態を防ぐ。

RK3506のBoard capabilityはProduct-neutralな`capabilities.json`へ分離済みである。一方、
Linux simulation runtimeのILI9341 provider／READMEや、旧RV1106 Target資産にはGarStream由来の
名称、周辺構成、用途が残る。これらを同じ判定条件で分離し、RK3506だけが偶然きれいな状態で
完了扱いしない。

### 4.7 分離完了の判定条件

次をすべて満たして、Applicationの染み出しを解消したと判定する。

1. Target Pack単体のtestを、GarStream repositoryなしで実行できる。
2. `gar-tools/targets`にGarStreamのProduct名、menu、protocol、専用device役割が存在しない。
3. 同じTarget Packへ別Applicationを追加してもTarget定義を変更しない。
4. GarStreamを別Boardへ移す際の変更が、原則としてBoard Profile選択とBindingに閉じる。
5. Target probeは汎用capabilityを報告し、Product適合性はBinding validatorが判定する。
6. Product固有service／environment生成物はProduct artifactまたはBindingから生成される。

---

## 5. RK3506で最初に証明する再利用

購入済みのLuckfox Lyra Zero Wは、Target Pack分離を確認する最初の題材として適している。
既存Lyra Plusと同じRK3506系Platformを共有しつつ、搭載I/Oや通信方法が異なるためである。

概念上は次のように共有する。

```text
RK3506 + Buildroot + BusyBox + armv7 toolchain
  ├─ Luckfox Lyra Plus board profile
  └─ Luckfox Lyra Zero W board profile
```

### 成功条件

Zero W対応時に、次を満たすことを再利用成功とする。

1. RK3506共通toolchain、ABI、Buildroot lifecycle recipeを複製しない。
2. GarStreamのPnP、RTP、menu、rotary state machineを変更しない。
3. 追加の中心をBoard ProfileとGarStream向けBindingに限定する。
4. Target probeがarchitecture、libc、Target ID、必要deviceをdeploy前に検証する。
5. fresh cloneからsetup、build、prepare、deploy、health確認まで再現できる。
6. 既存Lyra PlusとRaspberry Pi 5の経路を壊さない。

もしZero W対応のためにGarStream本体またはRK3506 provisioningを大量に分岐する必要があれば、
層分離がまだ不十分である。

---

## 6. GarStreamTxのBoard戦略

GarStreamTxを廉価Boardへ展開できると、GarStreamは「Raspberry Pi上のPoC」から
「目的別の組み込み製品候補」へ進む。

```text
同じGarStreamTxのProduct契約
  ├─ EC2／Linux simulation
  ├─ Raspberry Pi 5       : 高性能なreference実装
  ├─ Lyra Zero W          : RK3506低価格実装
  └─ RV1106 Board         : ISP／映像処理特化実装
```

### Raspberry Pi 5

- 現在の動作確認済みreference Target。
- 性能、USB、Raspberry Pi OS ecosystemに余裕がある。
- 廉価版の結果を比較し、障害時にProduct側とTarget側を切り分ける基準機として残す。

### Luckfox Lyra Zero W

- RK3506、512MB級の小型Linux Boardとして低価格TX候補にする。
- 既存RK3506 Target知識を再利用できるかを検証する。
- USB camera、SPI display、rotary encoder、network送信を同じProduct契約へbindingする。
- Raspberry Pi 5よりresourceが小さいため、native実装と性能測定が必要になる。

### RV1106 Board

- camera ISP／media acceleratorを持つ映像特化TX候補。
- Buildroot、RKMedia／MPP、MIPI CSI、Ethernet等をTarget capabilityとして扱う。
- 販売ページの記載だけを信頼せず、到着後にSoC variant、RAM、storage、Board modelをprobeする。
- 最初は既存のGarStream protocolとのbehavioral conformanceを優先し、codec変更は別Profileとして扱う。

### FRDM-IMX91S

- UUUによるOS image単位のdeployを検証する購入済みの将来Target。
- i.MX93ほどのNPU性能は不要であり、Yocto／SD・eMMC／USB SDP／UUUという
  新しいprovisioning方式を検証する目的にはi.MX91Sで十分である。
- SSH application deployとfull-image flashを同じ副作用として扱わない。
- NXP固有commandをGAR coreへ直書きせず、Target Packがboot mode、USB identity、image、
  destination、verify、recoveryを宣言する。

---

## 7. 「同じ実装」の意味を段階化する

Boardやarchitectureが異なる場合、同一性を一語で表さない。

| 段階 | 意味 |
|---|---|
| Exact binary | 同じbytesの実行ファイルを動かす |
| Same source and interfaces | 同じProduct sourceを別toolchainでbuildし、同じdevice／protocol契約で動かす |
| Behavioral conformance | 内部実装やacceleratorが異なっても、外部protocol、操作、状態遷移が一致する |

Raspberry Pi 5の`aarch64`とRK3506／RV1106の`armv7`ではExact binaryを目標にしない。
GarStreamの現実的な成功条件は、Same source and interfacesまたはBehavioral conformanceである。

Board固有media acceleratorを活用するときも、PnP、Source選択、menu、rotaryの1 detent＝1 step、
RXから見える映像契約を自動scenarioで確認する。

---

## 8. Target Packを製品資産にするための条件

### 8.1 Versionとprovenance

artifactには少なくとも次を記録し、deploy前にTarget probe結果と照合する。

- schema version
- Target ID
- architecture、ABI、libc
- toolchain／sysroot識別
- Target recipe version
- Product source commit
- gar-tools commit
- file checksums
- build ID

### 8.2 共通lifecycle contract

systemd、BusyBox、将来のcontainer／RTOS等の違いを、Target helperが共通語彙へ変換する。
deploy完了はファイル配置ではなく、次を満たした状態とする。

1. atomicに新artifactへ置換した。
2. 対象processをreload／restartした。
3. health probeが成功した。
4. 稼働build IDとartifact build IDが一致した。

### 8.3 Test

- manifest schema test
- recipe unit test
- lifecycle conformance test
- compatibility rejection test
- Board probe test
- Product×Board binding validation
- 実機acceptance／HIL test

Target Packは「READMEに書いてあるから対応」ではなく、これらのtestを通過して初めて対応済みとする。

### 8.4 Security

Target recipeはroot、sudo、flash deviceへ触れる可能性があるため、通常のlibraryより強い信頼境界になる。

- root helperの操作を限定する。
- recursiveな任意path削除や任意command実行を許さない。
- recipe versionとsourceをartifactへ記録する。
- destructiveなimage flashは対象deviceをprobeし、明示的な操作として扱う。
- 将来外部配布する場合は署名と配布元検証を設ける。

---

## 9. 現在地と次の検証

### 実装済み

- schema-v2 artifact、checksum、source／gar-tools／recipe provenance
- deploy前compatibility probeとread-only `target preflight`
- systemd／BusyBoxを共通化したTarget lifecycle
- Product requirements／Target capabilities／Bindingのoffline validation
- 複数workspace system topology
- metricsとGolden scenarioによるGarStream E2E契約
- Raspberry Pi 5とRK3506のProduct-neutral Board capability

詳細な確認範囲は[検証状態](../docs/07_VERIFICATION.md)を正本とする。

### 次に確認する順序

1. **Applicationの逆流を完全に除去する。** Linux simulation runtimeとRV1106資産に残る
   GarStream固有名称、Peripheral構成、menu／用途を、Peripheral adapter、Product、Bindingへ移す。
2. **Lyra Zero WでRK3506 Platform再利用を証明する。** 共通toolchain／lifecycleを複製せず、
   Board ProfileとBinding中心でGarStreamTxを動かす。
3. **FRDM-IMX91Sでfull-image provisioningを追加する。** `full-image-flash + usb-recovery +
   nxp-sdp-uuu`を、SSH application deployと独立した契約として実装する。
4. **RV1106は到着後にprobeから始める。** 販売情報ではなく、SoC、RAM、storage、boot mode、
   media stackを測定してBoard Profileを確定する。
5. **Physical Golden HILを閉じる。** read-only preflight／diagの先に、明示承認付きdeploy、
   physical input／display観測、rollbackを追加する。

対応Board数を増やす前に、既存Target Packを別Productが変更なしで利用できることを確認する。

---

## 10. 最終結論

ボードを複数試したことは遠回りではなかった。実機差を振らなければ、GAR CoreとTarget固有知識の
境界、Productと配線の境界、deployと稼働確認の境界は見えなかった。

シミュレーションはGARの重要機能だが、それだけが差別化ではない。

> **GARの持続的な価値は、実機で一度得たbring-up知識をTarget Packへ戻し、
> 次のAI、次のProduct、次のBoardが再利用できる循環にある。**

Lyra Zero WでRK3506知識の再利用を証明し、FRDM-IMX91SでUUUによるimage provisioningを加え、
RV1106で映像特化capabilityを検証する。この順序により、単なる対応Board数ではなく、
Target契約の厚みをGARの資産として増やしていく。

# GARの技術的ポジショニングと現在地

この文書は、市場予測ではなく、GARがどの方式を採用し、どこまで実装しているかを整理する。
具体的な操作契約は`docs/`、確認済み範囲は[検証状態](../docs/07_VERIFICATION.md)を正本とする。

## Simulationの三方式

| 方式 | 動かすもの | 強み | 弱み | 例 |
|---|---|---|---|---|
| Host-native／同arch Linux | nativeまたはcross-buildしたapplication | 高速、観測しやすい | kernel／device差はadapterが必要 | EC2 Graviton、Local Docker、native_sim |
| CPU／SoC emulation | 実機向けfirmware binary | MCUにも使え、bootを含められる | model精度と速度に依存 | Renode、QEMU |
| HIL／Physical Target | 実chipと実周辺 | 最終忠実度が高い | 台数、配線、復旧、観測に制約 | Raspberry Pi、Luckfox、ESP32 |

GARは一つを選ぶ製品ではない。ProductとTargetのcapabilityに応じて方式を選び、
build、deploy、start、observe、diagという上位語彙を揃える。

## 現在強い領域

### Linux edgeのshift-left

Linux applicationを標準`/dev/*`とnetwork interfaceへ寄せ、EC2／DockerではCUSE、gpio-sim、
Bridgeが周辺を再現する。Raspberry Pi 5のaarch64経路では同一binary、RK3506のarmv7経路では
同一source／interfaceによる移植を実証した。

### ArtifactとTarget lifecycle

schema-v2 artifactはsource、gar-tools、Target recipe、architecture、ABI、libc、checksumを固定する。
Target recipeはsystemdとBusyBoxの違いを共通lifecycleへ変換し、`status`、`log`、`health`、
`reload`、`running-build-id`を提供する。

### 複数node system

GarStreamTx/Rxにより、一台のapplicationだけでなく、複数workspace、node、link、runtime環境、
Golden scenarioを一つのsystemとして扱えるようになった。PnPやRTPはProduct責務のまま、GARは
起動順、環境注入、diagnostic、metrics assertionを担当する。

### Board知識の再利用

Raspberry Pi OS／systemdとRK3506 Buildroot／BusyBoxの差をTarget Packへ収容したことで、
GAR coreをdistribution条件分岐で膨らませずにTargetを追加できる形が見えた。次の焦点は、
Board資産に残るApplication固有周辺・名称を完全に分離することである。

## 実装済みbackend

| 領域 | 状態 |
|---|---|
| Local／Codespaces BuildEnvironment | 実装済み |
| Linux systemd simulation（Docker／SSH Remote） | 実装済み |
| Wokwi runtime | build artifact配置とlocal process lifecycleを実装 |
| MuJoCo runtime | model配置、検証、local process lifecycleを実装 |
| SSH／ADB file-transfer Target | 実装済み |
| ESP32 esptool Target | firmware bundle検証とflashを実装 |
| Raspberry Pi 5 Target Pack | systemd provisioning／lifecycleを実装 |
| Luckfox RK3506 Target Pack | Buildroot／BusyBox provisioning／lifecycleを実装 |
| Renode、ESP32 QEMU、AWS SSM runtime | setup選択肢と明示的な未実装errorまで |

## 差別化の置き場所

個別simulation engine、cloud、deploy toolには既存製品がある。GARが狙う空白は、それらを
AIが一つのセッションで扱える契約へまとめ、観測と次の操作まで閉じることである。

```text
Build provenance
      + Target capability / provisioning
      + Simulation Bridge / metrics
      + Multi-node scenario
      + AI-readable diagnostics
      = 再現可能な開発ループ
```

対応Board数だけを増やしても、この価値は厚くならない。新しいBoardで得た知識が
Productから分離され、別Productで再利用され、failureが自動testへ戻ることが重要である。

## 次に広げる異なる軸

### Full-image provisioning

現在のSSH Targetは、OSを維持したままapplicationとserviceを更新する。NXP i.MX91SのUUU、
Rockchip Maskrom、NVIDIA recoveryのようなUSB full-image flashは、別のprovisioning classである。

```text
provisioning.kind: full-image-flash
transport: usb-recovery
protocol: nxp-sdp-uuu | rockchip-maskrom | nvidia-rcm | allwinner-fel
```

最初の題材としてFRDM-IMX91Sを使う場合、GAR coreへUUUコマンドを直書きせず、Target Packが
boot mode、USB identity、image、destination、verify、recoveryを実装する。

### MCU／RTOS emulation

Renode等の統合では、SSH Linuxの前提を外し、provision、load、reset、execute、observeを
capabilityとして扱う必要がある。これはLinux SBCとは異なる二つ目の抽象検証になる。

### AMPと統一trace

Linux application coreとRTOS／MCU coreを持つSoCでは、起動順、shared memory、RPMsg、mailbox、
version不一致が境界故障になる。将来GARが両側のeventを一つの時系列へ正規化できれば、
単体simulatorや単体deploy toolとは異なる価値になる。ただし現時点では構想であり、実装済みとは扱わない。

## 冷静に残す制約

- Simulationは実機の電気特性、timing、driver品質を完全には再現しない。
- Same sourceだけでは同じbehaviorを保証しない。FPS、latency、bounce、packet lossもscenario契約に必要。
- HILは秘密情報、物理安全、runner保守を伴い、通常CIと同じには扱えない。
- 外部toolやBoard SDKのversion変化はTarget Packの継続保守を必要とする。
- 汎用platformを名乗る根拠は、対応数ではなく、異なるprovisioning方式を同じ上位契約で完走した実績である。

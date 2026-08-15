# 検証済み範囲と既知の制約

この文書は、履歴や作業予定ではなく、現在のGARがどこまで機械的に検証されているかを示す。
完了した作業の記録はGit履歴とCIへ任せ、ここには利用判断に必要な事実だけを残す。

## 自動検証される契約

`make check`は次をまとめて検証する。

- Python lint／format
- GAR coreのunit test
- artifact schema v2、checksum、provenance、互換性拒否
- Target prepare／deploy／configure／lifecycle／preflightの契約
- system topology、hardware contract、Golden scenario schema
- simulation process identity、diagnostic、Bridge adapter
- shell構文、VS Code Terminal BridgeのNode test

テスト件数は実装追加で変わるため、この文書では固定しない。

## Reference経路

| 経路 | 確認内容 | 段階 |
|---|---|---|
| Local／Codespaces build | Product hookから用途別artifact snapshotを生成 | 自動test／実運用 |
| EC2 Graviton Linux simulation | CUSE I2C/SPI、gpio-sim、Web Bridge、application deploy | 実機会話で確認済み |
| Raspberry Pi 5 | SSH、Raspberry Pi OS systemd recipe、boot service、real GPIO/SPI/video | 実機確認済み |
| Luckfox Lyra Plus RK3506 | armv7 cross-build、Buildroot／BusyBox recipe、real GPIO/SPI | 実機確認済み |
| GarStreamTx/Rx | discovery、lease、RTP映像、display、rotary、metrics | simulation／実機で確認済み |
| GarStream Golden scenario | 複数workspace topologyとBridge metricsによるE2E判定 | parser／orchestrator／CI契約を自動test |

Raspberry Pi 5とEC2はともにaarch64／glibcで、対応Productでは同一binaryを利用できる。
Lyraはarmv7l／gnueabihfなのでbinaryは別だが、GarStreamRxでは同じC++ source、Linux device I/F、
network protocol、state behaviorを使う。

## CIとHILの境界

- GARの通常CIは、実機や秘密情報を必要としないcontract testを実行する。
- GarStream EC2 workflowは、保護された接続設定が存在するときだけ実環境scenarioを実行する。
  設定がなければstructured `skipped`を成果として残す。
- Physical HIL workflowはmanual-onlyかつread-onlyで、`preflight`と`diag`までを対象とする。
  physical deployやBridge-driven Golden HILを実行したとは主張しない。
- Product child CIはnative unit testを実行する。Luckfox SDKが必要なproduction buildと、
  CI上のarmhf contract stubは区別して記録する。

workflow固有のsecret、runner、成果物契約は[workflow README](../.github/workflows/README.md)を参照する。

## 既知の制約

| 領域 | 現在の状態 |
|---|---|
| Renode MCU | setup／installerとerror-only runtimeまで。`.resc`生成と共通lifecycleは未実装 |
| ESP32 QEMU | setupと手動runnerの足場まで。GAR runtime lifecycleは未実装 |
| AWS SSM simulation | setup optionのみ。通常はSSH Remoteを使用 |
| Wokwi scenario | Product所有のWokwi形式を使用。共通Bridge scenarioへの統一途中 |
| Physical Golden HIL | read-only preflight／diagまで。自動deployと物理操作adapterは未実装 |
| Full-image provisioning | SSH application deployとは別契約。NXP UUU等のUSB recovery backendは未実装 |
| Target資産の純化 | RK3506 capabilityはProduct-neutral化済み。Linux simulation runtimeや旧RV1106資産にはGarStream由来の名称・周辺構成が残る |

最後の項目は重要な設計負債である。Target Packが保持するのはBoard capability、OS、toolchain、
provisioning、lifecycleまでとし、ILI9341、KY-040、menu、TX/RX用途、配線はPeripheral／Product／Bindingへ
分離する。完了条件は[Target Pack戦略](../info/06_TARGET_PACK_STRATEGY.md)を正本とする。

## 完了判定

変更を「完了」と呼ぶには、該当する層で次を満たす。

1. `make check`または該当repositoryの品質チェックが通る。
2. artifact／diagnostic／scenario結果が機械可読である。
3. deployした場合は、稼働build IDと配置artifactのbuild IDが一致する。
4. 実機を主張する場合は、simulation結果ではなく対象Targetで確認している。
5. 未実装backendやskipped CIを成功扱いしない。

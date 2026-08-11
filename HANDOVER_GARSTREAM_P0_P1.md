# GarStreamTx/Rx → GAR P0/P1 実装引き継ぎ

最終更新: 2026-08-11

この文書は、別セッションの SOL が過去のチャットログを読まずに、
GarStreamTx/Rx を通して見つかった Gapless Agent Runtime の P0/P1 を
実装・検証・commit・pushするための作業正本である。

運用規約の正本は `AGENT.md`、アーキテクチャの正本は
`docs/02_ARCHITECTURE.md`と`docs/08_REPOSITORY_LAYOUT.md`。この文書はそれらを
上書きせず、今回の作業順と現在状態を固定する。

---

## 0. SOL への実行依頼

計画だけ作って停止せず、P0を完了させてから P1 を順番に実装する。
作業中に別の一般化案を思いついても、P2より先へ広げない。

開始時に次を完全に読む。

1. `/home/user/Yurufuwa/GAR/GaplessAgentRuntime/AGENT.md`
2. `/home/user/Yurufuwa/GAR/GaplessAgentRuntime/docs/02_ARCHITECTURE.md`
3. `/home/user/Yurufuwa/GAR/GaplessAgentRuntime/docs/08_REPOSITORY_LAYOUT.md`
4. この文書

コマンド操作は原則`gar`経由。GAR本体の開発チェックは`make check`。
生SSHは、新しい診断経路の最初の事実確認や、現時点で`gar`に入口がない
実機診断に限定する。同じ生操作を二度必要とするなら、P1の`gar ... diag`
またはTarget recipeへ収容する。

---

## 1. 結論と今回のゴール

GarStreamTx/Rx の最終アーキテクチャはGAR思想におおむね沿っている。

- WSL control plane、Local/Codespaces BuildEnvironment、EC2 simulation、実機を
  1つの操作面で扱った。
- TXは`/dev/video0`、RXは`/dev/gpiochip*`と`/dev/spidev*`をsim/実機で共通化した。
- PnP/RTP/メニューはproduct、接続・artifact・仮想device・Target recipeはGAR側に置いた。
- RXはaarch64 EC2とarmv7l Lyraで別バイナリだが、同じC++ source、
  device I/F、protocol、state logicを使っている。

今回のゴールは、この成功を「このPCで一度動いた」状態から、
次の状態へ引き上げること。

> clean cloneから第三者とAIが、機械可読な診断とE2E判定を使って、
> TX/RXシステムを再現できる Golden Reference にする。

---

## 2. 現在の動作済み状態

最後に確認できていた機能:

- Raspberry Pi 5 TX が Source を自己広告する。
- Luckfox Lyra RX が TX を検出し、Source選択後にlease付き送信要求を送る。
- TXからRXへMJPEG/RTP/UDPで実映像が届く。
- TX/RXのILI9341に映像とローカルOSDが表示される。
- TXのOSDはprogram feedに混入しない。
- TX/RXのKY-040は1 detent = 1 stepで動作する。
- RXのGray-code decoder修正はhost unit test、EC2 sim、Lyra実機で確認済み。
- LyraのSPIは現在`GAR_SPI_MAX_HZ=24000000`で実用的な更新速度を確認済み。
- EC2 simでPC camera → TX `/dev/video0` → UDP → RX →
  `/dev/spidev0.0` → Virtual Hardware Panelを確認済み。
- Bridgeのrotary `+1` / `-1` / pressがアプリの1イベントと一致する。

接続名はIPではなくSSH config aliasを使う。IPは変化する前提。

| 役割 | workspace | simulation host | physical target |
|---|---|---|---|
| TX | `Local/GarStreamTx` | `vibecode-graviton-tx` | `raspi5` |
| RX | `Local/GarStreamRx` | `vibecode-graviton-rx` | `luckfox-lyra` |

`.gar/config.json`にはこのworkspaceとaliasが登録済み。ただし、
machine-local stateなのでGitに入れず、artifactの再現性に依存させない。

---

## 3. 現在のGit状態

### 3.1 cleanでpush済みのproductリポジトリ

| repository | branch | HEAD | 状態 |
|---|---|---|---|
| `/home/user/Yurufuwa/GarStreamTx/sources/gar-stream-tx` | `main` | `3906d70` | clean / pushed |
| `/home/user/Yurufuwa/GarStreamTx` | `GarStreamTx` | `0251f6f` | clean / pushed |
| `/home/user/Yurufuwa/GarStreamRx/sources/gar-stream-rx` | `main` | `c8e700e` | clean / pushed |
| `/home/user/Yurufuwa/GarStreamRx` | `GarStreamRx` | `8e25e04` | clean / pushed |

Product parentは共に`ThousandsOfTies/gar-build-env`のproduct branch。
Product childは`ThousandsOfTies/gar-stream-tx`と`ThousandsOfTies/gar-stream-rx`。

### 3.2 GaplessAgentRuntimeの未commit変更

Path: `/home/user/Yurufuwa/GAR/GaplessAgentRuntime`

Branch/remote state:

```text
main @ df13dd4
origin/main @ df13dd4
```

次の6ファイルはユーザー依頼とGarStream実機展開で生まれた意図した実装変更。
破棄・reset・checkoutしない。

```text
M scripts/gar_lib/commands/setup/workspace_setup.py
M scripts/gar_lib/simulation/runtime/linux_systemd.py
M scripts/gar_lib/target/file_transfer.py
M tests/test_gar_linux_systemd_environment.py
M tests/test_gar_target_architecture.py
M tests/test_gar_workspace_setup.py
```

これらに加え、この引き継ぎ作成による文書差分がある。

```text
M  HANDOFF.md
?? HANDOVER_GARSTREAM_P0_P1.md
```

文書差分も破棄せず、実装commitと混ぜるかは差分の意味に応じて判断する。

内容:

- workspace登録済み一覧は通常表示で番号を出さず、削除/修正/選択時だけ番号付きで再表示。
- 一覧と入力promptの間に空行を追加。
- simulation runtimeのファイル更新を`.gar-new` → atomic `mv`に変更。
- root SSHのBuildroot Targetでは`sudo`なし、通常userでは`sudo -n`を使い分ける。
- それぞれに回帰testがある。

現在の検査結果:

- Ruff lint: pass
- unittest: 340 tests pass
- `make check`: **fail**
- 失敗理由: Ruff format checkが次の2ファイルの再formatを求めている

```text
scripts/gar_lib/target/file_transfer.py
tests/test_gar_target_architecture.py
```

最初に対象をRuff formatし、`make check`全体を通す。

### 3.3 gar-toolsの未commit変更

Path: `/home/user/Yurufuwa/GAR/gar-tools`

Branch/remote state:

```text
main @ 6d45ae7
origin/main @ 6d45ae7
```

これも意図した変更。破棄しない。

```text
M  README.md
?? targets/luckfox-rk3506/
?? tests/test_luckfox_lyra_target.py
```

`targets/luckfox-rk3506/`には次がある。

- `target.json`: RK3506 / armv7l / Buildroot / BusyBox / SSH Target定義
- `provisioning/buildroot-busybox/prepare.sh`
- root専用の限定installer `gar-target-install`
- BusyBox init launcher template
- 現在のILI9341/KY-040 simulation hardware CSV
- Targetとprovisioning contractのテスト

現在の検査結果:

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 41 tests pass
- 最終的に`make check`とGitHub Actionsも確認する。

### 3.4 submodule pointerの未同期

TX/RX parentの`sources/gar-tools`は現在ともに次を参照している。

```text
d93cd69 sources/gar-tools
```

このcommitにはRK3506 Targetがない。P0でgar-toolsをcommit/pushした後、
少なくともGarStreamRx parentのpointerをそのcommitへ更新する。
TX pointerは、新commitがRK3506追加だけなら必須ではない。
後続で共通runtime/contractも変更した場合は両productを更新する。

---

## 4. 決定済み事項—再議論しない

1. **RX-driven PnP**
   - TXはRX host/addressを設定しない。
   - TXがSourceを自己広告する。
   - RXがSourceを保持・選択し、lease付き送信要求を出す。

2. **TX/RXは別workspace・別panel**
   - ルートHTMLに両方を詰め込まない。
   - panelはproductごとのVirtual Hardware Panelとする。

3. **Program feedはclean**
   - TXのメニュー/OSDはTXのローカルLCDのみ。
   - RXへ送る映像にUIを合成しない。

4. **simulation専用app logicを作らない**
   - 差し替えはV4L2/GPIO/SPIのdevice/runtime側に閉じ込める。
   - アプリはBridgeやHTMLを直接呼び出さない。

5. **実機にsimulation dummy deviceを配置しない**
   - 実機はreal GPIO/SPI/video deviceを使う。

6. **実行target上で場当たり的にbuildしない**
   - WSL/Local/Codespacesでbuildし、artifactをEC2/実機へ一方向に運ぶ。

7. **「同一バイナリ」を異ABI間で強制しない**
   - Exact binary parityはCPU/ABI/libcが一致する場合だけ。
   - Lyraでは同一source/device contract/behaviorをパリティとする。

8. **GARはproduct runtimeにならない**
   - PnP、RTP、メニュー、映像処理はGarStream側の責務。
   - GARはbuild/deploy/observe/diagnose/scenarioとTarget recipeの操作面。

9. **現在のLyraはOS/rootfs全体更新に戻さない**
   - 必要runtime、plugin、kernel moduleはapplication artifactに同梱。
   - board設定は限定された`configure-target`とTarget recipeで扱う。
   - i.MX + uuuのimage updateはP2の別Targetで実証する。

---

## 5. 責務境界

| 所有者 | 置くもの | 置かないもの |
|---|---|---|
| GaplessAgentRuntime | workspace/system graph、BuildEnvironment、artifact store/schema、access、lifecycleの操作面、diagnostics/scenario、JSON/exit code | PnP/RTP、product UI、board固有shell本体 |
| gar-tools / Target | board/OS/toolchain/provisioning、pin/bus capability、pinmux/DT/kernel、simulation adapter | 特定productのSource選択やmenu logic |
| GarStream product | PnP/RTP、GStreamer pipeline、menu/UI、device requirements、product scenario、性能/切断復旧/security | 汎用SSH/ADB搬送、汎用OS installer |
| machine-local binding | SSH alias、実際の配線、GPIO offset、必要なpeer override | ソース、共有artifact、Git管理するdefault |

現在`gar-tools/targets/luckfox-rk3506/hardware/`にILI9341/KY-040構成が入っているが、
これはGolden Referenceを動かす暫定contract。P1で次の3層へ分離する。

1. Product requirements: 必要なsignal/device/BOM
2. Target capabilities: boardで使えるpin/bus/mux/voltage/driver
3. Binding: その実機での配線とoffsetの対応

---

## 6. P0—先に必ず完了する

### P0-1. 現在の未commit変更を正本化する

依存順に分けてcommit/pushする。関係ない変更を一つのcommitに混ぜない。

1. GaplessAgentRuntime
   - 2ファイルをRuff format。
   - `make check`を完走。
   - setup UX / atomic sim deploy / root SSH Targetの変更を、意味単位が明確なcommitにする。
   - `main`へpushし、GitHub Actionsをgreenにする。

2. gar-tools
   - RK3506 Targetのテストと`make check`を実行。
   - `targets/luckfox-rk3506/`をcommitし、`main`へpush。
   - GitHub Actionsをgreenにする。

3. GarStreamRx parent
   - `sources/gar-tools`を新しいgar-tools commitへ更新。
   - 必要ならREADMEの参照を同期。
   - `GarStreamRx` branchへcommit/push。

4. GarStreamTx parent
   - gar-toolsの共通runtime/contractが変わった場合のみpointer更新。

コミット順は必ず「子/共有repo → parentのgitlink」にする。

### P0-2. Targetの観測とdeploy収束を実装する

現在`gar target`には`prepare/build/deploy/fetch`しかない。
Simulation側の`status/log/diag --json`と非対称。

必要なcontract:

- Target recipe経由でapplicationのstatus/log/healthを取得できる。
- GAR coreはproduct-specific process managerにならず、Target capabilityを呼ぶ。
- deploy後に新artifactを起動/reloadし、healthと稼働artifact hash/build IDを確認する。
- 起動またはhealthに失敗したら、直前releaseへ戻せるか、少なくとも
  「配置済みだが未稼働」を非0とJSONで明示する。
- systemdとBusyBox initの差はTarget recipe/adapterに閉じ込める。
- auth/sudoが必要な場合はTerminal Bridgeへhandoff。

コマンド名は既存の語彙と整合させる。実装前にcommand名だけの大規模な再編はしない。
最低限`status`、`log`、`diag --json`が必要。

### P0-3. Artifact provenance/schema v2

現在のartifactはdeploy先に対する条件が弱く、誤ABI配布やtools driftを
配置前に十分に拒否できない。

少なくとも次をschemaとsnapshot metadataに持たせる。

```text
schema_version
artifact kind
product/workspace
target ID
architecture
ABI/libcまたはtoolchain triple
entrypoint
source commit
gar-tools commit / target recipe version
file checksums
build ID / timestamp
kernel release/vermagic依存（必要なartifactのみ）
```

後方互換を明示的に決める。既存manifestを無言で壊さない。
deploy前にTargetの実測capabilityとartifact metadataを比較し、
aarch64 artifactのarmv7l Targetへの転送などを転送前に拒否する。

### P0完了条件

- 関連repoの意図した変更がすべてcommit/push済み。
- 各worktreeがclean。
- GaplessAgentRuntimeとgar-toolsのActionsがgreen。
- clean cloneが`luckfox-rk3506` Targetを検出・選択できる。
- 通常user+sudoのRasPiとroot/no-sudoのLyraで同じ`gar target` 操作面を使える。
- deploy後の稼働バージョンを機械可読に確認できる。
- 誤Target/誤arch artifactは転送前に失敗する。
- 実機を使う最終検証以外、繰り返しの生SSH操作を必要としない。

---

## 7. P1—GarStreamをGolden Referenceにする

P1は次の順番で行う。System graph、hardware、E2Eを同時に大きく書き換えない。

### P1-1. Machine-local情報をbuildから排除する

現在`/home/user/Yurufuwa/GarStreamRx/scripts/product-sim-build.sh`は、
GARの`.gar/config.json`を既定pathから読み、TX private IPをsimulation service artifactに
埋め込む。これはbuildとruntime topologyの責務混同。

- buildは接続先に依存しないartifactを作る。
- peer、host、port、workspace間linkはdeploy/start時にGARが注入する。
- product hookがGARの私有JSON構造を直接パースしない。
- broadcastが通る環境ではpeer override自体を不要にする。

また、GAR正本は`/etc/gar/<app>.env`を通常deployで上書きしないとするが、
RXは`config/gar-stream-rx.target.env`がある場合にartifactへ含めてdeployする。
次のどれかに統一し、暗黙の上書きをやめる。

- 初回configureのみ
- 明示的な`--with-config`
- 独立した`target configure`

既存の実機envを誤って消さないこと。

### P1-2. System topologyを一級モデルにする

GarStreamは単一workspaceではなく2ノードシステム。例:

```yaml
name: GarStream
nodes:
  tx:
    workspace: Local/GarStreamTx
    role: source
  rx:
    workspace: Local/GarStreamRx
    role: receiver
links:
  discovery:
    protocol: udp
    port: 5601
    from: rx
    to: tx
  media:
    protocol: rtp/udp
    port: 5600
    from: tx
    to: rx
```

実際のschema/command名は既存CLIに合わせて設計する。必要な能力:

- 複数workspaceのbuild/deploy/start順を解決。
- nodeごとのsim/target connectionを解決。
- linkからruntime config/firewall/diagnostic対象を生成。
- system全体のstatus/diag/testを1つのJSONで返す。
- PnP protocol自体はGarStreamに残す。GARはノードの構築・観測だけ担当。

最初から任意Nノードの巨大frameworkにせず、TX/RXの2ノードを
最小事例として実装・testする。

### P1-3. Hardwareを3層に分離する

今回得られた実機条件を正式なcontractへする。

- Product requirements
  - ILI9341 SPI display
  - KY-040 A/B/SW
  - USB UVC camera
  - 必要な最低SPI速度、電圧、フレームレート
- Target capabilities
  - boardのpin/bus/mux/voltage
  - kernel driver/device node
  - init/privilege/toolchain capability
- Binding
  - 物理pin ↔ signal ↔ GPIO offset
  - SPI bus/CS/max Hz
  - 必要なDT/pinmux設定

目標は、次を事前に機械判定できること。

- pin conflict
- 必要device/driverの不足
- voltage不整合
- bus・CSの重複
- SPI上限がproduct requirementを満たさない

例として`gar hw validate --json`相当の結果を返す。
実際の配線図/表はこのbindingから生成できる形を目指す。

### P1-4. Multi-node E2E scenarioとCI

GAR coreは複数Bridge/nodeに対するscenario実行・計測・assertionを提供し、
GarStream productが具体的なGolden scenarioを所有する。

必須scenario:

1. TXが`source_announce`する。
2. RXがTXをSource一覧に追加する。
3. RXがSourceを選択し`stream_request`を送る。
4. TXがlease中のRXへフレームを送る。
5. RXのILI9341 framebuffer/update countが変化する。
6. rotaryの1 detentで1つだけmenu stateが動く。
7. pressで決定/EXITする。
8. TX停止でlease/sourceが失効する。
9. TX再起動で再検出・再接続する。

機械可読な判定値:

- source/lease state
- last frame timestamp
- received/sent frame count
- FPS/drop count/latency
- framebuffer checksumまたはupdate count
- encoder event count
- menu state
- node/service health
- artifact build ID/hash

CIの役割:

- product child: unit/lint/build
- product parent: sim/target artifact manifestとarchitecture validation
- GAR core: system/scenario/diagnostic contractのunit/integration test
- gar-tools: Target manifest/provisioning/simulation adapter test
- EC2 E2E: workflow_dispatchまたは夜間実行
- physical HIL: 常時CI必須にせず、明示実行と結果記録

### P1-5. Clean-room verification

最後に既存workspaceの生成物を使わず、別directoryへcloneして確認する。

確認順:

1. GARをfresh clone。
2. `make init`。
3. TX/RX product workspaceを登録。
4. Target/environment/SSH aliasを`gar setup`で設定。
5. TX/RXのsim app/runtime build/deploy/start。
6. multi-node E2E scenarioを実行しJSON PASS。
7. Target build。
8. 既存実機へdeployする前にartifact compatibilityを確認。
9. ユーザー承認後にHIL deploy/diag。

初回成功までに必要だった人間入力回数、生コマンド回数、
所要時間も記録する。これが第三者UXのKPI。

### P1完了条件

- build artifactがmachine-local GAR config/IP/pathに依存しない。
- TX/RX topologyが宣言され、system全体を機械可読に診断できる。
- hardware requirement/capability/bindingが分離され、不整合を事前検出できる。
- Golden scenarioがTX→RX→display→rotary→切断復旧を無人判定する。
- product repoにCIがあり、通常の回帰がEC2/実機の目視に依存しない。
- clean-roomで同じ手順を再現できる。
- 主要repoがcleanで、必要なcommitは依存順にpush済み。

---

## 8. 最初の実行手順

まず、差分を保存したまま現状を確認する。`pull`、`reset`、`checkout --`を
先に行わない。

```bash
cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime
git status --short --branch
git diff --check
git diff

cd /home/user/Yurufuwa/GAR/gar-tools
git status --short --branch
git diff --check
git diff

cd /home/user/Yurufuwa/GarStreamRx
git status --short --branch
git submodule status

cd /home/user/Yurufuwa/GarStreamTx
git status --short --branch
git submodule status
```

このworkspaceではシェルコマンドに`rtk`が必要。
実際のツール呼び出しでは上記に`rtk`を付ける。

P0の最初の具体作業:

```bash
cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime
.venv/bin/ruff format \
  scripts/gar_lib/target/file_transfer.py \
  tests/test_gar_target_architecture.py
make check
```

これが通ったら、diffを再度レビューしてcommitする。
並行してgar-toolsのRK3506テストを確認可能。

---

## 9. 検証コマンドの正本

### GaplessAgentRuntime

```bash
cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime
make check
```

### gar-tools

```bash
cd /home/user/Yurufuwa/GAR/gar-tools
python3 -m unittest discover -s tests -p 'test_*.py'
make check
```

### RX native core

```bash
cd /home/user/Yurufuwa/GarStreamRx/sources/gar-stream-rx
cmake -S native -B native/build -DGAR_RX_BUILD_APP=OFF
cmake --build native/build
ctest --test-dir native/build --output-on-failure
```

### GAR経由のsimulation

```bash
cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime
gar sim app build --workspace Local/GarStreamTx
gar sim runtime build --workspace Local/GarStreamTx
gar sim runtime deploy --workspace Local/GarStreamTx
gar sim app deploy --workspace Local/GarStreamTx

gar sim app build --workspace Local/GarStreamRx
gar sim runtime build --workspace Local/GarStreamRx
gar sim runtime deploy --workspace Local/GarStreamRx
gar sim app deploy --workspace Local/GarStreamRx
```

実際のstart順やポートは新しいsystem topology/scenarioを正本にする。
AWS loginが必要な場合はvisible terminalでユーザーに引き渡す。
検証後に不要なEC2を起動したまま残さない。

### Physical Target

```bash
cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime
gar target build --workspace Local/GarStreamTx
gar target build --workspace Local/GarStreamRx
```

`prepare/deploy`はroot管理領域と実機に変更を加える。特にRXの
`configure-target`はLuckfox Lyra Plusのboot DTBを限定的に更新し、終了値10で
reboot requiredを通知する。実行前に対象、diff、必要性を確認する。

既存Lyraには元boot imageの保全用copyが`/var/lib/gar/backups/`にある。
これを通常deployで削除しない。

---

## 10. 既知の設計課題

P0/P1実装時に落とさないこと。

1. **Target commandの非対称**
   - simulationにはstatus/log/diagがあるがTargetにはない。

2. **deploy successとrunning versionが同じではない**
   - EC2 simで新バイナリ配置後も旧processが残った事例がある。

3. **artifact provenance不足**
   - source/tools/recipe/arch/ABI/kernel依存の記録が弱い。

4. **buildがruntime topologyを読む**
   - RX sim buildがmachine-local`.gar/config.json`に依存。

5. **複数gar-tools copyのversion drift**
   - sibling repo、product submodule、`.gar/tools`の互換version拘束がない。

6. **Target capabilityとproduct hardwareの混同**
   - RK3506 Targetのhardware CSVがGarStreamRx固有構成を含む。

7. **永続envの上書きcontractが不統一**
   - GAR文書とRX artifactの現状が一致していない。

8. **product CIの不足**
   - GarStreamTx/Rxのparent/childに定常的なGitHub Actionsがない。

9. **「同じバイナリ」文言が強すぎる**
   - GARの一般文書をExact/Source/Behavioral parityの段階表現に更新する。

---

## 11. P2以降—今回は実施しない

- i.MX + uuuによるimage全体書き込みTarget。
- Renode/STM32などSSHではないMCU Target。
- Linux + RTOS AMPの統一trace。
- GarStreamのproduction security/auth/encryption。
- 一般的な大規模fleet management。

P0/P1のGolden Referenceが完成する前にこれらへ広げない。

---

## 12. 最終成果に必要な報告

別セッションの SOL は、最終報告に少なくとも次を含める。

- P0/P1の完了/未完了表。
- 変更した各repoのcommit hashとpush先branch。
- Actions/CIのURLと結果。
- clean-room testの条件と結果。
- simulation E2EのJSON結果。
- physical HILで確認した範囲と、未実施の物理確認。
- 生SSH/手動操作が残った場合は、理由と次に収容する契約。
- 新しい設計決定と、見送った案。
- 全関連repoの最終`git status --short --branch`。

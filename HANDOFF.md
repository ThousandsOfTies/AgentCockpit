# GaplessAgentRuntime 実装レビュー引き継ぎ

最終更新: 2026-08-09

> **2026-08-11:** GarStreamTx/Rx から得られた P0/P1 の実行作業は
> [`HANDOVER_GARSTREAM_P0_P1.md`](HANDOVER_GARSTREAM_P0_P1.md) を最初に読むこと。
> 同文書に現在のdirty worktree、commit順、Golden Referenceの完了条件を記録している。

この文書は、全体レビュー後の実装状態と、今後判断が必要な項目を短く引き継ぐためのものです。
操作手順は`docs/`、設計境界は`GAR_LIB_STRUCTURE.md`を正本とします。

## 現在の結論

`cli.py`へ集中していたparser・dispatch・表示責務はcommand moduleへ移り、
`api.py`、build、artifact、simulation、targetがprogrammaticなobject境界として機能する
構成になりました。短さより処理順が読めることを優先し、動的method lookupやreflection、
tuple indexによる状態表現を避けています。

品質確認の正本は`make check`です。テスト件数は追加で変わるため、文書へ固定値を書きません。

## 今回整理した領域

### CLIとAPI

- `cli.py`はcommand moduleが所有するparserを合成し、top-level adapterを選ぶ薄い入口。
- `commands/sim.py`と`commands/target.py`は明示的な`match`でactionをdispatch。
- `gar sim io`はaction別parserで必須引数を表現。
- `api.py`はprintせず、artifact・diagnostic・host state・hardware control resultを返す。
- CLIが人間向け表示とJSON表示を担当。

### Workspaceと設定

- `Workspace`は`WorkspaceConnection`、`SelectedEnvironments`、`Ec2Settings`、
  `DockerSettings`、`TargetSettings`、`AdbSettings`、`Esp32Settings`を保持。
- JSON mappingは`resolve_workspace()`の境界で具象設定objectへ変換。
- `selected_target`と`hardware_dir`をWorkspaceへ含め、simulation/targetがglobal configを
  読み直さない構成にした。
- hardwareは明示path、product `hardware/`、product内gar-tools、共有gar-toolsの順に探索。
- workspace選択は`load_config(workspace_selector=...)`の呼び出しcontextだけで有効。
  setupの選択をmodule globalへ残して後続commandへ漏らさない。

### Buildとartifact

- BuildEnvironmentは`LocalBuildEnvironment`と`CodespacesBuildEnvironment`の2種類。
- ESP32専用BuildEnvironmentは廃止し、local/Codespacesの共通実装を使う。
- ESP32固有のPlatformIO処理もproduct workspaceの`product-target-build.sh`が担当。
- typed artifact manifest parserが`files`形式とproduct `artifact`形式を検証。
- artifactは`.gar/artifacts/<workspace-id>/<kind>/<build-id>/`へ不変snapshotとして保存。
- `SIM_APP`、`SIM_RUNTIME`、`TARGET_APP`は別latest pointerを持つ。

### Setupとenvironment

- 単一fileだったsetup commandを`commands/setup/` packageへ分割。
- workspace、target、environment選択を別moduleにし、`command.py`がphase順を示す。
- setup状態はenum/dataclassで表し、object sentinelやtuple indexを使わない。
- environmentはcategory別baseと明示的`ENVIRONMENT_OPTIONS` registryを使用。
- `pkgutil`・reflection・class属性の後付け変更は行わない。
- Renode/AWS SSM等の大きい導入処理は`environments/installers/`へ分離。
- archive展開はpath traversalとlinkを拒否する共通処理を使う。
- target manifestのpath/backend不整合はsetup時に表示する。

### Simulation

- `runtime_host`を`session_host`へ改名し、remote SSH runtimeだけがhostを返す。
- local Docker/Wokwi/MuJoCoがEC2設定へfallbackしない。
- systemd `RuntimeDirectory=gar`、lifecycle commandはfail-fast。
- Wokwi/MuJoCo process stateは共通storeでatomic write/file lockし、PID、command、
  `/proc` start timeで所有確認する。
- repeated startはidempotentで、stale PIDから無関係processをkillしない。
- MuJoCo app deployはmanifest記載のassetを`.gar/mujoco/`へ安全にmaterializeし、modelを検証する。
- `HardwareControlResult`とdiagnostic modelをCLI側でrenderする。

### Physical Target provisioning

- `gar target prepare`を共通CLIとして追加し、OS依存処理はRuntime本体ではなく
  `gar-tools/targets/<id>/target.json`の`provisioning` recipeから解決する。
- Raspberry Pi 5 / Raspberry Pi OS recipeはreference runtime package、`gar`service
  account、device group、限定sudo installer、共通`gar-app@.service`を冪等に導入する。
- product artifactの標準entry pointは`/opt/gar/apps/<app>/run`。root所有service unitは
  productから配布しない。
- 永続設定は任意の`/etc/gar/<app>.env`へ分離し、通常deployでは上書きしない。
  共通serviceはenvがある場合だけ読み込み、deploy後にenable/restartする。
- Raspberry Pi実機へsimulation dummy device、CUSE、gpio-sim、Web Panelを導入しない。
- 旧`/etc/sudoers.d/90-gar-deploy`の`NOPASSWD: ALL`はrecipeで限定ruleへ移行済み。
- GarStreamTxで実機prepare/build/deploy、非rootでのapplication importまで確認済み。

### ローカル補助ツール

- terminal requestはtyped storeでatomic publishし、CLI/setup/MCPが共有。
- MCP request IDはvalidationとpath containmentを行う。
- MCPは`resources/list`、`prompts/list`、`ping`へ応答し、不正JSON-RPCでもprocessを継続する。
- EC2 port forwardはPython実装がPID・host・ports・SSH commandを検証し、shellは薄い入口。
- scenario runnerはload/validate/executeを分離し、不正入力でtracebackを出さない。
- USB list失敗を空の成功結果として扱わない。
- DSM generatorは`--check`とsyntax error検出に対応。
- Makefile/CIの`make check`がRuff、unittest、DSM、shell構文、Node testをまとめて確認する。
- VS Code extensionのrequest validation/shell quotingはNode標準testで確認する。
- GitHub ActionsのPython matrixは3.11〜3.14。
- 巨大だったCLI testはsetup/config、USB、terminal/HW、sim IO、sim infra、target、codeへ
  分割し、共通fixture/assertionを`tests/support/gar_cli_test_support.py`へ置く。

## 現在の主要経路

```text
gar command
  → command-owned parser / CLI adapter
  → resolve_workspace()
  → Gar(workspace).sim / target
  → build environment または composition
  → artifact snapshot
  → simulation runtime / physical target
```

ESP32もLinux targetも同じ経路です。target固有compile手順はproduct hook、GARのtarget層は
artifact検証とdeploy/flashを担当します。

## 関連workspace

| パス | 役割 |
|---|---|
| `/home/user/Yurufuwa/GAR/GaplessAgentRuntime` | GAR実装と文書の正本 |
| `/home/user/Yurufuwa/GAR/gar-tools` | target manifest、hardware、runtime資産 |
| `/home/user/Yurufuwa/GarAdhocApp` | Linux app product workspace |
| `/home/user/Yurufuwa/GarAdhocApp/sources/gar-adhoc-app` | Linux app source submodule |
| `/home/user/Yurufuwa/GarVibeRemote` | Vibe Remote product workspace |
| `/home/user/Yurufuwa/GarVibeRemote/sources/gar-vibe-ui` | VS Code bridge / M5StickC source submodule |

Vibe Remoteの旧sibling checkoutを新しい手順へ持ち込まず、`GarVibeRemote/sources/`を使ってください。

## 残る制約

- Renode、ESP32 QEMU、AWS SSM runtimeはerror-only実装で、setup/依存確認まで。
- network workspaceを直接buildするBuildEnvironmentはない。
- Wokwi固有scenarioは共通Bridge JSON contractへ統一途中。
- `.gar/config.json`の保存表現は後方互換のmapping。runtimeへ渡すWorkspaceはtyped。
- config全体のschema/version migrationと標準Python package化は、必要性を確認してから行う。

`ssh_remote`は`gar setup --ec2-host HOST`によるworkspace設定が必須で、個人環境名への
fallbackはありません。port-forward Make targetも`EC2=HOST`を省略できません。

## 次回の開始手順

```bash
git status --short
git pull --ff-only
make check
```

作業中差分がある場合はpullより先に内容と所有者を確認します。生成文書は
`tools/gen_gar_lib_dsm.py`で更新し、`--check`で同期を確認します。

# リポジトリ配置と資産の責務

GARは、Runtime core、Target Pack、Build environment、Productを別repositoryとして扱う。
この分離は配布形態の都合ではなく、依存方向を守るための設計契約である。

## 全体像

```text
Yurufuwa/
├─ GAR/
│  ├─ GaplessAgentRuntime/     # gar CLI、orchestration、artifact、diagnostic
│  ├─ gar-tools/               # Target Pack、simulation provider、Board capability
│  └─ gar-build-env/           # devcontainer／Codespacesの共通雛形
└─ ProductWorkspace/
   ├─ scripts/                 # Product build hooks
   ├─ hardware/                # requirementsとTarget binding
   ├─ gar-system.json          # 必要な場合のみ
   └─ sources/
      ├─ product-source/       # Product実装の固定済みsource
      └─ gar-tools/            # buildに使うTarget資産の固定済みsource
```

利用者がsibling `gar-tools`を持たない場合、`gar setup`は
`GaplessAgentRuntime/.gar/tools`へ取得できる。開発者のsibling checkoutと利用者のauto-cloneは
同じ役割を持つが、正本の選択を曖昧にしない。

## Repositoryごとの責務

| Repository | 所有するもの | 所有しないもの |
|---|---|---|
| GaplessAgentRuntime | CLI、workspace、build協調、artifact store、system／hardware契約、diagnostic | Product source、Board固有pin、OS別provisioning script |
| gar-tools | Target manifest、Board capability、toolchain探索、OS／init recipe、simulation provider | Product menu、protocol、TX/RX用途、Product固有配線 |
| gar-build-env | devcontainer、共通build依存、Product workspace生成 | Product behavior、Target deploy logic |
| Product workspace | build hooks、Product requirements、Binding、system topology、scenario、source固定 | GAR coreのtransport、汎用Board定義 |
| Product source | application／firmware、driver adapter、protocol、UI、unit test | machine-local Host、credential、GAR state |

## GaplessAgentRuntime内部

```text
GaplessAgentRuntime/
├─ scripts/
│  ├─ gar                         # thin entrypoint
│  └─ gar_lib/
│     ├─ commands/                # argparse、対話、表示、CLI adapter
│     ├─ core/                    # workspace、config、安全な共通値
│     ├─ build/                   # Local／Codespaces BuildEnvironment
│     ├─ artifacts/               # manifest、provenance、不変snapshot
│     ├─ access/                  # SSH、ADB、Docker、AWS等のtransport
│     ├─ simulation/              # runtime、host、Bridge control、diagnostic
│     ├─ target/                  # compatibility、transfer、lifecycle
│     ├─ system/                  # multi-node topologyとscenario
│     ├─ environments/            # setup option、registry、installer
│     └─ vscode/                  # Terminal Bridge request／status
├─ tests/                         # core contract tests
├─ docs/                          # 現行の操作・設計資料
├─ info/                          # 背景、位置付け、将来方針
├─ infra/                         # simulation host IaC
├─ tools/                         # MCP、VS Code extension、開発補助
├─ codespaces/                    # sshfsの一時mount point
└─ .gar/                          # machine-local state（Git管理外）
```

`scripts/gar_lib`の正確なmodule一覧と参照関係は、手書き文書へ複製せずsource codeを正本とする。

## 依存方向

```text
commands
  → programmatic API
  → build / simulation / target / system use case
  → environment composition
  → access capability
  → external tool or host

Product requirements ──┐
                       ├─ Binding ── Target capabilities
Peripheral adapter ────┘
```

setup optionは依存確認と選択metadataを持つ。runtime objectとして再利用せず、保存したIDから
composition境界で具象objectを構成する。

## Artifactの配置

BuildEnvironmentがProduct hookを実行し、用途別snapshotを作る。

```text
.gar/artifacts/<workspace-id>/
├─ sim_app/<build-id>/
├─ sim_runtime/<build-id>/
└─ target_app/<build-id>/
```

各directoryにはartifact本体、`artifact.json`（配置manifest）、`artifact-info.json`（GARが生成する
provenance metadata）、checksumを保持する。`latest.json`は最新snapshotを指すだけで、snapshot自体は
build後に変更しない。Target上では`artifact-info.json`の内容を`.artifact-info.json`へコピーし、配置済み
buildのmarkerとして使う。`deploy`は`build`／`fetch`を暗黙実行しない。

旧snapshotに残る`gar-artifact.json`と、既存Targetに残る`.gar-artifact.json`は読み取り互換で扱う。
新しくcapture／deployするartifactは`artifact-info.json`と`.artifact-info.json`を生成する。

Productのbuild staging directoryやCodespaces内の一時artifactは正本ではない。WSL側storeへcaptureされ、
schemaとchecksumを通過したsnapshotだけがdeploy対象になる。

## Machine-local state

`.gar/`はrepositoryへcommitしない。

| Path | 内容 |
|---|---|
| `.gar/config.json` | workspace、選択environment、接続alias |
| `.gar/tools/` | setupが取得したgar-tools checkout |
| `.gar/artifacts/` | immutable artifact snapshots |
| `.gar/terminal-requests/` | visible terminalへの要求 |
| `.gar/terminal-status/` | request実行状態 |
| `.gar/wokwi/`／`.gar/mujoco/` | local runtime workspace／state |

秘密鍵、token、cloud credentialをartifactやsystem schemaへ入れない。SSH config Host名やBridge URLなどの
個体差は実行時設定とする。

## Target Packの内部境界

```text
gar-tools/targets/<target-id>/
├─ target.json                    # identity、compatibility、backend、recipe
├─ hardware/capabilities.json     # Boardが提供する汎用resource
├─ provisioning/<os-recipe>/      # prepare、installer、lifecycle helper
├─ toolchain/                      # 必要な場合のSDK／sysroot探索
└─ README.md                       # boot、電源、recovery等の人間向け補足
```

Target Packへ置けるのは、Board／SoC／OS／toolchain／provisioning／recovery／generic capabilityである。
次はProduct側へ置く。

- ILI9341をProductのDISPLAYとして使う定義
- KY-040をmenu操作へ割り当てる定義
- TX／RX、Source、Profile等のProduct用語
- Product service名、環境変数、既定path
- 具体的な部品とphysical pinを結ぶ配線

汎用Peripheral driverを共有する場合は独立したPeripheral／Device Adapter資産にする。
そのPeripheralをProduct roleとBoard resourceへ割り当てるのはBindingである。

## Product workspace

再現可能なProduct workspaceは、sourceとgar-tools revisionを固定し、build hookを所有する。

```text
ProductWorkspace/
├─ scripts/
│  ├─ product-sim-build.sh
│  ├─ product-sim-env-build.sh
│  └─ product-target-build.sh
├─ hardware/
│  ├─ requirements.json
│  └─ bindings/<target-id>.json
├─ scenarios/
├─ gar-system.json
└─ sources/
```

すべてが必須ではない。単一node／hardware不要のProductはsystemやhardware contractを省略できる。
ただしbuild commandをGAR coreへ追加せず、Product hookでartifact contractへ変換する。

## 探索順と再現性

gar-toolsは次の優先順位で解決する。

1. 明示的な`GAR_TOOLS_ROOT`
2. Product workspace内の固定済み`sources/gar-tools`
3. GaplessAgentRuntimeと並ぶ開発者用sibling checkout
4. `.gar/tools`のauto-clone

build metadataには、実際に使ったgar-tools commitとdirty状態を記録する。別copyへ切り替わった場合、
Target recipe identityと一致しないartifactをdeployしない。

## 生成物と文書

- `docs/`は現在の操作契約だけを置く。
- `info/`は時間に依存しにくい背景と方針を置く。
- 一時的なhandover、完了済みTODO、作業中のGit statusはcommitへ残し、恒久文書にしない。
- Product固有配線、実機写真、Golden scenario説明はProduct repositoryへ置く。

## なぜGAR本体にgar-tools submoduleを持たないか

GAR利用者の入口を`clone → make init → gar setup`へ保つため、Runtime本体はgar-toolsを必須submoduleにしない。
一方、再現可能なProduct buildでは、Product workspaceが使用したgar-tools revisionを固定する。

この二つは矛盾しない。Runtime利用時の単純さと、Product build時の再現性を別の境界で満たしている。

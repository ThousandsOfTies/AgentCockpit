# Agent Terminal Bridge 設計メモ

> このドキュメントは **bridge の仕組み（request ファイル・extension・status）** を扱います。
> AI の**振る舞いルール**（いつ裏で実行し、いつ handoff するか）は [AGENT.md「Terminal 操作の原則」](../AGENT.md) を正本とします。

## 目的

Gapless Agent Runtime では、AI Agent がビルド、初期化、デプロイ、実行確認を進める。ただし `sudo` パスワード、`gh auth login`、クラウド認証などは AI に渡さず、人間が VSCode integrated terminal 上で直接入力する。

そのため、通常処理は AI 側の裏実行で進め、sudo/auth など人間入力が必要な場面だけ visible terminal へ handoff する（判断基準の詳細は [AGENT.md「Terminal 操作の原則」](../AGENT.md)）。
AI と VSCode terminal を直接つなぐのではなく、明示的な橋を置く。

```text
AI / Codex
  -> gar config command を裏で実行
  -> sudo/auth が必要なら gar terminal run
  -> .gar/terminal-requests/*.json
  -> Gapless Agent Runtime VSCode Extension
  -> VSCode Integrated Terminal
  -> Human sudo/auth input
```

## 構成

- `gar config` は最初に target を表示し、その後カテゴリ単位で状態を表示する。
  - Target
  - 開発環境
  - シミュレート環境
  - 実機環境
- 設定済みカテゴリは選択済み environment だけを表示する。
- 選択状態は `.gar/config.json` に保存する。
- `.gar/` は git 管理しない。
- `gar terminal run`、setup installer、MCPは共通の`TerminalRequestStore`を使い、
  `.gar/terminal-requests/*.json`をatomic publishする。
- environment が sudo/auth handoff を必要とした場合も同じrequest storeを使う。
- `gar config` は VSCode Terminal Bridge の導入状況を表示する。
- `tools/vscode-gar/` にVSCode extensionがある。
  - `.gar/terminal-requests/*.json` を監視する。
  - 要求を受けたら VSCode integrated terminal を作成する。
  - コマンドは `sendText()` で terminal に送る。
  - terminal 出力の捕捉や追加入力送信は行わない。AI は裏で状態確認して復帰する。
  - `Gapless Agent Runtime: Run gar config` コマンドも提供する。
  - request validationとshell quotingはNode標準testで回帰確認する。

## 使い方

AI の振る舞いルールは [AGENT.md「Terminal 操作の原則」](../AGENT.md) を優先する。
通常作業は裏で実行し、sudo/auth など人間入力が必要な時だけ visible terminal に handoff する。

### VSCode extension のローカルインストール

```bash
make init
```

その後、VSCode window を reload する。

### Agent / MCP から visible terminal に投げる

MCP 設定例は `make init` で生成される。

```bash
.gar/mcp-config.json
```

MCP tool `run_in_visible_terminal` は以下の request を作る。

```json
{
  "command": ".venv/bin/gar config",
  "cwd": "/path/to/GaplessAgentRuntime",
  "title": "Gapless Agent Runtime"
}
```

MCP を使わず CLI から同じ request を作る場合:

```bash
gar terminal run --title "Gapless Agent Runtime" --command ".venv/bin/gar config"
```

## Request / status lifecycle

extensionはrequestを検証し、terminalへ`sendText()`できた後だけ`processed/`へ移動する。
不正requestは`invalid` statusとして記録する。

- `.gar/terminal-requests/*.json`: 未処理要求
- `.gar/terminal-status/*.json`: started / invalid など

実行結果は terminal から読まず、AI が裏で状態確認コマンドを実行して判断する。

## gar configとの統合

`gar config` は VSCode Terminal Bridge の有無を確認する。

導入済みなら、AI は sudo が必要な処理を `gar terminal run` 経由で visible terminal に流せる。
未導入の場合は、TTY 実行時に `gar config` から直接導入できる。まとめて整える場合は `make init` を実行する。

MCP 設定は `make init` が `.gar/mcp-config.json` に生成する。

## 作らないもの

- terminal emulator
- sudo password 入力 UI
- shell / PTY の独自実装
- VSCode terminal の再実装
- Marketplace 公開前提の仕組み

## 保守時の確認

request store、MCP server、VSCode extensionの変更は`make check`でまとめて確認する。
人間入力後の成否はterminal出力の推測ではなく、対象のstatus／diag commandで再確認する。

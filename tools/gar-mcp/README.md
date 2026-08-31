# Gapless Agent Runtime MCP Server

Gapless Agent Runtime 用の最小 MCP server です。

VSCode integrated terminal を直接制御するのではなく、共通のtyped request storeから
`.gar/terminal-requests/*.json`をatomic publishします。`tools/vscode-gar`のVSCode extensionが
それを拾い、人間が見えるintegrated terminalにコマンドを送ります。status IDは単純な
request IDだけを受け付け、status directory外のpathは読みません。

AI の運用ルールは [`../../AGENT.md`「Terminal 操作の原則」](../../AGENT.md) を優先します。通常作業は裏で実行し、sudo password / GitHub 認証 / cloud auth など人間入力が必要な時だけ、この MCP server で visible terminal に handoff します。

## MCP 設定例

```json
{
  "mcpServers": {
    "gar": {
      "command": "python3",
      "args": ["/path/to/GaplessAgentRuntime/tools/gar-mcp/server.py"]
    }
  }
}
```

現在の環境向けの設定は `make init` で生成できます。

```bash
.gar/mcp-config.json
```

## Tools

### run_in_visible_terminal

VSCode integrated terminal で実行する request を作成します。

```json
{
  "command": ".venv/bin/gar config",
  "cwd": "/path/to/GaplessAgentRuntime",
  "title": "Gapless Agent Runtime"
}
```

### list_terminal_status

`.gar/terminal-status/*.json` を一覧します。

### get_terminal_status

指定 id の status を取得します。

## Protocol support

`initialize`、`tools/list`、`tools/call`に加え、空の`resources/list`・`prompts/list`と
`ping`へ応答します。JSON-RPC notification（idなし）は応答せず、invalid request/paramsや
malformed JSONを受けてもserver processを終了しません。

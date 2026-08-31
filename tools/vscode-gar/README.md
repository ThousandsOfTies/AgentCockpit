# Gapless Agent Runtime Terminal Bridge

VSCode integrated terminal に Gapless Agent Runtime の実行要求を流すための拡張です。

Agentは共通request store経由で`.gar/terminal-requests/*.json`に要求を書きます。拡張は
そのファイルを監視し、VSCodeの見えるterminalを開いてコマンドを送ります。requestは
`sendText()`成功後だけ`processed/`へ移動します。`sudo`のパスワード入力が必要な場合は、
そのterminalに人間が入力します。

## Agent からの使い方

```bash
gar terminal run --title "Gapless Agent Runtime" --command ".venv/bin/gar config"
```

## VSCode からの使い方

ローカルインストール:

```bash
make init
```

インストール後、VSCode window を reload してください。

Command Palette で次を実行します。

```text
Gapless Agent Runtime: Run gar config
```

## Request / Status

この拡張は以下を監視します。

```text
.gar/terminal-requests/*.json
```

terminal にコマンドを送ったら status を書きます。

```text
.gar/terminal-status/<request-id>.json
```

request validationとshell quotingはVS Code APIから分離した純粋ロジックとして
`node:test`で確認します。開発時はrepository rootで`make check`を実行してください。

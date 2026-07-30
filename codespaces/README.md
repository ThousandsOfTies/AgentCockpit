# Codespaces mount point

このディレクトリは `gar code start` が Codespaces の product workspace を
SSHFS で一時的にマウントする場所です。マウントされた内容は生成物であり、
Git では追跡しません。接続状態は
`~/.config/codespace-dev/state.json`へprivateなJSONとしてatomic保存されます。

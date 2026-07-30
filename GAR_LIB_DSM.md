# gar_lib 依存関係 DSM (Design Structure Matrix)

`tools/gen_gar_lib_dsm.py` により import 文の静的解析から自動生成。 再生成: `.venv/bin/python3 tools/gen_gar_lib_dsm.py`

読み方: **行 (consumer)** が **列 (provider)** を import している数。 空欄 = 依存なし。対角線 (同一package内) は集計から除外。

## package粒度 DSM

| consumer \\ provider | access | artifacts | build | commands | core | environments | gar_lib(top-level) | recovery | scripts.gar(entrypoint) | simulation | target | tests | vscode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **access** | 9 |  |  |  | 6 |  |  |  |  |  |  |  |  |
| **artifacts** | 1 | 2 |  |  | 6 |  |  |  |  |  |  |  |  |
| **build** |  | 4 | 6 |  | 18 |  |  |  |  |  | 5 |  |  |
| **commands** | 2 |  |  | 5 | 38 | 3 | 2 | 2 |  | 1 | 3 |  | 13 |
| **core** |  |  |  |  | 5 |  |  |  |  |  |  |  |  |
| **environments** |  |  |  |  | 5 | 31 |  |  |  |  |  |  |  |
| **gar_lib(top-level)** |  | 2 | 7 | 8 | 3 |  | 1 | 3 |  | 5 | 1 |  |  |
| **recovery** |  |  |  |  | 2 |  |  |  |  |  |  |  |  |
| **scripts.gar(entrypoint)** |  |  |  |  |  |  | 1 |  |  |  |  |  |  |
| **simulation** | 23 | 4 |  |  | 20 |  |  |  |  | 45 | 1 |  | 1 |
| **target** | 6 | 6 |  |  | 15 |  |  |  |  |  | 9 |  |  |
| **tests** | 17 | 3 | 6 | 19 | 53 | 13 | 9 | 2 |  | 31 | 10 |  |  |
| **vscode** |  |  |  |  | 3 |  |  |  |  |  |  |  |  |

file粒度 (99x99) の完全なmatrixは `GAR_LIB_DSM_file_level.csv` を参照 (Excel/sheetsで開くと見やすい)。

## 公開メンバの参照状況サマリ

- 対象module数: 99
- 公開メンバ(top-level関数/class/UPPER定数)総数: 366
- 他moduleから一度も参照されていないメンバ: 166  (詳細は `GAR_LIB_PUBLIC_API_USAGE.md` の「外部未参照」表)

詳細な「メンバ単位でどこから参照されているか」は `GAR_LIB_PUBLIC_API_USAGE.md` を参照。


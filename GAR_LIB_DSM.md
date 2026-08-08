# gar_lib 依存関係 DSM (Design Structure Matrix)

`tools/gen_gar_lib_dsm.py` により import 文の静的解析から自動生成。 再生成: `.venv/bin/python3 tools/gen_gar_lib_dsm.py`

読み方: **行 (consumer)** が **列 (provider)** を import している数。 空欄 = 依存なし。対角線 (同一package内) は集計から除外。

## package粒度 DSM

| consumer \\ provider | access | artifacts | build | commands | core | environments | gar_lib(top-level) | scripts.gar(entrypoint) | simulation | target | tests | vscode |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **access** | 9 |  |  |  | 6 |  |  |  |  |  |  |  |
| **artifacts** | 1 | 2 |  |  | 6 |  |  |  |  |  |  |  |
| **build** |  | 3 | 4 |  | 15 |  |  |  |  |  |  |  |
| **commands** | 2 |  |  | 52 | 49 | 3 | 2 |  | 5 | 5 |  | 39 |
| **core** |  |  |  |  | 12 |  |  |  |  |  |  |  |
| **environments** |  |  |  |  | 6 | 57 |  |  |  |  |  | 1 |
| **gar_lib(top-level)** |  | 2 | 7 | 9 | 5 |  | 1 |  | 9 | 1 |  |  |
| **scripts.gar(entrypoint)** |  |  |  |  |  |  | 1 |  |  |  |  |  |
| **simulation** | 17 | 6 |  |  | 21 |  |  |  | 57 | 2 |  | 1 |
| **target** | 6 | 5 |  |  | 11 | 2 |  |  |  | 8 |  |  |
| **tests** | 15 | 6 | 7 | 39 | 74 | 18 | 15 |  | 39 | 11 |  | 1 |
| **vscode** |  |  |  |  | 3 |  |  |  |  |  |  |  |

file粒度 (115x115) の完全なmatrixは `GAR_LIB_DSM_file_level.csv` を参照 (Excel/sheetsで開くと見やすい)。

## file配置距離

各Pythonファイルをtreeのleaf、import元→import先の一意な組を1 edgeとして、最短pathに含まれるtree edge数を測定。平均だけでなく外れ値も確認できるようp95と最大値を併記する。

- 一意なfile依存edge数: 270
- 平均path長: 3.489
- import binding数による加重平均path長: 3.545
- p95 / 最大path長: 5 / 6

## 公開メンバの参照状況サマリ

- 対象module数: 115
- 公開メンバ(top-level関数/class/UPPER定数)総数: 428
- 他moduleから一度も参照されていないメンバ: 170  (詳細は `GAR_LIB_PUBLIC_API_USAGE.md` の「外部未参照」表)

詳細な「メンバ単位でどこから参照されているか」は `GAR_LIB_PUBLIC_API_USAGE.md` を参照。


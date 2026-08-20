# コマンドリファレンス

`gar` コマンド一覧。WSL の venv 上で実行する（`make start` で有効化）。
設計背景は [02_ARCHITECTURE.md](02_ARCHITECTURE.md)、シミュレーション詳細は
[06_SIMULATION.md](06_SIMULATION.md) を参照。

---

## 0. 初期セットアップ

| コマンド | 内容 |
|---|---|
| `make init` | `.venv` 作成・`gar` symlink・VSCode extension install |
| `make start` | venv + bash completion を有効化したサブシェルを開く |
| `make check` | Ruff、unittest、shell構文、VS Code拡張のNode testをまとめて確認 |
| `gar setup` | target選択・gar-tools確認/取得・workspace/environment/接続設定・依存確認。`ssh_remote`ではruntime host入力必須。local product workspaceは複数登録可能 |
| `gar setup --no-install` | 不足依存をインストールせず、導入案内を表示 |
| `gar setup --ec2-host HOST` | simulation runtime用SSH host aliasを保存。`ssh_remote`選択時は設定必須 |
| `gar setup --esp32-port PORT` | ESP32 esptool用serial portを保存 |
| `gar hw init` | 現在のProduct directoryに、Product所有の空のhardware CSV schemaを生成 |
| `gar hw init --dir DIR [--force]` | 出力先を明示し、必要なら既存CSVを上書き（`--target`は互換用でschemaには影響しない） |
| `gar hw validate [--workspace NAME] [--requirements PATH] [--capabilities PATH] [--binding PATH] [--json]` | Product requirements、Target capabilities、Bindingを実機接続前に静的検証 |
| `make port-forward EC2=HOST` | 明示したEC2 SSH hostへのHardware Panel port forwardを開始 |
| `make port-forward-stop EC2=HOST` | 明示したEC2 SSH hostのport forwardを停止 |
| `make port-forward-status EC2=HOST` | 明示したEC2 SSH hostのport forward状態を確認 |

### Workspace ごとの設定

`GaplessAgentRuntime/.gar/config.json` は `workspaces` 配列を正本とします。
target、environment、EC2 接続先は各 workspace 要素に保存され、別アプリの設定と混ざりません。

```json
{
  "workspaces": [
    {
      "id": "ws_42f8c1",
      "name": "Local/Product",
      "connection": {
        "type": "local",
        "path": "/path/to/Product"
      },
      "branch": "main",
      "selected_environments": {
        "codespace": "local",
        "simulator": "ssh_remote",
        "target": "uuu"
      },
      "selected_target": "frdm-imx91s",
      "target": {
        "serial": "/dev/ttyCH343USB0"
      },
      "ec2": {
        "host": "my-sim-host",
        "identity_file": "~/.ssh/my-sim-host.pem"
      }
    }
  ]
}
```

`gar setup` の simulator 一覧では `local_docker` を新規選択しません。Docker 用の
image・device・mount 設定は、既存または明示的な build/UT workspace と互換性を保つため、
target 定義 (`gar-tools/targets/<id>/target.json` の `simulation.docker`) に残しています。
標準の Linux device simulation は `ssh_remote` を使用します。

Docker backendを明示した既存workspaceでは、workspaceの `docker` 設定で target 定義を
上書きできます。すべて省略可能です。

```json
      "docker": {
        "container": "gar-sim",
        "image": "gar-linux-device:latest",
        "bridge_port": 18080
      }
```

target 側の宣言は次の形です。`buildContext` があれば、container を新規作成する
前に `gar sim host start` が `docker build` を実行します。変更がなければ Docker
の build cache が使われます。

```json
  "simulation": {
    "docker": {
      "image": "gar-linux-device:latest",
      "buildContext": "targets/linux-device",
      "publishedBridgePort": 8080,
      "containerBridgePort": 8080,
      "publishedHost": "127.0.0.1",
      "init": ["/sbin/init"],
      "privileged": true,
      "hostCgroups": true,
      "environment": ["GAR_BRIDGE_HOST=0.0.0.0"],
      "tmpfs": ["/run", "/run/lock"],
      "mounts": ["/sys/kernel/config:/sys/kernel/config"],
      "devices": ["/dev/fuse", "/dev/cuse"]
    }
  }
```

`publishedBridgePort`はhost側、`containerBridgePort`はcontainer内でbridgeがlistenする
portです。workspaceの`docker.bridge_port`はhost側だけを上書きします。既存の
`bridgePort`は両方へ同じ値を設定する互換形式として読み込まれます。
`publishedHost`はDockerがhost側で公開するIPアドレスで、既定値は`127.0.0.1`です。
bridge自体は通常loopbackだけでlistenし、Docker targetだけが`environment`で
`GAR_BRIDGE_HOST=0.0.0.0`を明示します。`GAR_BRIDGE_PORT`は
`containerBridgePort`から自動設定されるため、target定義への重複記載は不要です。

container は host kernel を共有するため、GPIO(`gpio-sim`) には Linux 5.17 以降の
host kernel が必要です。`gar sim gpio check --json` で確認できます。

`gar sim app build` / `gar sim runtime build` は、選択された simulator に応じて
product build hook に次の環境変数を渡します。artifact を動かす simulation host
のアーキテクチャに合わせるためです。

| simulator | `GAR_SIM_ARCH` | `CC` |
|---|---|---|
| `local_docker`（明示／既存workspace） | このマシンのアーキテクチャ（`docker.arch` で上書き） | `gcc` |
| `ssh_remote` | `aarch64`（`ec2.arch` で上書き） | `aarch64-linux-gnu-gcc` |

`GAR_SIM_ENVIRONMENT` には simulator の ID そのものが入ります。target build
（`gar target build`）にはこれらの変数は渡りません。

`id` は GAR が自動生成する内部用の不変 ID で、ユーザーが入力する必要はありません。`name` は自動生成された workspace名で、既定値は `Local/<product-branch>`、
`Codespaces/<product-branch>`、`Network/<product-branch>` です。`main` branch の場合は
workspace directory 名を使います。setup の修正画面で変更できます。`gar setup` の
一覧に表示され、`--workspace NAME` で指定する識別子でもあります。connection は
`local`、`codespaces`、`network` のいずれかです。複数 workspace がある場合、product
workspace 内で `gar` を実行するとその path の設定が選ばれます。GAR root から Wokwi build を実行する場合は、
`gar sim app build --workspace NAME` を指定してください。登録が1件だけなら指定は不要です。
workspace選択は各commandの呼び出しcontextで解決され、setupで選んだworkspaceを
process内のglobal状態として後続commandへ持ち越しません。

### Hardware contract (`gar hw validate`)

`hardware/requirements.json`はProductが必要とするdevice/driver、電圧、SPI速度・mode、video FPSを、
`gar-tools/targets/<target>/hardware/capabilities.json`はBoard resourceとarchitecture/ABI/toolchain、
init system、privilege modelを宣言します。`hardware/bindings/<target>.json`だけが論理要件をGPIO line、
物理pin、SPI bus/CS、pinmuxへ割り当てます。既定pathはworkspaceの`selected_target`から解決されます。

`hardware/*.csv`もProduct所有のruntime入力です。GARはworkspaceの`hardware/`（またはworkspace設定の
`hardware.path`）から読み、simulation runtimeへ渡します。Target Pack内のCSVへfallbackしないため、
別Productの部品・配線が暗黙に混入することはありません。

`gar hw validate --workspace NAME --json`はSSHや実機への書込みを行わず、pin競合、bus/CS競合、
device/driver不足、電圧、SPI上限/mode、video FPS、Product/Target driftをstdoutの単一JSONで返します。
終了codeは適合時0、不適合または入力不正時1です。

`gar setup` の workspace 追加では接続種別を選びます。Codespaces は Codespace 名と
その中の path、network は IP address または SSH host と remote path を入力します。
Git remote と branch は接続先から自動検出し、検出できない場合だけ branch を確認します。

---

## 1. ビルド環境 管理

| コマンド | 内容 |
|---|---|
| `gar code boot [--workspace NAME]` | workspaceのdevelopment environmentがCodespacesならVMを起動。localなら状態を案内 |
| `gar code start [--workspace NAME]` | workspace設定からCodespaceとremote pathを解決し、sshfsマウント・terminal profileを追加 |
| `gar code stop [--workspace NAME]` | 保存済み接続状態を使ってマウント解除・profile削除 |
| `gar code shutdown [--workspace NAME]` | workspaceに対応するCodespace VMを停止 |
| `gar code status [--workspace NAME]` | Codespace VM / 接続状態を確認 |

各commandは`--workspace NAME`でproduct workspaceを選びます。Codespaces環境では
`--target NAME`（互換alias: `--codespace NAME`）で接続先を一時上書きできます。
`start`は`--remote-path`、`--mount-dir`、`--settings`、`--profile-name`、`--no-mount`、
`stop`は同種のlocal接続設定と`--shutdown`に対応します。

---

## 2. シミュレーション (`gar sim`)

物理ハードウェアエミュレータ（AWS EC2上の互換ランタイム、またはWokwiなどのローカル/クラウドエミュレータ）を用いた動作検証コマンドです。詳細は [06_SIMULATION.md](06_SIMULATION.md) を参照。

## System topology (`gar system`)

複数のproduct workspaceを一つの宣言として扱う場合は、schema v1 JSONを使います。
`gar system {build,deploy,start,status,diag,test} --file PATH [--json]` の既定file名は
`gar-system.json`です。`--json`は成功・失敗ともstdoutに単一JSONだけを出力します。

```json
{
  "schema_version": 1,
  "name": "GarStream",
  "nodes": [
    {"id": "tx", "workspace": "Local/GarStreamTx", "app": "gar-stream-tx", "role": "source", "environment": "sim", "runtime_env": {"PEER_IP": {"node_private_ip": "rx"}}},
    {"id": "rx", "workspace": "Local/GarStreamRx", "app": "gar-stream-rx", "role": "receiver", "environment": "sim", "runtime_env": {}}
  ],
  "links": [{"id": "media", "from": "tx", "to": "rx", "protocol": "rtp/udp", "port": 5600}],
  "order": ["tx", "rx"]
}
```

`order`は全nodeを一度ずつ含めます。nodeの`runtime_env`は安全な大文字環境変数名をキーにし、
`{"literal": scalar}`、`{"node_private_ip": "node-id"}`、
`{"link_port": "link-id"}`のいずれかを値にします。IPはbuild artifactに埋め込まず、deploy/start時に
runtimeへ注入します。simはapp→runtimeをbuildし、runtime→appをdeployしてport forwardなしでstartします。
targetは専用のruntime env fileを配置してから既存target lifecycleを通じてbuild/deploy/start/status/diagします。
`gar system test --scenario PATH [--bridge NODE=http://host:port]... --json` は全nodeの診断、health、
最新artifactのbuild ID/checksumに続けてproduct-owned Golden scenarioを実行します。`--bridge`はmachine-localな
origin overrideであり、scenario fileにURLやIPを保存しません。未指定のsim Bridge URLはworkspaceの
`docker.bridge_port`から導出します。

scenario schema v1は`schema_version`、`name`、`steps`、任意の`cleanup`だけを持ちます。stepは
`type`だけをdiscriminatorにして、`command`（Bridgeの`rotate`/`press`または
`via: "runtime"`の`start`/`stop`）、`observe`、`assert`、`wait`（`milliseconds`）を表します。
`observe`はnodeのappから`GET /api/metrics/{application}`を解決します。`assert`はliteralの`value`、
または先行observeを参照する`value_metric`（相互排他）を比較でき、任意の`timeout_ms`/`interval_ms`で
bounded pollingできます。`cleanup`のcommandは本体の失敗後も必ず実行されます。
JSON出力にはmetrics、assertion、failure、cleanupを含みます。
各linkのJSONには、OS/infra adapterへ渡せるingress/egress `firewall` planと
`diagnostic_target`も含まれます。P1-2 coreはこのplanを生成し、host firewallを暗黙には変更しません。

### 2.1. `gar sim <subject> <action>` の3語構造

`gar sim`配下は「対象（subject）」「操作（action）」を分け、操作対象のレイヤーを明示します。
`gar target <action>`は実機ライフサイクル、`gar system <action>`は複数node、
`gar hw <action>`はHardware contractを扱います。`code`、`usb`、`terminal`も独立した
top-level groupです。

| subject | レイヤー | 操作対象 | 日常的な役割 |
|---|---|---|---|
| `gar sim host` | **ホスト** | EC2 / container などシミュレーションホストOS | シミュレーション用のVMやホストの起動・停止・接続状態の管理 |
| `gar sim runtime` | **ランタイム** | 仮想デバイス（I2C, SPI, GPIO）のスタブ | 仮想デバイスのエミュレータ（CUSEスタブやブリッジ等）のビルド・起動・ログ監視・個別デバッグ |
| `gar sim app` | **アプリ** | Product成果物 | 検証したいProductアプリケーションのビルドと環境への反映 |
| `gar sim gpio` | **仮想GPIO** | GPIO dummy runtime | GPIO dummy runtime の生成・配置・状態確認 |
| `gar sim io` | **仮想H/W操作** | Bridge control plane | button 押下・RFID タップなど virtual H/W への入力注入（AI / CI 向け） |
| `gar sim infra` | **インフラ** | AWS等インフラ設備 (Terraform) | テスト用インスタンス自体の作成・破棄（開発初期のみ実行） |

`gar target` はsubjectを持たず、`gar target build/deploy/fetch`の2語で実機向けartifactを扱います。

---

### 2.2. ユースケース別基本フロー

#### A. 初めてシミュレーション環境を構築するとき / 完全に初期化するとき
ホストVMを起動し、仮想デバイス環境（runtime）をビルドして起動するまでの手順です。

```bash
# 1. ホストVMの起動とSSH接続設定の更新
gar sim host start --pull

# 2. 仮想デバイスドライバ（スタブ）のビルド・デプロイ・起動
gar sim runtime build
gar sim runtime deploy
gar sim runtime start

# 3. アプリケーションのビルドとデプロイ
gar sim app build
gar sim app deploy

# 4. シミュレーション環境全体の正常性診断（JSON出力で確認）
gar sim runtime diag --json
```

#### B. アプリのコードを修正し、再テストするとき (日常開発)
仮想デバイス環境（runtime）は起動したまま、アプリケーションのみを再デプロイして検証します。

```bash
# アプリケーションをビルドしてホストへ再配置
gar sim app build
gar sim app deploy
```
> [!NOTE]
> アプリケーションは `gar sim runtime start` の時点では自動起動しません。シミュレーションホストにログイン、またはテスト用プロセス起動コマンド等を通じて手動で起動します。

#### C. シミュレーションを終了するとき
リソースを無駄にしないよう、仮想環境とホストVMを停止します。

```bash
# 1. 仮想デバイス環境の停止
gar sim runtime stop

# 2. ホストVMの停止
gar sim host stop
```

---

### 2.3. コマンド一覧

#### ホスト管理 (`gar sim host`)
| コマンド | 内容 |
|---|---|
| `gar sim host start [--pull] [--no-update-ssh]` | シミュレーションホストを起動し、SSH接続設定を更新（`--pull` はworkspaceの `ec2.repo_dir` / `docker.repo_dir` で `git pull`） |
| `gar sim host stop` | シミュレーションホストを停止（インスタンスは削除されず、課金が抑えられます） |
| `gar sim host status [--json]` | ホストの実状態を表示。Dockerではinspectしたimage/portと現在specの一致も報告 |
| `gar sim host <start/stop/status> --workspace NAME` | 指定workspaceのsimulator選択に応じ、DockerまたはEC2 host設定を使う |

#### 仮想デバイス環境管理 (`gar sim runtime`)
| コマンド | 内容 |
|---|---|
| `gar sim runtime build` | runtime artifactが必要なenvironmentで`product-sim-env-build.sh`を実行。Wokwi/MuJoCoなど不要なenvironmentでは何も作らない |
| `gar sim runtime build --workspace NAME` | 複数登録したworkspaceのうち、登録名でruntime build対象を指定 |
| `gar sim runtime deploy` | ビルドしたスタブや接続用Webブリッジをホストへ転送・配置 |
| `gar sim runtime deploy --workspace NAME` | 指定 workspace の `deploy.sim_env` artifact bundle を転送・配置 |
| `gar sim runtime start [--no-port-forward]` | 選択したruntimeを起動。remote runtimeではterminal profileとHardware Panel用port forwardも構成 |
| `gar sim runtime stop [--keep-port-forward]` | 選択したruntimeを停止し、既定ではremote runtimeのport forwardも停止 |
| `gar sim runtime status` | runtimeとport forwardの状態を表示 |
| `gar sim runtime diag [--json]` | プロセス、仮想デバイス、APIの動作状況をまとめて診断（AIエージェントの診断時は `--json` 推奨） |
| `gar sim runtime log` | 仮想環境の主要ログ（ブリッジやドライバ等）を表示 |

`runtime start` は `--settings PATH` と `--profile-name NAME` で起動設定を上書きできます。

#### 仮想GPIO管理 (`gar sim gpio`)
| コマンド | 内容 |
|---|---|
| `gar sim gpio <plan/install/start/stop/status/check>` | GPIO dummy runtime の個別設定・デバッグ管理（`check` は kernel 側の前提条件確認、`plan`/`status`/`check` は `--json` 対応） |

#### 仮想H/W操作 (`gar sim io`)
| コマンド | 内容 |
|---|---|
| `gar sim io state [--json]` | virtual H/W の現在値を取得 |
| `gar sim io press --device button --line 17 [--duration-ms 150]` | button を押下 |
| `gar sim io set --device rfid --uid <UID>` | device の値を設定（RFID タップの注入など） |
| `gar sim io clear --device rfid` | device の値を解除 |

#### アプリケーション配置 (`gar sim app`)
| コマンド | 内容 |
|---|---|
| `gar sim app build` | 選択したBuildEnvironmentで`product-sim-build.sh`を実行し、simulation application artifactを作成 |
| `gar sim app build --workspace NAME` | `gar setup` 一覧の workspace名でビルド対象を指定 |
| `gar sim app clean [--workspace NAME]` | 選択した product workspace の simulation build artifact を削除 |
| `gar sim app deploy` | 最新のアプリケーション成果物をシミュレーションホストの実行可能パスへ反映 |
| `gar sim app deploy --workspace NAME` | 指定workspaceの`deploy.app` artifact bundleを反映。MuJoCoは`.gar/mujoco/`へ安全にmaterialize |

#### インフラ管理 (`gar sim infra`)
| コマンド | 内容 |
|---|---|
| `gar sim infra setup` | 現在のシミュレーションホスト設定値を表示し、Terraform による作成計画を確認 |
| `gar sim infra apply` | インフラを実際に適用してインスタンスを作成し、`.gar/config.json` と SSH config を更新 |
| `gar sim infra destroy` | インスタンスを完全に破棄 |

各infra actionは`--key-name`、`--region`、`--auto-approve`をTerraformへ渡せます。

---

## 3. 実機 build / deploy (`gar target`)

| コマンド | 内容 |
|---|---|
| `gar target prepare [--workspace NAME]` | 選択Targetが持つOS別recipeを初回適用。接続方法と権限取得方法はTarget Packが定義し、必要なservice account、限定installer、boot serviceなどを導入 |
| `gar target configure --workspace NAME --app NAME --file PATH [--json]` | recipe-backed SSH Targetへ明示指定した既存の通常ファイルを`/etc/gar/<app>.env`として原子的に配置。artifactは不要 |
| `gar target build [--workspace NAME]` | workspaceのlocal/Codespaces build environmentで`scripts/product-target-build.sh`を実行し、実機用artifact snapshotを最新化。hookには選択Target IDを`GAR_TARGET`で渡す |
| `gar target preflight [--workspace NAME] [--app NAME] [--json]` | 最新TARGET_APPのchecksum/provenanceと、接続Targetのarch/ABI/libc/kernel・導入済みrecipe/tools identityを読み取り専用probeで検証。配置・設定・lifecycle操作は行わない |
| `gar target deploy [--workspace NAME] [--json]` | workspaceに設定したADB・serial（esptool flash）・SSH/scp環境へ最新artifactを配置。lifecycle対応Targetではreload、health、稼働build ID一致まで確認 |
| `gar target status [--workspace NAME] [--app NAME] [--json]` | Target recipeのlifecycle capability経由でapplicationの稼働状態を取得 |
| `gar target log [--workspace NAME] [--app NAME] [--lines N] [--json]` | Target recipe経由で末尾logを取得（既定200行） |
| `gar target diag [--workspace NAME] [--app NAME] [--json]` | status、health、期待/稼働build IDをまとめて診断 |

低レベルコマンド:

| コマンド | 内容 |
|---|---|
| `gar target fetch [--workspace NAME]` | workspace の build environment から artifact bundle を WSL hub へ取得（Codespaces は gh cp、local は取得不要）。artifact node の内部処理 |

ADB接続に失敗した場合は、Terminal Bridgeを通じて`gar usb list` / `gar usb attach`による復旧手順を案内する。

日常操作:

```bash
gar target preflight --workspace Local/Product --app my-app --json
gar target deploy
```

実機への配置前には`preflight`を独立して実行できます。成功JSONはworkspace、target ID、app、build ID、
互換性report、`compatible: true`、`ok: true`、`exit_code: 0`を返します。失敗もstdoutの単一JSONで
`compatible: false`とerrorを返し、非0終了します。対応範囲はLinux file-transfer Targetです。
`preflight`は互換性probe以外のSSH command、file push、configure、reload、diagを呼び出しません。

systemd型Targetの標準contractでは、product artifactは
`/opt/gar/apps/<app>/run`をentry pointとして提供します。root管理のunitはproductが
配布せずTarget recipeの`gar-app@.service`を共有し、永続設定は
`/etc/gar/<app>.env`へ分離します。env fileは任意で、存在するときだけ読み込みます。
設定の書込みは`gar target configure --workspace NAME --app NAME --file PATH`だけが行い、通常のdeployは
このファイルを削除・上書きしません。`configure --json`はworkspace、target、app、source、destination、
SHA-256 hash、configured、okを単一のstdout JSONで返します。
deploy後はserviceをenableしてrestartし、PnPやdefault設定で動くproductは初回deployから
そのままboot運用へ移れます。

`gar-app-lifecycle-v1`を宣言するTargetでは、GARはTarget所有helperの共通actionだけを
呼び出します。systemd / BusyBox initの差はrecipe側に閉じ込められ、GAR自身はproductの
process managerになりません。`deploy --json`は起動またはhealth収束に失敗した場合、
`placed: true`、`running: false`、rollbackが利用不可であることをJSONで返して非0終了します。
`status` / `log` / `diag`は`--app`を指定すればローカルartifactなしでも観測できます。

Raspberry Pi OS recipeはreal device用のreference runtime packageと`gar`accountを
準備しますが、gpio-sim/CUSE/Web Panelは導入しません。また旧GAR試作版が作った
`/etc/sudoers.d/90-gar-deploy`（`NOPASSWD: ALL`）だけを削除し、限定installer用ruleへ
移行します。

ESP32 / USB serial の低レベル確認やトラブルシュートは
[03_DEVELOPMENT_ENVIRONMENT.md](03_DEVELOPMENT_ENVIRONMENT.md) を参照。

---

## 4. USB 接続（WSL2 usbipd-win passthrough）

WSL2 から Windows 側の `usbipd-win` を呼び、USB serial / adb デバイスを
`/dev/ttyACM*` や `/dev/ttyUSB*` として WSL2 に接続するための補助コマンド。
Windows 側に `usbipd-win` が必要。

初回 bind は Host OS 側の管理者権限が必要になることがある。その場合は
Windows 管理者 PowerShell で一度だけ実行する。

```powershell
usbipd bind --busid <busid>
```

| コマンド | 内容 |
|---|---|
| `gar usb bind --match CH9102` | USB デバイスを usbipd-win に share 登録 |
| `gar usb attach` | USB-C デバイスを usbipd-win 経由で WSL2 に attach |
| `gar usb detach` | detach |
| `gar usb status` | 接続状態確認 |
| `gar usb list [--json]` | 接続可能デバイス一覧 |

`attach` / `bind`は`--busid`、`--match`、`--no-remember`、`detach`は`--busid` / `--match`、
`status`は`--busid` / `--match` / `--json`に対応します。

adb 実機は Windows 側 `adb.exe` を直接使う environment もあり、その場合は `usbipd-win`
不要。USB serial flash など WSL2 の device node が必要な経路では `gar usb` を使う。

---

## 補助

| コマンド | 内容 |
|---|---|
| `gar terminal run -- <cmd>` | VSCode integrated terminal でコマンドを実行（sudo 等の人間入力が必要な場合） |
| `gar terminal gc [--keep-days N] [--dry-run]` | terminal request/statusの古いエントリを削除 |
| `gar completion bash` | bash completion script を出力 |

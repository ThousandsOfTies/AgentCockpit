# コマンドリファレンス

`gar` コマンド一覧。**現行実装はWSLのvenv上で実行する**（`make start`で有効化）。
Windowsをentrypointにする運用の経緯と人間作業は
[0から実機まで](00_ZERO_TO_TARGET_TUTORIAL.md)、既存設計は
[02_ARCHITECTURE.md](02_ARCHITECTURE.md)、シミュレーション詳細は
[06_SIMULATION.md](06_SIMULATION.md)を参照する。

## 実行場所と実装状態

Windows host用の同名`gar` launcherは移行目標であり、まだこのrepositoryには存在しない。
macOS用entrypoint／host adapterも未実装・未検証である。
次の表は、現行commandの実体と、command名を変えずに到達する移行先を区別する。

| capability／command | 現行実装 | Windows host移行後 | 状態 |
|---|---|---|---|
| `gar setup`、`gar sim ... build`、`gar target build`、`gar system ...` | WSL上のPython GAR | Windows launcherからWSL backendへ固定routing | launcher未実装 |
| `gar target deploy`（UUU） | WSL上でmanifestのLinux版`uuu`を直接起動 | Windows native `uuu.exe`を起動 | Windows UUU adapter未実装 |
| UUU後の`serialVerify` | POSIX `/dev/tty*`を`termios`で監視 | Windows COM adapterで監視 | Windows COM adapter未実装 |
| `adb_win` Target | WSLからWindows `adb.exe`を起動 | Windows hostからnative `adb.exe`を起動可能にする | 現行のWSL interop経路は実装済み |
| `gar usb` | WSLから`usbipd.exe`を操作 | Linux専用USB toolだけが使う例外経路 | 現行実装済み |
| Local Docker simulation | WSLからDockerを操作する既存workspace | Docker Desktop WSL2 backendをWSLから操作 | 現行setupでは新規選択せず、Desktop上の同等性も未検証 |
| Git、test、project全体の検索 | WSL shellで各command／`rg`を直接実行 | Windows launcherからWSLへ固定routing可能 | 対応するGAR top-level commandは未実装 |

移行では「Windowsで失敗したらWSL」というfallbackを標準にしない。build／source操作はWSL、
UUU／COMはWindows、Linux専用USBだけはWSL + usbipd、というcapability単位の固定routingにする。
Docker Desktopを導入しただけではProduct buildが自動的にcontainer化されない。Product build hook
またはSimulationEnvironmentがDockerを選択した場合だけ利用する。

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
`code boot`／`shutdown`はcloud VMの起動／停止と課金状態を変える。初回認証、organization policy、
課金可否は人間が確認し、不要になったVMは明示的に停止する。

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

remote `host start`はcloud computeと課金状態を変え得る。人間または明示的に権限を与えられたCIが
provider、workspace、課金可否を確認し、不要になったhostは`stop`する。

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
`apply`／`destroy`は外部resourceを変更する。`--auto-approve`はTerraformの入力を省略するだけであり、
人間または明示的に権限を与えられたCIによる実行承認を省略する意味ではない。

---

## 3. 実機 build / deploy (`gar target`)

| コマンド | 内容 |
|---|---|
| `gar target prepare [--workspace NAME]` | recipe-backed SSH TargetだけがOS別recipeを初回適用。ADB、esptool、UUUでは不要でありerrorになる |
| `gar target configure --workspace NAME --app NAME --file PATH [--json]` | recipe-backed SSH Targetへ明示指定した既存の通常ファイルを`/etc/gar/<app>.env`として原子的に配置。artifactは不要 |
| `gar target build [--workspace NAME]` | workspaceのlocal/Codespaces build environmentで`scripts/product-target-build.sh`を実行し、実機用artifact snapshotを最新化。hookには選択Target IDを`GAR_TARGET`で渡す |
| `gar target preflight [--workspace NAME] [--app NAME] [--json]` | Linux file-transfer Targetのchecksum/provenanceと、arch/ABI/libc/kernel・recipe/tools identityをread-only probeで検証。UUUは非対応 |
| `gar target deploy [--workspace NAME] [--json]` | ADB・serial（esptool）・SSH/scp・UUU環境へ最新artifactを配置またはflash。lifecycle対応Targetだけreload、health、稼働build ID一致まで確認 |
| `gar target status [--workspace NAME] [--app NAME] [--json]` | lifecycle capabilityを持つTargetのapplication稼働状態を取得。UUUは非対応 |
| `gar target log [--workspace NAME] [--app NAME] [--lines N] [--json]` | lifecycle capabilityを持つTargetの末尾logを取得（既定200行）。UUUは非対応 |
| `gar target diag [--workspace NAME] [--app NAME] [--json]` | lifecycle capabilityを持つTargetのstatus、health、期待/稼働build IDを診断。UUUは非対応 |

UUU Targetが利用する標準経路は`target build` → 人間によるboot／USB確認 → `target deploy`だけである。
`serialVerify`がTarget Packにあればdeploy内で実行するが、application lifecycleのhealth／build ID
収束とは別の確認である。

### 人間確認と副作用

次は運用上の確認境界である。現行CLIがすべての確認promptを強制するとは限らないため、AIは
commandが実行可能であることを、人間の承認済みであることと同一視しない。

| 操作 | 主な副作用 | 人間の関与 |
|---|---|---|
| `target build` | local／cloudのCPU、disk、artifact snapshotを更新 | 通常不要。cloud認証や課金判断が必要な場合だけ確認 |
| `target preflight` | Linux file-transfer Targetのread-only probe | 通常不要。対象Targetのidentityは人間が最初に確定する。UUUでは実行しない |
| `target prepare` | recipe-backed SSH TargetのOS、account、service、権限設定を変更 | 初回とrecipe更新時に対象と変更内容を承認。ADB、esptool、UUUでは実行しない |
| `target configure` | 永続的なruntime設定を変更 | 設定値、secretの扱い、対象appを確認 |
| `target deploy`（SSH／ADB） | applicationを置換し、serviceをrestartし得る | productionや稼働中Targetでは実行時点を承認 |
| `target deploy`（esptool／UUU） | firmware／full imageを書き換え、既存dataを失い得る | Board、port、storage、boot mode、imageを毎回確認して承認 |
| `target status`／`log`／`diag` | lifecycle Targetでは原則read-only | 通常不要。logにsecretが含まれ得る環境では共有範囲を確認。UUUでは実行しない |

低レベルコマンド:

| コマンド | 内容 |
|---|---|
| `gar target fetch [--workspace NAME]` | workspace の build environment から artifact bundle を WSL hub へ取得（Codespaces は gh cp、local は取得不要）。artifact node の内部処理 |

ADB接続に失敗した場合は、Terminal Bridgeを通じて`gar usb list` / `gar usb attach`による復旧手順を案内する。

Recipe-backed Linux Targetの日常操作:

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

## 4. USB 接続（WSL2 usbipd-win passthrough、例外経路）

WSL2 から Windows 側の `usbipd-win` を呼び、USB serial / adb デバイスを
`/dev/ttyACM*` や `/dev/ttyUSB*` として WSL2 に接続するための補助コマンド。
Windows 側に `usbipd-win` が必要。

これは現行UUU／POSIX serial backendとの互換経路である。Windows native UUU／COM adapterへ
移行したTargetでは使わず、Linux専用toolがUSB deviceを直接必要とする場合だけ明示的に使う。

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

WSLへattachしている間、そのUSB deviceはWindows native toolから利用できない。人間が対象を識別し、
device所有権をWSLへ移すことを承認してからattachする。FRDM-IMX91Sの現行UUU経路ではdownload USBと
debug UARTが別deviceであり、保存できるbus IDは一件だけである。両方を`gar usb list`で識別し、
各commandへ`--busid`を明示する。自動検出に頼らない。

現行UUU経路では、これに加えてWSLへLinux版UUU／libusbを導入し、debug UARTを開けるよう
udev ruleまたはgroup membershipを人間が設定する。Windows native UUU／COMへ移行した後は不要になる。

adb 実機は Windows 側 `adb.exe` を直接使う environment もあり、その場合は `usbipd-win`
不要。USB serial flash など WSL2 の device node が必要な経路では `gar usb` を使う。

---

## 5. Windows hostの初回準備（GAR外のcommand）

この節は`gar` commandではない。Windowsをentrypointにするため、人間がmachineごとに一度だけ
実行または確認するOS操作である。UAC、driver導入、physical Target選択をAIが無断で完了扱いにしない。
判断理由と安全な実行順の正本は[0から実機まで](00_ZERO_TO_TARGET_TUTORIAL.md)とし、この節は
copy可能なhost commandの索引だけを提供する。

### WSLとDockerの確認

```powershell
wsl.exe --list --verbose
docker version
wsl.exe --distribution Ubuntu-26.04 -- docker version
```

Dockerを使う場合は、人間がDocker DesktopのWSL2 backendと対象distributionのWSL integrationを
有効にする。最後のcommandは現在のPCのdistribution名を使った例であり、別machineでは
`Ubuntu-26.04`を`wsl.exe --list --verbose`で確認した名前へ置き換える。Windows側だけでなく、
対象WSL distribution内からDocker daemonへ到達できることと、Product workspaceがWSL filesystem上に
あることを確認する。

### Yurufuwa作業領域rootのWindows link

artifact単位や個別Projectのlinkを切替のたびに張り替えない。複数Projectを含むYurufuwa作業領域rootへ
directory symbolic linkを一本だけ作成する。junction（`/J`）ではなくsymbolic linkを使う。

次は現在のPCの値である。別machineでは、先に`wsl.exe --list --verbose`でdistribution名を、
WSL shellの`pwd`で作業領域rootを確認してから`-Target`を置き換える。

```powershell
New-Item -ItemType Directory -Force C:\GAR
New-Item -ItemType SymbolicLink `
  -Path C:\GAR\Yurufuwa `
  -Target '\\wsl.localhost\Ubuntu-26.04\home\user\Yurufuwa'

Test-Path C:\GAR\Yurufuwa\GAR\GaplessAgentRuntime
```

2026-08-28のこのmachineでの試験ではlink作成に管理者PowerShellが必要だった。Developer Modeを有効にする場合も、
有効化は人間が判断する。link作成後の通常参照には管理者権限を要求しない。

Windows pathはWindows native peripheral toolがartifactへ到達するためのaliasである。WSL commandは
引き続き`/home/user/Yurufuwa`を使い、Windows native Git／build／recursive searchをlink越しに
実行しない。配下Projectの切替に追加linkやlinkの張り替えは不要である。

### Windows native UUUとserialの確認

```powershell
Get-Command uuu.exe
uuu.exe -h
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name
```

これらはtoolとportの存在確認だけであり、flash commandではない。人間がdownload USB、debug UART、
boot mode、対象Board、書込みstorageを確認してから`gar target deploy`を承認する。Windows native
UUU／COM adapterが未実装の間は、Windows上で同名`gar`からdeployできるとはみなさない。

### 移行中の診断用WSL起動

Windows launcher実装前にPowerShellから現行GARを診断するときは、`wsl.exe`で明示的にWSL commandを
起動できる。ただし、これはdaily user interfaceではなく移行中の診断手段である。次は現在のPCの例で、
別machineではdistribution名と`--cd`のpathを置き換える。

```powershell
wsl.exe --distribution Ubuntu-26.04 `
  --cd /home/user/Yurufuwa/GAR/GaplessAgentRuntime `
  -- bash -lc 'source .venv/bin/activate && gar --help'
```

### Text検索command

| command | 用途 | Project全体での扱い |
|---|---|---|
| WSL版`rg` | source、設定、logの高速な再帰検索 | 標準。WSL filesystem内で実行する |
| Windows版`rg.exe` | NTFS上のWindows-local file検索 | WSL project linkの全走査には使わない |
| `Select-String` | PowerShell pipeline内の小規模なtext検索 | 補助用途 |
| `findstr` | 単純なliteral検索やcommand出力のfilter | `grep`互換interfaceとして使わない |

`gar grep`と`gar search`は現行commandではない。将来追加する場合は、Windows上でもWSL版`rg`へ
固定routingし、OSごとに異なるregex semanticsをuser／AIへ見せない。

---

## 6. 補助

| コマンド | 内容 |
|---|---|
| `gar terminal run -- <cmd>` | VSCode integrated terminal でコマンドを実行（sudo 等の人間入力が必要な場合） |
| `gar terminal gc [--keep-days N] [--dry-run]` | terminal request/statusの古いエントリを削除 |
| `gar completion bash` | bash completion script を出力 |

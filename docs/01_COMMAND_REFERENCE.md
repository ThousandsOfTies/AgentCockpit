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
| `gar setup` | target 選択・gar-tools 確認/取得・依存 target graph と接続設定の保存・依存コマンド確認・既定 host 保存。local product workspace は複数登録でき、対話画面で追加/削除します |
| `gar hw init` | `gar-tools` の target テンプレートから `hardware/` に CSV を生成 |

### Workspace ごとの設定

`GaplessAgentRuntime/.gar/config.json` は `workspaces` 配列を正本とします。
target、environment、EC2 接続先は各 workspace 要素に保存され、別アプリの設定と混ざりません。

```json
{
  "workspaces": [
    {
      "id": "ws_42f8c1",
      "name": "Local/GarStreamRx",
      "connection": {
        "type": "local",
        "path": "/home/user/Yurufuwa/GarStreamRx"
      },
      "branch": "main",
      "selected_environments": {"codespace": "local", "simulator": "ssh_remote"},
      "selected_target": "linux-device",
      "ec2": {
        "host": "vibecode-graviton",
        "identity_file": "~/.ssh/vibecode-graviton.pem"
      }
    }
  ]
}
```

`simulator` に `local_docker` を選んだ場合は `ec2` の代わりに `docker` を使います。
container の image・device・mount など「どんな container が必要か」は target 定義
(`gar-tools/targets/<id>/target.json` の `simulation.docker`) が持ちます。
workspace の `docker` はその上書きだけを担当し、すべて省略可能です。

```json
      "selected_environments": {"codespace": "local", "simulator": "local_docker"},
      "docker": {
        "container": "gar-sim",
        "image": "gar-linux-device:latest",
        "bridge_port": 8080
      }
```

target 側の宣言は次の形です。`buildContext` があれば、image がないときに
`gar sim host start` が `docker build` まで行います。

```json
  "simulation": {
    "docker": {
      "image": "gar-linux-device:latest",
      "buildContext": "targets/linux-device",
      "bridgePort": 8080,
      "init": ["/sbin/init"],
      "privileged": true,
      "hostCgroups": true,
      "tmpfs": ["/run", "/run/lock"],
      "mounts": ["/sys/kernel/config:/sys/kernel/config"],
      "devices": ["/dev/fuse", "/dev/cuse"]
    }
  }
```

container は host kernel を共有するため、GPIO(`gpio-sim`) には Linux 5.17 以降の
host kernel が必要です。`gar sim gpio check --json` で確認できます。

`gar sim app build` / `gar sim runtime build` は、選択された simulator に応じて
product build hook に次の環境変数を渡します。artifact を動かす simulation host
のアーキテクチャに合わせるためです。

| simulator | `GAR_SIM_ARCH` | `CC` |
|---|---|---|
| `local_docker` | このマシンのアーキテクチャ（`docker.arch` で上書き） | `gcc` |
| `ssh_remote` | `aarch64`（`ec2.arch` で上書き） | `aarch64-linux-gnu-gcc` |

`GAR_SIM_ENVIRONMENT` には simulator の ID そのものが入ります。target build
（`gar target app build`）にはこれらの変数は渡りません。

`id` は GAR が自動生成する内部用の不変 ID で、ユーザーが入力する必要はありません。`name` は自動生成された workspace名で、既定値は `Local/<product-branch>`、
`Codespaces/<product-branch>`、`Network/<product-branch>` です。`main` branch の場合は
workspace directory 名を使います。setup の修正画面で変更できます。`gar setup` の
一覧に表示され、`--workspace NAME` で指定する識別子でもあります。connection は
`local`、`codespaces`、`network` のいずれかです。複数 workspace がある場合、product
workspace 内で `gar` を実行するとその path の設定が選ばれます。GAR root から Wokwi build を実行する場合は、
`gar sim app build --workspace NAME` を指定してください。登録が1件だけなら指定は不要です。

`gar setup` の workspace 追加では接続種別を選びます。Codespaces は Codespace 名と
その中の path、network は IP address または SSH host と remote path を入力します。
Git remote と branch は接続先から自動検出し、検出できない場合だけ branch を確認します。

---

## 1. ビルド環境 管理

| コマンド | 内容 |
|---|---|
| `gar code boot` | Codespace VM を起動し、必要なら接続準備を行う |
| `gar code start` | Codespace を sshfs マウント・terminal profile を追加 |
| `gar code stop` | マウント解除・profile 削除 |
| `gar code shutdown` | Codespace VM を停止 |
| `gar code status` | Codespace VM / 接続状態を確認 |

---

## 2. シミュレーション (`gar sim`)

物理ハードウェアエミュレータ（AWS EC2上の互換ランタイム、またはWokwiなどのローカル/クラウドエミュレータ）を用いた動作検証コマンドです。詳細は [06_SIMULATION.md](06_SIMULATION.md) を参照。

### 2.1. `gar <group> <subject> <action>` の3語構造
すべてのコマンドは「グループ（`sim` / `target`）」「対象（subject）」「操作（action）」の3語で表します。
`gar sim` の subject は、操作対象となるレイヤーに対応します。

| subject | レイヤー | 操作対象 | 日常的な役割 |
|---|---|---|---|
| `gar sim host` | **ホスト** | EC2 / container などシミュレーションホストOS | シミュレーション用のVMやホストの起動・停止・接続状態の管理 |
| `gar sim runtime` | **ランタイム** | 仮想デバイス（I2C, SPI, GPIO）のスタブ | 仮想デバイスのエミュレータ（CUSEスタブやブリッジ等）のビルド・起動・ログ監視・個別デバッグ |
| `gar sim app` | **アプリ** | アプリケーション成果物 | 検証したいアプリケーション本体（`sensor_demo`など）のビルドと環境への反映 |
| `gar sim gpio` | **仮想GPIO** | GPIO dummy runtime | GPIO dummy runtime の生成・配置・状態確認 |
| `gar sim io` | **仮想H/W操作** | Bridge control plane | button 押下・RFID タップなど virtual H/W への入力注入（AI / CI 向け） |
| `gar sim infra` | **インフラ** | AWS等インフラ設備 (Terraform) | テスト用インスタンス自体の作成・破棄（開発初期のみ実行） |

`gar target` の subject は現在 `app` のみで、実機向けの build / deploy / fetch を担当します。

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
| `gar sim host start [--pull]` | シミュレーションホストを起動し、SSH接続設定を更新（`--pull` で最新の `gar-tools` 等を git pull） |
| `gar sim host stop` | シミュレーションホストを停止（インスタンスは削除されず、課金が抑えられます） |
| `gar sim host status` | ホストの現在の実行状態を表示 |
| `gar sim host <start/stop/status> --workspace NAME` | 指定 workspace に保存された EC2 設定を使う |

#### 仮想デバイス環境管理 (`gar sim runtime`)
| コマンド | 内容 |
|---|---|
| `gar sim runtime build` | 仮想デバイススタブ（CUSE I2C/SPI など）や Wokwi firmware をビルド |
| `gar sim runtime build --workspace NAME` | Wokwi など複数登録した workspace のうち、登録名でビルド対象を指定 |
| `gar sim runtime deploy` | ビルドしたスタブや接続用Webブリッジをホストへ転送・配置 |
| `gar sim runtime deploy --workspace NAME` | 指定 workspace の `deploy.sim_env` artifact bundle を転送・配置 |
| `gar sim runtime start` | 仮想環境（systemd サービス群）とポートフォワードを起動 |
| `gar sim runtime stop` | 仮想環境（systemd サービス群）を停止 |
| `gar sim runtime status [--json]` | 各サービスの状態やポートフォワードの接続状態を表示 |
| `gar sim runtime diag [--json]` | プロセス、仮想デバイス、APIの動作状況をまとめて診断（AIエージェントの診断時は `--json` 推奨） |
| `gar sim runtime log` | 仮想環境の主要ログ（ブリッジやドライバ等）を表示 |

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
| `gar sim app build` | シミュレーション用のアプリケーション成果物をビルド (※現在は移行中のため、一部ターゲットは Makefile を経由) |
| `gar sim app build --workspace NAME` | `gar setup` 一覧の workspace名でビルド対象を指定 |
| `gar sim app clean [--workspace NAME]` | 選択した product workspace の simulation build artifact を削除 |
| `gar sim app deploy` | 最新のアプリケーション成果物をシミュレーションホストの実行可能パスへ反映 |
| `gar sim app deploy --workspace NAME` | 指定 workspace の `deploy.app` artifact bundle を反映 |

#### インフラ管理 (`gar sim infra`)
| コマンド | 内容 |
|---|---|
| `gar sim infra setup` | 現在のシミュレーションホスト設定値を表示し、Terraform による作成計画を確認 |
| `gar sim infra apply` | インフラを実際に適用してインスタンスを作成し、`.gar/config.json` と SSH config を更新 |
| `gar sim infra destroy` | インスタンスを完全に破棄 |

---

## 3. 実機 build / deploy (`gar target app`)

| コマンド | 内容 |
|---|---|
| `gar target app build [--workspace NAME]` | workspaceのbuild environmentで実機用artifactを最新化。target定義から解決するため、Linux系は `scripts/product-target-build.sh`、ESP32/M5Stack（`esp32_esptool`）は PlatformIO ビルド＋artifact取得を自動で切り替える |
| `gar target app deploy [--workspace NAME]` | workspaceに設定したADB・serial（esptool flash）・SSH/scp環境へ最新artifactを配置 |

低レベルコマンド:

| コマンド | 内容 |
|---|---|
| `gar target app fetch [--workspace NAME]` | workspace の build environment から artifact bundle を WSL hub へ取得（Codespaces は gh cp、local は取得不要）。artifact node の内部処理 |

ADB接続に失敗した場合は、Terminal Bridgeを通じて`gar usb list` / `gar usb attach`による復旧手順を案内する。

日常操作:

```bash
gar target app deploy
```

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
| `gar usb list` | 接続可能デバイス一覧 |

adb 実機は Windows 側 `adb.exe` を直接使う environment もあり、その場合は `usbipd-win`
不要。USB serial flash など WSL2 の device node が必要な経路では `gar usb` を使う。

---

## 補助

| コマンド | 内容 |
|---|---|
| `gar terminal run -- <cmd>` | VSCode integrated terminal でコマンドを実行（sudo 等の人間入力が必要な場合） |
| `gar terminal gc` | terminal-requests の古いエントリを削除 |
| `gar completion bash` | bash completion script を出力 |

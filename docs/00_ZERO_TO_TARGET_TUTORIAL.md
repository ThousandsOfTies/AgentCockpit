# 0 から実機動作までのチュートリアル

このチュートリアルは、しばらく間が空いてもGapless Agent Runtimeを最初から
立ち上げ直し、simulationで予行してからRaspberry Pi 5 / Raspberry Pi OS実機へ
同じapplicationを配置するための一本道です。

操作は人間が行います。AI に頼むときは、各チェックポイントの出力を貼って「次は何をすればいい？」と聞けば続きから進められるようにします。

## ゴール

最終的に次の状態を作ります。

```text
WSL Hub (Gapless Agent Runtime)
  gar setup 済み
  Codespace build VM に接続済み
  EC2 simulation host を起動・deploy・diag 済み
  RasPi5 実機へ target deploy 済み

RasPi5
  /opt/gar/apps/<app>/run を gar service accountで実行
  real /dev/gpiochip* / /dev/i2c-* / /dev/spidev* / /dev/video* を利用
  gar-app@<app>.service でboot自動起動
```

## 前提

この手順は「完全に空の AWS アカウントや Raspberry Pi OS イメージを作る」手順ではありません。次のものは用意済み、または既存手順で用意されている前提です。

| 対象 | 前提 |
|---|---|
| Windows / WSL2 | WSL2 Ubuntu から `git`, `python3`, `make` が使える |
| GitHub | Codespaces を使える。`gh auth login` 済み、または途中でログインできる |
| EC2 simulation host | `gar sim host start` で起動できる EC2 設定がある |
| RasPi5 | Raspberry Pi OS が起動し、実 H/W 配線済み |
| 実機接続 | Raspberry Pi 5標準はpasswordless SSH接続と、sudo可能な通常user |
| ビルド成果物 | Codespace 側で artifact bundle を作れる target repo がある |

配線は [05_HARDWARE_WIRING.md](05_HARDWARE_WIRING.md) を参照します。コマンドの細かい意味は [01_COMMAND_REFERENCE.md](01_COMMAND_REFERENCE.md) が正本です。

## 1. WSL Hub を初期化する

Gapless Agent Runtime repo に移動します。

```bash
cd path/to/GaplessAgentRuntime
git pull
```

初回、または `.venv` を作り直したいとき:

```bash
make init
```

日常作業の開始:

```bash
make start
```

`make start` の後は、サブシェル内で `gar` と bash 補完が有効になります。抜けるときは `exit` です。

チェック:

```bash
gar ?
gar setup --no-install
```

`python3-venv` がないと言われた場合:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv
rm -rf .venv
make init
make start
```

## 2. target / environment / runtime host を設定する

まず `gar setup` を実行します。

```bash
gar setup
```

最初に target（何を動かしたいか）を選びます。target ごとの推奨 backend が表示され、その後に接続 environment を選びます。

基本の選択は次です。

| カテゴリ | 推奨 |
|---|---|
| Target | Raspberry Pi 5 / Raspberry Pi OS |
| 開発環境 | GitHub Codespaces |
| シミュレート環境 | EC2 runtime host へ接続するための SSH Remote |
| 実機環境 | SSH / scp |

ESP32 / M5Stack を扱う場合は Target で `ESP32 / M5Stack` を選びます。標準セットアップでは Wokwi を主な simulation backend として準備します。Espressif QEMU、Renode、fake-idf、probe 類は必要になった時だけ使う任意の target tool です。

Raspberry Pi 5では実機環境に`SSH / scp`を選び、SSH configのHost名を保存します。
`Linux device / RasPi-compatible`はsimulation runtime用の互換Targetであり、実機Piの
OS provisioningを行うTargetではありません。

ここでの `SSH Remote` は「シミュレータ種別」ではなく、EC2 simulation runtime host へ `ssh` / `scp` で入るための接続 environment です。`AWS SSM` は現状の runtime 操作では非推奨な environment です。

`SSH Remote`を選んだ場合はEC2のSSH host aliasを必ず設定します。個人環境名への
fallbackはありません。

```bash
gar setup --ec2-host my-sim-host
```

チェック:

```bash
gar sim host status
gar code ?
gar target ?
```

## 3. Codespace build VM に接続する

Codespace が 1 つだけなら名前指定なしで進めます。

```bash
gar code start
```

複数ある場合:

```bash
gh codespace list
gar code start --codespace <codespace-name>
```

これで WSL Hub から Codespace の workspace が見えるようになり、VS Code の terminal profile も作られます。

チェック:

```bash
cat ~/.config/codespace-dev/state.json
ls ~/codespace-dev 2>/dev/null || true
```

## 4. 選択したBuildEnvironmentで成果物をビルドする

`gar setup`で選択した開発環境が`github_codespaces`なら、GARがCodespace内のproduct hookを
実行し、成果物をWSL側artifact storeへ同期します。`local`ならworkspace内の同じhookを
ローカル実行します。EC2や実機ではビルドしません。

用途ごとの標準コマンド:

```bash
gar sim app build       # simulation application
gar sim runtime build   # Linux runtime artifact。不要なenvironmentではno-op
gar target build        # 実機用application / firmware
```

内部ではproduct workspaceの`product-sim-build.sh`、`product-sim-env-build.sh`、
`product-target-build.sh`をartifact種別に応じて呼び分けます。ESP32も例外ではなく、
product workspace側の`product-target-build.sh`がPlatformIO buildとartifact stagingを
担当します。GARのBuildEnvironmentは、実行場所に応じて
`LocalBuildEnvironment`または`CodespacesBuildEnvironment`を選びます。

Codespaces側の既存bundleだけを再取得する場合は`gar target fetch`を使います。
`deploy`はbuild/fetchを暗黙実行しないため、先にartifactを用意してください。

Codespaces側を手動診断する場合の既定bundle:

```bash
ls -la /workspaces/gar-build-env/artifacts/from-codespace
cat /workspaces/gar-build-env/artifacts/from-codespace/artifact.json
```

`artifact.json` には用途に応じて `deploy.app` / `deploy.sim_env` が必要です。
各sectionは`files`の一覧、またはproduct hookが生成した`artifact`を持てます。
取得後は`.gar/artifacts/<workspace-id>/<artifact-kind>/<build-id>/`へ種別ごとの
不変snapshotとして保存され、`latest.json`が最新buildを指します。

## 5. 先に simulation で予行する

実機へ行く前に、EC2 simulation host で同じ arm64 バイナリを動かします。

WSL Hub 側で:

```bash
gar sim host start
gar sim runtime build
gar sim runtime deploy
gar sim runtime start
gar sim app build
gar sim app deploy
gar sim runtime diag --json
```

`diag --json` の `"ok": true` が目安です。失敗したら次を確認します。

```bash
gar sim runtime diag --json
gar sim gpio status --json
gar sim runtime log
```

EC2 にログインしてアプリを起動します。

```bash
ssh my-sim-host
~/sensor_demo
```

仮想 H/W は backend の UI から操作します。
Linux / RasPi-compatible simulation では Web UI / Virtual Hardware Panel、
Wokwi simulation では VS Code Wokwi Simulator / Diagram UI を使います。
Wokwi の手動確認では `gar sim runtime diag --json` に表示される `project_dir` の
`diagram.json` を開き、
Editor ペイン左上の再生ボタンを押します。このとき `wokwi.toml` が参照する
`firmware.bin` / `firmware.elf` が Wokwi 側へ送信されます。

AI / CI から再現操作を行う場合は、単発のUI操作コマンドではなく
GAR共通のJSONシナリオとして定義します。Linux bridge向けの既存補助ランナーは
`scripts/run_scenario.py` です。

```bash
python scripts/run_scenario.py path/to/scenario.json
gar sim runtime diag --json
```

期待:

```text
`press` / `device: button` action で system_on 相当の状態が変わる
`set` / `device: rfid` action で UID が bridge state / OLED 表示へ反映される
sensor_demo が EC2 上で落ちない
```

simulation を止める場合:

```bash
gar sim runtime stop
gar sim host stop
```

## 6. RasPi5 実機を準備する

配線は [05_HARDWARE_WIRING.md](05_HARDWARE_WIRING.md) の通りにします。

RasPi5 側で I2C / SPI を有効化していない場合:

```bash
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo reboot
```

再起動後、RasPi5 側で確認します。

```bash
ls -l /dev/i2c-1 /dev/spidev0.0 /dev/gpiochip*
```

I2C デバイスを確認する場合:

```bash
sudo apt-get update
sudo apt-get install -y i2c-tools
i2cdetect -y 1
```

目安:

```text
SSD1306 OLED: 0x3c
VL53L0X:      0x29
```

RFID は配線と SPI 有効化が合っていれば、`sensor_demo` 実行時に UID 読み取りで確認します。

Raspberry Pi 5標準経路では、WSLからSSH configのHost名で接続できることを確認します。

```bash
ssh raspi5 'cat /proc/device-tree/model; . /etc/os-release; echo "$PRETTY_NAME"'
```

鍵、HostName、Userなどの接続詳細は`~/.ssh/config`が正本です。`gar setup`へは
Host見出しの`raspi5`だけを保存します。

## 7. 必要なTargetだけADB USB-C経路を使う

この節はRaspberry Pi 5標準手順では不要です。USBだけで到達する別Targetが
`ADB USB-C` backendを選択した場合に使用します。

まず WSL Hub 側で確認します。

```bash
gar usb list
gar usb status
adb devices
```

未 share と表示された場合は、Windows の管理者 PowerShell で一度だけ実行します。

```powershell
usbipd bind --busid <busid>
```

その後 WSL Hub 側で:

```bash
gar usb attach --busid <busid>
adb devices
```

`device` と表示されれば OK です。

`gar target deploy` はADB接続失敗を分類し、Terminal Bridge経由で`gar usb list` / `gar usb attach`の復旧手順を案内します。ただし初回の`usbipd bind`だけは管理者PowerShellが必要です。

## 8. 実機へ deploy する

選択したworkspaceのTarget/OS recipeを一度適用してから、最新target artifactを
`gar setup`で設定した実機へ配置します。

```bash
gar target prepare --workspace Local/Product  # 初回・recipe更新時
gar target build --workspace Local/Product
gar target deploy --workspace Local/Product
```

`target prepare`の中身はGaplessAgentRuntimeへ直書きせず、選択Targetの
`target.json`が指定するOS別recipeで決まる。Raspberry Pi 5 / Raspberry Pi OS
recipeはroot SSHログインや`NOPASSWD: ALL`を設定しない。GARのroot所有限定installer
だけをsudo実行可能にし、実機service用の`gar`user、device group、共通の
`gar-app@.service`を導入する。実機のGPIO/SPI dummy runtimeは導入しない。

旧GAR試作版の`/etc/sudoers.d/90-gar-deploy`が残っていればrecipeが削除し、
`/usr/local/lib/gar/gar-target-install`だけをpasswordなしで実行できるruleへ移行する。
管理者が別名で作ったsudoers設定は変更しない。

systemd型Targetではproduct artifactを`/opt/gar/apps/<app>`へ配置し、実行入口を
`run`とする。boot設定はTarget recipeが所有し、product固有の永続設定は
`/etc/gar/<app>.env`へ分離する。したがってapplicationの再deployやrecipeの再適用で
SSH鍵とproduct設定は消えない。

CodespacesでGAR外から作成済みのbundleを再取得してdeployする場合:

```bash
gar target fetch
gar target deploy
```

配置結果を確認します。`APP`はartifactのapplication名へ置き換えます。

```bash
ssh raspi5 'ls -l /opt/gar/apps/APP/run'
ssh raspi5 'systemctl is-enabled gar-app@APP.service'
```

## 9. RasPi5 で実行する

共通serviceはenvなしでも起動し、`/etc/gar/APP.env`が存在する場合だけ上書き設定として
読み込みます。PnPや安全なdefaultを持つproductは、deploy直後から起動できます。
実機固有値が必要なproductだけ、READMEに従ってartifact同梱の`.env.example`から
永続設定を作成します。接続先や認証情報をGARが推測して書き込みません。

```bash
ssh raspi5
sudo install -D -m 0644 /opt/gar/apps/APP/APP.env.example /etc/gar/APP.env
sudo editor /etc/gar/APP.env
sudo systemctl restart gar-app@APP.service
systemctl status gar-app@APP.service --no-pager
```

serviceを介さずentry pointだけ診断するときは、永続設定を読み込んで`gar`accountで
実行します。通常運用の起動・再起動はsystemdを使用します。

```bash
sudo systemctl restart gar-app@APP.service
journalctl -u gar-app@APP.service -n 100 --no-pager
```

期待:

```text
gar-app@APP.service が active
application logに起動完了とreal deviceのopen結果が出る
productの物理入力を操作すると、実出力・表示・network送信が反応する
```

停止・再開は`systemctl stop/restart gar-app@APP.service`で行います。

## 10. よくある詰まり方

### `gar setup` で不足コマンドが出る

まず案内に従います。sudo や認証が必要なものは人間が visible terminal で実行します。

```bash
gar setup --no-install
```

出力を AI に貼ると、次の手順に分解できます。

### `gar code start` が Codespace を選べない

```bash
gh auth status
gh codespace list
gar code start --codespace <codespace-name>
```

### `gar sim runtime diag --json` が `"ok": false`

```bash
gar sim runtime diag --json
gar sim gpio status --json
gar sim runtime log
ssh my-sim-host 'systemctl --no-pager --full status gar-sim.target gar-bridge.service gar-gpio-sim.service'
```

出力を貼って「どこが悪い？」と聞けばよいです。

### `gar target deploy` が artifact を見つけられない

Codespace 側で artifact bundle の場所を確認します。

```bash
ls -la /workspaces/gar-build-env/artifacts/from-codespace
cat /workspaces/gar-build-env/artifacts/from-codespace/artifact.json
```

WSL Hub 側で取得し直します（取得元は workspace の build environment 設定から解決されます）。

```bash
gar target fetch
gar target deploy
```

### adb device が見えない

```bash
gar usb list
gar usb attach
adb kill-server
adb start-server
adb devices
```

`Not shared` の場合は Windows 管理者 PowerShell で:

```powershell
usbipd bind --busid <busid>
```

### RasPi5 で `/dev/i2c-1` や `/dev/spidev0.0` がない

RasPi5 側で:

```bash
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo reboot
```

### `gar-app@APP.service` が起動しない

```bash
ssh raspi5 'systemctl status gar-app@APP.service --no-pager'
ssh raspi5 'journalctl -u gar-app@APP.service -n 100 --no-pager'
```

`/opt/gar/apps/APP/run`が無ければ`product-target-build.sh`のartifact contractを確認します。
ログが必須設定の不足を示す場合だけ、product READMEに従って`/etc/gar/APP.env`を作ります。



## 11. 最短コマンドまとめ

思い出し用の最短版です。

```bash
cd ~/Yurufuwa/GAR/GaplessAgentRuntime
git pull
make init
make start
gar setup
gar code start

# Codespace 側で target repo をビルドし artifact bundle を作る

gar sim host start
gar sim runtime deploy
gar sim runtime start
gar sim runtime diag --json
ssh my-sim-host '~/sensor_demo'

gar target prepare --workspace Local/Product  # 初回・recipe更新時
gar target build --workspace Local/Product
gar target deploy --workspace Local/Product
ssh raspi5 'systemctl status gar-app@APP.service --no-pager'
```

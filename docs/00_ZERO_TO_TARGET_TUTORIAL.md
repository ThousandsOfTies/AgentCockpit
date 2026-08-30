# 0から実機動作までのチュートリアル

この文書は、Product workspaceをGARへ登録し、simulationで確認してからPhysical Targetへ
deployする標準経路に加え、Windows／WSL／Docker／実機をどのように分担させるかを示す。
個々の引数は[コマンドリファレンス](01_COMMAND_REFERENCE.md)、現行構成の環境差は
[開発環境](03_DEVELOPMENT_ENVIRONMENT.md)と[シミュレーション](06_SIMULATION.md)を参照する。

## この文書の現在地

2026-08-30時点では、GAR CLIはWSL上で動作する。Windowsをユーザー向けentrypointにする構成は、
NXP UUUとUSB-C debug UARTを扱った経験から合意した**移行目標**であり、Windows版GAR launcher、
Windows native UUU adapter、Windows COM adapterはまだ実装されていない。

この文書では状態を次のように区別する。

| 表記 | 意味 |
|---|---|
| 現行 | 現在のrepositoryに実装され、WSL上の`gar`から利用できる |
| 移行目標 | 操作方法として合意したが、adapterまたはlauncherの実装が必要 |
| 人間作業 | 物理操作、認証、管理者権限、危険な対象の選択など、自動化しない作業 |

以下の既存チュートリアルの`gar`コマンドは、特記しない限り現行のWSL shellで実行する。
移行後もコマンド名と引数は変えず、Windows launcherが実行場所を隠蔽する。

## 結論: Windowsを入口、WSLをLinux実行環境にする

移行目標は「Windowsですべてを実行する」ことではない。Windowsがuser／AI向けの入口と
local peripheralを所有し、file-intensiveなLinux作業はWSLへ固定的に委譲する。

```text
Human / AI
    │ 同じ gar コマンド
    ▼
Windows host entrypoint                         移行目標
    ├─ build / test / Git / rg ───────────────► WSL ext4 workspace
    ├─ containerized Linux workload ──────────► WSL2 + Docker Desktop
    ├─ NXP full-image flash ──────────────────► Windows native uuu.exe
    └─ boot log / interactive console ────────► Windows COM port
```

Windows hostでのroutingは「native commandがあれば使い、なければfallbackする」という動的判定に
しない。capabilityごとに実行場所を固定し、user／AIには同じ`gar` interfaceだけを公開する。

| 操作 | Windows hostでの固定先 | 理由 |
|---|---|---|
| Product build、test、Git、source検索 | WSL | POSIX semanticsとWSL ext4上のfile performanceを維持する |
| Linux container build／simulation | WSL2 backend | Linux path、bind mount、inotifyを維持する |
| NXP UUU flash | Windows | USBをWindowsが直接所有し、usbipd attach／detachを不要にする |
| USB-C debug UART | Windows | `COMn`を直接利用し、USB device所有権の移動を避ける |
| Linux専用toolがUSBを直接必要とする場合 | WSL + usbipd | native Windows adapterがない場合だけの明示的な例外 |

Windows SSH serverを同一host内のtransportとして追加しない。WindowsからWSL commandを起動する
境界には`wsl.exe`相当のprocess adapterを使い、SSHはremote machineへの接続に限定する。
会話中の`gar-host.exe`はこの薄いWindows entrypointを説明するための仮称であり、実装済みbinary名でも、
常駐SSH serverでもない。公開command名はOSにかかわらず`gar`のままにする。

### OS差を吸収する境界

user／AIがOSごとのcommand名を選ばないことが目的である。Product hookやTarget recipeへ
`if Windows`／`if WSL`を散らさず、host adapterがcapabilityを固定routingする。

| user-facing host | 移行目標の実行model | 状態 |
|---|---|---|
| Windows | Windows entrypoint + WSL Linux executor + Windows peripheral adapter | launcher／UUU／COMは未実装 |
| Linux | 現行GAR core、Linux toolchain、native deviceを直接利用 | 現行の基本経路 |
| macOS | 同名entrypointからnative toolまたはcontainer backendを利用 | host adapter、実機経路とも未設計・未検証 |

Codespaces、EC2、Physical Targetはuser-facing host OSの追加種類ではなく、GARが操作するremote
Build／Simulation／Target environmentとして扱う。

## この結論に至った経緯

| 検討した構成 | 分かったこと | 判断 |
|---|---|---|
| WSL常駐、時々Docker | Linux開発は自然だが、UUU／serialのたびにusbipd操作が必要 | 実機所有者としては不向き |
| WSLからWindows SSH serverへ接続 | Windows native toolは呼べるが、同一hostに認証・daemon・path変換を追加する | 採用しない |
| WSLからWindows executableを個別に直接実行 | ADBでは有効だが、commandごとの呼び分けがuser interfaceへ漏れる | GAR adapter内に閉じ込める |
| Windowsですべてbuild／検索 | USBは容易だが、Linux build、GNU互換、Defender、cross-filesystem I/Oが問題 | source処理はWSLへ残す |
| Windows + Docker Desktop | Linux containerは利用できるが、sourceをNTFSへ移す理由にはならない | WSL2 backendとして利用可能 |
| WindowsからWSL filesystemを参照 | `\\wsl.localhost`で参照でき、Yurufuwa作業領域rootの短いaliasも作れる | device toolのartifact参照に使う |

このため、レベルシフトするのは**操作の起点**であり、Product sourceやbuild directoryの保存先ではない。
Docker Desktop上で、現在のsimulationが要求するprivileged device、host cgroup、`/sys` mount等が
Linux hostと同等に動くことはまだ検証していない。Docker Desktopの導入だけで既存buildやsimulationが
自動的に移行するとみなさず、Product hook／environmentごとに検証する。

## Yurufuwa作業領域をWindows側へ見せる

artifactや個別Projectへのlinkを張り替えるのではなく、複数Projectを含むYurufuwa作業領域rootへ
不変のlinkを一本だけ作る。一般形と現在のPCでの対応は次のとおりである。

```text
C:\GAR\Yurufuwa
    → \\wsl.localhost\<Distro>\<WSL-workspace-root>

現在のPC:
C:\GAR\Yurufuwa
    → \\wsl.localhost\Ubuntu-26.04\home\user\Yurufuwa
```

Windowsのdirectory junctionはUNC target用ではないため、directory symbolic linkを使う。
2026-08-28のこのmachineでの試験では通常権限での作成が拒否されたため、次は管理者PowerShellで
一度だけ実行する。

```powershell
New-Item -ItemType Directory -Force C:\GAR
New-Item -ItemType SymbolicLink `
  -Path C:\GAR\Yurufuwa `
  -Target '\\wsl.localhost\Ubuntu-26.04\home\user\Yurufuwa'
Test-Path C:\GAR\Yurufuwa\GAR\GaplessAgentRuntime
```

配下のProjectに追加linkは作らない。Project切替はYurufuwa配下のdirectory移動または
GARの`--workspace`選択で行う。

```text
C:\GAR\Yurufuwa\GAR\GaplessAgentRuntime
C:\GAR\Yurufuwa\GarServoPet
C:\GAR\Yurufuwa\GarStreamTx
```

linkはpathを短くするnamespace bridgeであり、WSL filesystemをNTFSへ変換しない。Windows toolで
source tree全体を再帰走査せず、Windows native UUUがbuild imageを読むなど、境界を越える操作を
限定する。WSL側では`/mnt/c/GAR/Yurufuwa`を逆向きに辿らず、元の
`/home/user/Yurufuwa`を使う。

## 検索commandの方針

`findstr`は単純なWindows text filterには使えるが、`grep`互換のproject検索interfaceにはしない。
正規表現、文字code、除外規則、再帰検索の差をuser／AIへ露出させないため、source treeの検索は
WSL上の`rg`（ripgrep）へ固定する。Windows版GNU toolを導入する必要はない。

現行ではWSL shellから直接`rg`を使う。`gar grep`／`gar search`は未実装であり、実装するまでは
command referenceに存在するものとして扱わない。

## 人間が担当する作業

反復可能なbuild、deploy、diagnosticはGARへ収容する。一方、次は人間の判断または操作を残す。

| 時点 | 人間が行うこと | GAR／AIへ任せない理由 |
|---|---|---|
| PC初回準備 | WSL2とdistributionを有効化し、必要ならDocker DesktopのWSL integrationを有効化 | OS機能、license、再起動を伴う |
| 現行UUU経路の準備 | Windowsへusbipd-win、WSLへLinux版UUU／libusbを導入し、udev／groupでserial permissionを設定する | 現行backendはWSLのUSBとPOSIX serialを使う |
| 現行UUU接続 | 管理者権限で対象deviceを一度`usbipd bind`し、download USBとdebug UARTを明示的にattachする | USB所有権の移動と対象deviceの識別が必要 |
| 移行先Windows tool準備 | NXP公式`uuu.exe`、対象USB／UART driver、serial terminalを導入する | driver導入と配布元の確認が必要 |
| Project登録 | Yurufuwa作業領域rootのWindows link作成を管理者権限で承認し、link先を確認する | UACとlocal filesystem変更を伴う |
| 実機経路の初回検証 | adapter実装後、`uuu.exe`がproject link越しのimageを読めることと、COM adapterが期待logを読めることを確認する | path aliasはWin32 tool互換性を保証しない |
| `gar setup` | Product、Target Pack、Build／Simulation／Target environment、machine-local接続先を選ぶ | 製品と接続対象の意味を決める作業 |
| Hardware準備 | 配線、電圧、boot switch、download USB、debug UART、電源を資料どおり接続する | 物理世界をsoftwareから推測できない |
| Target識別 | USB device、COM port、対象storage、接続台数を目視で確定する | 誤対象へのflashを防ぐ |
| 認証 | cloud login、GitHub device login、host key、secret／runner登録を承認する | credentialをGARへ保存しない |
| 破壊的操作 | full-image flash、infra destroy等の対象と実行時点を承認する | data消去や外部resource変更を伴う |
| 実機受入れ | LED、display、音、機構、発熱などmachine-readableでない結果を確認する | sensor／fixtureがない観測は自動化できない |

一度人間が選んだmachine-local情報は設定へ保存し、日常操作のたびに再入力させない。ただしUSBの
bus IDやCOM portは差し直しで変わり得るため、対象を自動推測してflashしない。

## 技術的な根拠

- [Microsoft: WSLからUSB deviceへ接続するにはusbipd-winが必要](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)
- [Microsoft: Linux toolで扱うprojectはWSL filesystemへ置く](https://learn.microsoft.com/en-us/windows/wsl/filesystems)
- [Docker: bind mountするsourceはLinux filesystemへ置く](https://docs.docker.com/desktop/features/wsl/best-practices/)
- [NXP mfgtools: UUUはWindows binaryを提供](https://github.com/nxp-imx/mfgtools)

## ゴール

```text
Product workspace
  → build artifact
  → simulation deploy / diag
  → Physical Target
      ├─ recipe-backed Linux: preflight → deploy → diag
      └─ NXP UUU full image: 人間がboot／USB確認 → deploy内でflash／serialVerify
```

複数node製品では、最後に`gar system test`でE2E scenarioを実行する。

## 前提

- 現行CLIを使う場合はWSL2からrepositoryを操作できる。
- 移行目標ではWindowsを入口にしても、Product sourceとbuild directoryはWSL filesystemへ置く。
- Python 3、Git、対象environmentに必要なCLIを導入できる。
- Product workspaceにbuild hookとsourceが存在する。
- Target Packは`gar-tools`にあり、Product固有hardware bindingはProduct workspaceにある。
- 実機配線はProductのbinding／配線資料と、Target Packのpin／電圧資料を突き合わせて行う。

GAR本体はProduct固有の配線図を持たない。Board capabilityは`gar-tools/targets/<target-id>/`、
実際の部品と配線はProduct workspaceを正本とする。

## 1. GARを初期化する

```bash
cd /path/to/GaplessAgentRuntime
make init
make start
```

`make init`はlocal venv、`gar` entrypoint、VS Code Terminal Bridge、MCP設定を用意する。
日常操作は`make`ではなく`gar`を使用する。

## 2. Workspaceとenvironmentを設定する

```bash
gar setup
```

対話では次を選択・入力する。

1. Product workspaceのpathと表示名
2. Target Pack
3. BuildEnvironment（LocalまたはGitHub Codespaces）
4. SimulationEnvironment
5. TargetEnvironment
6. SSH config Host、serial port等のmachine-local接続情報

設定はGaplessAgentRuntime直下の`.gar/config.json`へ保存される。秘密鍵そのものやProductの
runtime secretは保存しない。登録後はworkspace名を確認する。

```bash
gar setup --no-install
```

`--no-install`は不足commandを表示するだけで、導入処理を実行しない。

## 3. Hardware contractを検証する

Productにhardware contractがある場合、実機へ触れる前にoffline検証する。

```bash
gar hw validate --workspace Local/Product --json
```

検証対象は次の三つである。

- Product所有の`requirements.json`
- Target Pack所有の`capabilities.json`
- Product×Target所有のbinding

ここではschema、device、driver、電圧、GPIO／SPI競合、速度、video FPS等を確認する。
実Target上のdevice存在確認は後段の`preflight`／`diag`で行う。

## 4. Simulation artifactをbuildする

```bash
gar sim runtime build --workspace Local/Product
gar sim app build --workspace Local/Product
```

選択したBuildEnvironmentがProduct hookを実行し、WSL側artifact storeへsnapshotを作る。

```text
.gar/artifacts/<workspace-id>/sim_runtime/<build-id>/
.gar/artifacts/<workspace-id>/sim_app/<build-id>/
```

buildとdeployは別操作である。deployはbuildやfetchを暗黙に実行しない。

Codespacesを明示的に起動・接続する必要がある場合は次を使う。

```bash
gar code boot --workspace Local/Product
gar code start --workspace Local/Product
gar code status --workspace Local/Product
```

## 5. Simulationを起動する

host lifecycleを持つenvironmentでは先にhostを起動する。

```bash
gar sim host start --workspace Local/Product
gar sim host status --workspace Local/Product
```

runtimeとapplicationを配置する。

```bash
gar sim runtime deploy --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

`diag`の`ok`だけでなく、service、device、Bridge、application health、build IDを確認する。
仮想I/O操作はBridge経由で行う。

```bash
gar sim io press --workspace Local/Product --device button --line 17
gar sim runtime log --workspace Local/Product
```

使用可能なdevice／引数はTarget Packと`gar sim io --help`を参照する。

## 6. 複数node systemを検証する

Productに`gar-system.json`がある場合は、nodeを個別に操作せずsystem単位で実行できる。

```bash
gar system build --file /path/to/gar-system.json --json
gar system deploy --file /path/to/gar-system.json --json
gar system start --file /path/to/gar-system.json --json
gar system diag --file /path/to/gar-system.json --json
gar system test \
  --file /path/to/gar-system.json \
  --scenario /path/to/scenario.json \
  --bridge tx=http://127.0.0.1:8081 \
  --bridge rx=http://127.0.0.1:8080 \
  --json
```

Bridge URLはmachine-local入力なので、system schemaやartifactへ埋め込まない。

## 7. Recipe-backed Linux Targetを準備する

SSH／file-transfer型Targetでは、初回またはTarget recipe更新時にだけ実行する。

```bash
gar target prepare --workspace Local/Product
```

`prepare`の内容はTarget Packが所有する。Raspberry Pi OSではsystemdと限定sudo、RK3506
BuildrootではBusyBox initとroot helperを設定する。GAR coreはdistribution名で分岐しない。

UUUはapplication lifecycleではなくfull-image provisioningであるため、この節の`prepare`と
`configure`を実行しない。現行UUU backendの`target prepare`は意図的にerrorを返す。

永続的なProduct設定が必要なら、deployとは分けて明示する。

```bash
gar target configure \
  --workspace Local/Product \
  --app product-app \
  --file /path/to/product-app.env \
  --json
```

通常のapplication deployは`/etc/gar/<app>.env`、SSH鍵、host keyを上書きしない。

## 8. Target artifactをbuildする

```bash
gar target build --workspace Local/Product
```

buildはrecipe-backed Linux TargetとUUU Targetに共通である。Product hookが実機用artifactを作り、
GAR artifact storeへsnapshot化する。

### Recipe-backed Linux Targetを事前検証する

```bash
gar target preflight --workspace Local/Product --json
```

`preflight`はLinux file-transfer Target専用である。artifactを転送せず、次を読み取り専用で照合する。

- artifact checksumとprovenance
- Target ID、architecture、ABI、libc、toolchain triple
- active gar-toolsと適用済みrecipeのidentity
- deploy／configure／lifecycle capability

不一致を無視してdeployしない。source、gar-tools、recipeのどれを更新すべきか診断結果から判断する。
UUU Targetはcompatibility probeを持たないため、現行の`target preflight`には対応しない。

## 9. Recipe-backed Linux Targetへdeployして収束を確認する

```bash
gar target deploy --workspace Local/Product
gar target status --workspace Local/Product --json
gar target diag --workspace Local/Product --json
gar target log --workspace Local/Product
```

deploy成功の基準は転送完了ではない。applicationがhealthを満たし、running build IDが
配置artifactのbuild IDと一致することを確認する。

## 10. NXP UUU Targetへfull imageを書き込む

FRDM-IMX91Sの現行UUU backendは、WSL上のGAR processからLinux版`uuu`を起動し、起動確認も
POSIX serial device（`/dev/tty*`）で行う。この経路ではdownload USBとdebug UARTをWSLへ
attachする必要がある。

UUU Targetで利用するGAR lifecycleは`target build`と`target deploy`に限定される。`target prepare`、
`configure`、`preflight`、`status`、`log`、`diag`は利用できず、application healthやrunning build IDの
収束を報告しない。

### 10.1. Imageをbuildする

```bash
gar target build --workspace Local/Product
```

### 10.2. 人間がTargetと物理状態を確認する

deploy commandを実行する前に、次を順に確認する。

1. Target Pack、Board manual、Product配線資料に記載されたdownload USBとdebug UARTを取り違えていない。
2. 対象Board、書込みstorage、image build IDが正しい。
3. boot switchをSerial Downloader modeへ切り替えた。
4. serial terminal等が確認対象の`/dev/tty*`またはCOM portを占有していない。
5. full-image書込みによる既存data消去を承認した。

### 10.3. 現行WSL backendでは二つのUSB deviceをattachする

10.3と10.4は現行WSL backendの経路である。Windows native adapterの実装後は、この二節を
10.5の経路へ置き換える。

`gar usb`が記憶するbus IDは一件だけなので、自動検出に頼らず、人間が`gar usb list`でdownload USBと
debug UARTを識別して各commandへ明示する。

```bash
gar usb list
gar usb bind --busid <download-usb-busid>
gar usb bind --busid <debug-uart-busid>
gar usb attach --busid <download-usb-busid>
gar usb attach --busid <debug-uart-busid>
gar usb status --busid <download-usb-busid>
gar usb status --busid <debug-uart-busid>
```

`bind`が管理者権限不足で失敗した場合は、表示された二つのbus IDを推測せず、Windows管理者
PowerShellでそれぞれ`usbipd bind --busid <busid>`する。bind後のattachは通常権限で実行する。

### 10.4. Imageを書き込む

物理状態とUSB attachを確認した後に実行する。

```bash
gar target deploy --workspace Local/Product
```

`target deploy`はartifact manifestのimageを検証してUUUを実行し、Target Packに`serialVerify`が
あれば同じdeploy内でboot logのpatternを待つ。

### 10.5. Windows native経路への移行目標

移行後もuser／AIが実行するcommandは変えない。

**移行目標（未実装）のPowerShell interface:**

```powershell
gar target deploy --workspace Local/Product
```

ただしWindows launcherのadapterが、artifact pathをYurufuwa作業領域link経由のWindows pathへ変換し、
Windows native `uuu.exe`とWindows COM adapterを起動する。native UUU／COM adapterが実装され、
実機で検証されるまでは、このPowerShell例を利用可能な現行commandとして扱わない。この経路では
download USBとdebug UARTをWindowsが所有するため、10.3のusbipd操作は行わない。

### 10.6. 書込み後に人間が行うこと

1. deployの終了codeと`serialVerify`結果を保存する。
2. boot switchを通常起動に必要なmodeへ戻す。
3. Board manualどおりに電源を再投入する。
4. serial boot logと、必要ならdisplay／LED／発熱等を確認する。

## 11. Linux toolがUSB Targetを直接必要とする場合

NXP UUU以外でも、Linux専用vendor toolなどWSL process自身がUSB deviceを必要とする場合に限り、
対象を確認してからusbipdでattachする。複数deviceの場合は、それぞれのbus IDを明示する。

```bash
gar usb list
gar usb bind --busid <busid>
gar usb attach --busid <busid>
gar usb status --busid <busid>
```

USB attachとimage flashは物理状態を変更するため、対象deviceを推測して実行しない。
Windows native UUU／COMへ移行したTargetでは、この手順を標準経路にしない。`gar usb`は
Linux専用toolのための互換・例外経路として残す。

## 12. 終了

```bash
gar sim runtime stop --workspace Local/Product
gar sim host stop --workspace Local/Product
gar code stop --workspace Local/Product
gar code shutdown --workspace Local/Product
```

Physical Targetの停止はBoard固有であり、GARのapplication lifecycleと電源操作を混同しない。

## よくある失敗

| 症状 | 最初に確認すること |
|---|---|
| workspaceを選べない | `gar setup`の登録pathと現在directory |
| artifactがない | 対応する`build`または`fetch`を実行したか |
| SSH接続に失敗 | `ssh <config-host> true`、host key、認証session |
| `preflight`がidentity drift | source／gar-toolsを同期して再build、recipe更新なら再prepare |
| deploy後も古い挙動 | `gar target diag --json`のexpected／running build ID |
| simulation deviceがない | `gar sim runtime diag --json`のservice／device状態 |
| scenarioが失敗 | node health、Bridge URL、metrics freshness、cleanup結果 |
| 実機I/Oがない | Product binding、pinmux、kernel driver、電源、物理配線 |
| Windows project pathを開けない | WSL distribution名、`\\wsl.localhost`の到達性、directory symbolic linkのtarget |
| project検索が遅い | Windows processでWSL treeを走査していないか。WSL上の`rg`を使う |
| Windows native UUU／COMへrouteされない | adapterは移行目標で未実装。現行UUUはLinux／WSL backendである |
| UUUがimageを開けない | project link先、artifact実体、UUUのWSL共有path対応を確認し、未検証を成功扱いしない |

検証済み範囲と未実装backendは[検証状態](07_VERIFICATION.md)を参照する。

# 0から実機動作までのチュートリアル

この文書は、WindowsをGARの操作面にし、Dockerでbuild、VirtualBoxまたはAWSの
Ubuntu Sim Hostでsimulation、Windows nativeのUSB／COM／UUUでNXP実機へ進む標準経路を示す。
個々のoptionは[コマンドリファレンス](01_COMMAND_REFERENCE.md)、役割分担は
[開発環境](03_DEVELOPMENT_ENVIRONMENT.md)、simulationの詳細は[シミュレーション](06_SIMULATION.md)を参照する。

## この文書の現在地

2026-08-31時点で次のadapterと設定階層をrepositoryに実装している。

- Windowsから起動できる`scripts\gar.cmd`とWindows対応Python entrypoint
- Product hookをLinux container内で実行するDocker BuildEnvironment
- `SimulationEnvironment=ssh_remote`と独立した`Sim Host=virtualbox|aws_ec2`
- VirtualBox VM lifecycle adapterとVirtualBox／AWS共通Ubuntu bootstrap
- Windows host nativeの`uuu.exe`とpyserial `COMn`によるNXP flash／boot verification
- Windows／POSIXのprocess lifecycleとSIM artifact architecture guard

一方、実Windows PCのDocker Desktop、実VirtualBox VMの`gpio_sim`、実NXP Boardの
UUU／COMまで通すE2Eはまだ実施していない。この文書は実装済みの操作契約と、
実machineで人間が確認すべき境界を分けて記載する。

## 全体像

```text
Human / AI
    │ 同じ gar command
    ▼
Windows host
    ├─ Local Docker ── Product build / test / Linux tools
    ├─ VirtualBox Ubuntu ── local Linux-device Sim Host (`gpio_sim`)
    ├─ AWS Ubuntu ───── remote Sim Host variant
    └─ Native USB / COM ── NXP UUU / serial console
```

WSLはGARの必須構成要素ではない。Docker Desktopが内部でWSL2を使う場合も、
ユーザーとGARが見るのはDocker Engineである。WindowsにSSH serverを立てたり、
`wsl -c "make all"`とhost commandを手で呼び分けたりしない。

VirtualBoxとAWSは別のsimulatorではない。Ubuntu上の同じLinux device runtimeを実行し、
ローカルVMかremote VMかというSim Host providerの差だけをGARが吸収する。

## 人間の作業一覧

| 時点 | 人間が行うこと | 理由 |
|---|---|---|
| Windows初回準備 | Python 3、Git、Docker Desktop、VirtualBox、OpenSSH Clientを正規配布元から導入 | license、UAC、OS再起動がある |
| NXP初回準備 | NXP UUU、download USB driver、debug UART driverを導入 | vendorとdeviceの信頼判断が必要 |
| VirtualBox初回準備 | Ubuntu VM、network、SSH key／host key、bootstrap、`gpio_sim`を準備 | VM／kernelはsoftwareから推測できない |
| AWS初回準備 | login、region、instance type、key、課金上限を選ぶ | credentialと課金をGARが代行決定しない |
| `gar config` | Product、Target、Build、Simulator、Sim Host、接続先を選ぶ | どの製品／machineを操作するかの決定 |
| 実機作業 | 配線、電圧、boot switch、USB、COM、storageを確認 | 誤接続／誤flashを防ぐ |
| 破壊的操作 | full-image flash、Terraform destroyの対象と時点を承認 | data消去や外部resource変更がある |
| 受入れ | display、LED、音、機構、発熱などを確認 | fixtureのない物理観測は自動化できない |

一度選んだVM名、SSH alias、COM portはmachine-local設定へ保存する。ただしUSB／COMは
差し直しで変わり得るので、flash直前に人間が再確認する。

## 0. Windows hostを準備する

repositoryをWindows側の作業領域へcloneする。新規構成ではWSL filesystemを
Windowsへsshfs／junctionでmountする必要はない。Product workspaceもWindows側に置き、
build時はDockerがbind mountする。

PowerShellで非破壊的な確認を行う。

```powershell
python --version
git --version
docker version
VBoxManage --version
ssh -V
uuu.exe -h
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name
```

`uuu.exe -h`とserial一覧はtool／portの存在確認だけで、imageを書き込まない。
Docker Desktopのdaemon起動、workspaceのfile sharing、VirtualBoxのnetworkは人間が確認する。

## 1. GARを起動する

Windowsでrepository rootから実行する。

```powershell
scripts\gar.cmd setup
scripts\gar.cmd config
scripts\gar.cmd --help
```

`setup`はlauncherだけが処理し、repository内の`.venv\Scripts\python.exe`とGAR用Python依存を
必要に応じて用意する。`scripts`がPATHに無ければユーザーPATHへ登録するか`[Y/n]`で確認する。
続けてWindowsではPowerShell、LinuxではBash、macOSではZshのTab補完登録を`[Y/n]`で確認する。
登録済みならmarkerを検出してSKIPし、機能追加後の候補は現在のCLI parserから自動取得する。
変更はPowerShell／Windows Terminal／VS Code／ChatGPT Appをいったん終了して開き直した後に
有効になる。workspace／environment設定は行わず、
続く`config`が担当する。PATH登録後は以下を`gar ...`と表記する。Linux／macOSのhostでは
`scripts/gar ...`を使う。公開commandと引数は同じである。

## 2. Workspaceとenvironmentを設定する

```powershell
gar config
```

対話で次を選ぶ。

1. Product workspaceのpathと表示名
2. Target Pack
3. BuildEnvironment: 通常は`Local Docker`、必要なら`GitHub Codespaces`
4. SimulationEnvironment: Linux device simulationなら`SSH Remote`
5. Sim Host: localなら`Local Ubuntu (VirtualBox)`、remoteなら`Remote Ubuntu (AWS EC2)`
6. TargetEnvironment: SSH／ADB／esptool／UUU等
7. VirtualBox VM名、SSH config Host alias、COM port等のmachine-local値

```powershell
gar config --no-install
```

`--no-install`は不足commandを表示するだけで、導入を実行しない。設定は
GaplessAgentRuntime直下の`.gar/config.json`に保存する。秘密鍵やProduct runtime secretは保存しない。

Linux device simulationの例では概念上次の関係になる。

```json
{
  "selected_environments": {
    "codespace": "local",
    "simulator": "ssh_remote",
    "simulation_host": "virtualbox",
    "target": "uuu"
  },
  "simulation_host": {
    "provider": "virtualbox",
    "host": "gar-sim-local",
    "arch": "x86_64"
  },
  "virtualbox": {
    "vm": "GAR Ubuntu Sim"
  },
  "target": {
    "serial": "COM5"
  }
}
```

`codespace: "local"`は互換IDで、UI上の意味は`Local Docker`である。

## 3. VirtualBox local Sim Hostを準備する

AWSを使う場合はこの節を飛ばし、`gar sim infra`でAWS providerを準備する。
VirtualBoxの初回作業は次のとおりである。

1. Ubuntu VMを作り、host-only networkまたはNAT port forwardでWindowsからSSH可能にする。
2. `infra/simulation-host/ubuntu-bootstrap.sh`をVM内でroot権限で実行する。
3. `sudo modprobe gpio-sim && test -d /sys/kernel/config`が成功することを確認する。
4. Windowsの`%USERPROFILE%\.ssh\config`へ固定aliasとkeyを登録する。
5. 初回`ssh gar-sim-local`でhost keyと接続先を人間が確認する。

```sshconfig
Host gar-sim-local
    HostName 192.168.56.10
    User gar
    IdentityFile C:/Users/USER/.ssh/gar-sim-local
```

```powershell
VBoxManage showvminfo "GAR Ubuntu Sim" --machinereadable
ssh gar-sim-local "uname -m; sudo modprobe gpio-sim; test -d /sys/kernel/config"
gar sim host status --workspace Local/Product
```

詳細は[`infra/virtualbox/README.md`](../infra/virtualbox/README.md)を参照する。

## 4. Hardware contractを検証する

Productにhardware contractがある場合、実機へ触れる前にoffline検証する。

```powershell
gar hw validate --workspace Local/Product --json
```

検証対象はProduct所有の`requirements.json`、Target Pack所有の`capabilities.json`、
Product×Target所有のbindingである。ここではschema、device／driver、電圧、GPIO／SPI競合等を
検証する。実Target上のdevice存在は後段の`preflight`／`diag`で確認する。

## 5. Simulation artifactをDockerでbuildする

```powershell
gar sim runtime build --workspace Local/Product
gar sim app build --workspace Local/Product
```

Local DockerはProduct workspaceを`/workspace`へbind mountし、container内のBashで次を実行する。

- `scripts/product-sim-env-build.sh`
- `scripts/product-sim-build.sh`

既定の`gar-build-env:ubuntu-24.04`がなければ`infra/build/`からbuildする。Product hookが
Docker daemonを使わない場合は`build.docker_socket=false`にし、host daemonへの権限を渡さない。

成果物はhost側storeの別snapshotへcaptureする。

```text
.gar/artifacts/<workspace-id>/sim_runtime/<build-id>/
.gar/artifacts/<workspace-id>/sim_app/<build-id>/
```

buildとdeployは別操作である。deployはbuildやfetchを暗黙実行しない。

## 6. Simulationを起動する

VirtualBoxとAWSでcommandは同じである。

```powershell
gar sim host start --workspace Local/Product
gar sim host status --workspace Local/Product
gar sim runtime deploy --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

VirtualBoxの場合、`host start`は`VBoxManage startvm ... --type headless`を使う。AWSの場合は
instanceを起動し、SSH configのaddressを更新する。runtime／applicationの配置はどちらも
共通のSSH／SCP経路である。

`diag`の`ok`だけでなく、service、device node、Bridge、application health、build IDを確認する。

```powershell
gar sim io press --workspace Local/Product --device button --line 17
gar sim runtime log --workspace Local/Product
```

### Sim Hostを切り替えた場合

VirtualBoxの既定はx86_64、AWS Gravitonの既定はaarch64である。`gar config`でproviderを
切り替えたら、SIM_RUNTIMEとSIM_APPの両方を再buildする。異なるarchitectureの
最新snapshotをdeployしようとするとGARは拒否する。

## 7. 複数node systemを検証する

```powershell
gar system build --file C:\path\to\gar-system.json --json
gar system deploy --file C:\path\to\gar-system.json --json
gar system start --file C:\path\to\gar-system.json --json
gar system diag --file C:\path\to\gar-system.json --json
gar system test `
  --file C:\path\to\gar-system.json `
  --scenario C:\path\to\scenario.json `
  --bridge tx=http://127.0.0.1:8081 `
  --bridge rx=http://127.0.0.1:8080 `
  --json
```

Bridge URLはmachine-local入力なので、system schemaやartifactへ埋め込まない。

## 8. Recipe-backed Linux Targetを準備する

SSH／file-transfer型Targetでは、初回またはTarget recipe更新時だけ実行する。

```powershell
gar target prepare --workspace Local/Product
```

`prepare`の内容はTarget Packが所有する。NXP UUUはapplication lifecycleではなくfull-image
provisioningなので`target prepare`と`target configure`を実行しない。

永続的なProduct設定が必要なrecipe-backed SSH Targetでは明示的に実行する。

```powershell
gar target configure `
  --workspace Local/Product `
  --app product-app `
  --file C:\path\to\product-app.env `
  --json
```

## 9. Target artifactをbuildする

```powershell
gar target build --workspace Local/Product
```

Local Dockerの`product-target-build.sh`が実機用artifactを作り、host側storeへsnapshot化する。

Recipe-backed Linux Targetでは配置前にread-only検証を行う。

```powershell
gar target preflight --workspace Local/Product --json
```

checksum／provenance、Target ID、architecture／ABI／libc、recipe／tools identityの不一致を
無視しない。UUU Targetはcompatibility probeを持たないので`preflight`非対応である。

## 10. Recipe-backed Linux Targetへdeployする

```powershell
gar target deploy --workspace Local/Product
gar target status --workspace Local/Product --json
gar target diag --workspace Local/Product --json
gar target log --workspace Local/Product
```

deploy成功の基準はfile転送完了ではない。application healthとrunning build IDが
配置artifactのbuild IDと一致することを確認する。

## 11. NXP UUU Targetへfull imageを書き込む

Windows nativeの標準経路では、GAR processが同じWindows hostのPATHから`uuu.exe`を起動し、
`target.serial` の`COMn`をpyserialで開く。WSL、Linux版UUU、usbipd attach／detachは必要ない。

UUU Targetが利用するGAR lifecycleは`target build` → 人間確認 → `target deploy`である。
`prepare`、`configure`、`preflight`、`status`、`log`、`diag`はapplication lifecycleではないため使わない。

### 11.1 Imageをbuildする

```powershell
gar target build --workspace Local/Product
```

### 11.2 人間が書き込み対象を確認する

1. Target Pack、Board manual、Product配線資料のdownload USBとdebug UARTを取り違えていない。
2. 対象Board、書込みstorage、image build IDが正しい。
3. boot switchをSerial Downloader modeへ切り替えた。
4. UUUがdownload USBを認識している。
5. 設定済みCOM portがdebug UARTであり、serial terminalが占有していない。
6. full-image書き込みで既存dataを失う可能性を承認した。

確認用のread-only command例:

```powershell
uuu.exe -lsusb
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name
```

### 11.3 GARからflashする

```powershell
gar target deploy --workspace Local/Product
```

GARはTarget Packの`provisioning.uuu.command`をargvとして展開し、shellを経由せず
`uuu.exe`を起動する。`serialVerify`が定義されている場合は、書き込み後に
COM portで期待起動patternを待つ。このpattern検出はapplication health／running build IDの確認とは異なる。

### 11.4 書き込み後の人間作業

1. 電源を切り、boot switchを通常bootへ戻す。
2. flash toolとserial terminalがdeviceを開いたままでないことを確認する。
3. 再起動後のCOM log、LED／display／network等のProduct behaviorを確認する。
4. E2Eが未検証の段階ではUUU exit codeだけを成功報告にしない。

## 12. `gar usb`を使うlegacy compatibility経路

Linux-only USB toolがUSB device nodeを直接必要とする旧workspaceだけ、WSL + usbipdを明示的に使う。

```powershell
gar usb list
gar usb bind --busid <busid>
gar usb attach --busid <busid>
gar usb status --busid <busid>
gar usb detach --busid <busid>
```

USB所有権がWindowsからWSLへ移るので、対象BUSIDを人間が識別する。Windows native
UUU／COMの標準経路ではこのcommandを使わない。

## 13. 終了とresource回収

```powershell
gar sim runtime stop --workspace Local/Product
gar sim host stop --workspace Local/Product
```

VirtualBoxはACPI shutdown後にVM stateを確認する。AWSはinstance停止後もstorage等の課金が
残り得る。infraそのものを不要と判断した場合だけ、対象を確認して次を実行する。

```powershell
gar sim infra destroy
```

## よくある失敗

| 症状 | 確認する境界 |
|---|---|
| `docker` commandがない／daemonへ到達できない | Docker Desktopの導入、起動、context、file sharing |
| Product hookが見つからない | workspace path、`scripts/product-*.sh`、containerの`/workspace` |
| Docker buildが遅い | Windows bind mount、Defender、小file数、Codespaces利用の比較 |
| VirtualBox hostが起動しない | VM名／UUID、`VBoxManage showvminfo`、VirtualBox service |
| SSHでVMへ到達できない | host-only／NAT network、SSH alias、key、host key |
| `/dev/gpiochip*`がない | Ubuntu kernel、`linux-modules-extra`、`modprobe gpio-sim`、runtime deploy |
| `simulation artifact architecture ...` | Sim Host切替後にSIM_RUNTIME／SIM_APPを再build |
| `uuu.exe`がない | Windows PATH、NXP配布package、`Get-Command uuu.exe` |
| UUUがBoardを見つけない | download USB／driver、Serial Downloader mode、cable／電源 |
| serial verificationがtimeout | `target.serial`のCOM、baud、port占有、debug UARTとdownload USBの取り違え |
| `gar usb`が必要に見える | 選択TargetがWindows native UUU／COMかlegacy WSL backendかを確認 |

実装済みと実機検証済みを混同しない。[検証状態](07_VERIFICATION.md)が現在地の正本である。

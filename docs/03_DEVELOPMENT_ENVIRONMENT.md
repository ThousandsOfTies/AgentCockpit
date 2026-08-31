# 開発環境の役割

GARは環境ごとに手順を切り替えず、同じ`gar ...`の背後で実行場所を分ける。
基本構成は次のとおりである。

| 環境 | 役割 | 置かないもの |
|---|---|---|
| Windows host | ユーザー／AIの操作面、workspace／artifact store、USB／COM／UUU | Linux build依存、`gpio_sim` runtime |
| Local Docker | Product build hook、test、Linux tool | 実機USBとserial所有権、恒久的なsimulation state |
| GitHub Codespaces | 固定devcontainerによるcloud BuildEnvironment | physical device access、runtime secret |
| VirtualBox Ubuntu | local Sim Host。Linux device runtimeと`gpio_sim`の実行 | Product build、Windows peripheral tool |
| AWS Ubuntu | remote Sim Host。VirtualBoxと同じruntimeのremote provider | 場当たり的compile／source修正 |
| Physical Target | 配布済みapplicationとreal deviceの実行 | BuildEnvironment、simulation provider |

```text
Human / AI
    │ gar ...
    ▼
Windows host
    ├─ build / test / Linux tools ─► Docker
    ├─ local Linux simulation ───► VirtualBox Ubuntu
    ├─ remote Linux simulation ──► AWS Ubuntu
    └─ flash / console ───────► native USB / COM / UUU
```

## Windowsを操作面にする

Windowsは次を所有する。

- `gar` CLIと`.gar/config.json`
- immutable artifact store
- Docker、VirtualBox、SSH／SCPへのcontrol
- VS Code、browser、Agent Terminal Bridge
- Windowsが直接所有するUSB deviceとCOM port
- NXP `uuu.exe`、Windows ADB、vendor tool

WindowsかLinuxかをユーザーが都度判定しない。たとえばProduct buildはDocker adapter、
NXP full-image flashはUUU adapter、boot logはpyserial adapterが実行場所を固定する。
コマンドはどのhost OSでも`gar target deploy`のままである。

WindowsにSSH serverを立てて同一PC内を往復する構成は取らない。SSHは
VirtualBox／AWS／Physical Targetなど、別OSのruntimeへ到達するtransportとして使う。

## WSLの位置づけ

WSLはGARのcontrol plane、build environment、simulation environmentのいずれでもなく、
必須の構成要素ではない。Docker DesktopがLinux containerを動かす内部実装として
WSL2を使うことはあるが、GARからはDocker Engineというcapabilityだけを見る。

Linux-only USB toolを一時的に使う旧経路ではWSL + usbipdを使える。そのための
`gar usb` commandは互換性のために残すが、Windows native UUU／COMの標準経路では
使わない。

## BuildEnvironment

BuildEnvironmentはProduct hookを実行し、GAR artifact contractへ変換する。

```text
Product source + fixed gar-tools
  → product-*-build.sh
  → staging artifact.json
  → LocalArtifactStore.capture()
```

### Local Docker

`gar config`の`Local Docker`は、Product workspaceを`/workspace`へbind mountし、
Linux container内のBashでProduct hookを実行する。旧`local`設定IDは互換のため残るが、
意味はhost native buildではなくLocal Dockerである。

- 既定image: `gar-build-env:ubuntu-24.04`
- 既定context: `infra/build/`
- workspace内script: `scripts/product-*.sh`
- 必要なProductだけDocker socketをmountできる

Docker socketのmountはhost daemonへの強い権限である。Product hookがDockerを呼ばない場合は
`.gar/config.json`の`build.docker_socket`を`false`にする。imageを固定する場合は
`build.image`を設定する。

Windows DefenderやNTFSの影響を受ける大量の小file処理は、GNU toolをWindowsへ
都度移植するのではなくcontainer内のLinux toolに寄せる。ただしWindows bind mount自体の
I/O性能はProductごとに計測し、大規模buildではCodespaces等も比較する。

### GitHub Codespaces

大きなSDK、cross toolchain、devcontainerで固定した依存が必要なProductはCodespacesを利用する。

```bash
gar code boot --workspace Local/Product
gar code start --workspace Local/Product
gar code status --workspace Local/Product
```

sshfs mountは一時的な視界であり、sourceやartifactの正本ではない。build結果は
GARがartifact storeへsnapshot化する。

## SimulationEnvironmentとSim Host

SimulationEnvironmentはruntimeの種類、Sim Hostはそれruntimeを載せるmachine providerである。
Linux device simulationではこの二つを分ける。

```text
SimulationEnvironment: ssh_remote / Linux systemd runtime
                         │
                         ├─ Sim Host: virtualbox  (local Ubuntu, x86_64既定)
                         └─ Sim Host: aws_ec2     (remote Ubuntu, aarch64既定)
```

VirtualBoxとAWSは別シミュレータではない。共通のSSH／SCP、Ubuntu bootstrap、
Linux systemd runtimeを使い、hostの起動／停止とaddress解決だけをprovider adapterが担う。

VirtualBoxはWSLで使えなかった`gpio_sim`を含むlocal simulationの標準である。
AWSはcloud認証、課金、remote accessが必要な場合のvariantである。

## Physical TargetとWindows native peripheral

Physical TargetはBuildEnvironmentではない。Target固有toolchainはProduct hookとTarget Packが管理し、
実機上の臨時compileを標準手順にしない。

Raspberry Pi OSはSSH／systemd、RK3506 BuildrootはSSH／BusyBox、ESP32はesptool、NXPはUUUと
transportが異なるが、入口は`gar target ...`で統一する。

NXP UUU backendはWindows hostのPATHにある`uuu` / `uuu.exe`をshell経由でなく起動する。
Target Packの`serialVerify`がある場合はpyserialで`COM5`などを開き、起動patternを確認する。
download USBとdebug UARTは別deviceであり、人間が取り違えを防ぐ。

## Machine-localな設定

VM名、IP address、SSH alias、COM port、credential pathはProduct sourceへ埋め込まない。
`.gar/config.json`とOSのSSH configに保存する。例:

```json
{
  "selected_environments": {
    "codespace": "local",
    "simulator": "ssh_remote",
    "simulation_host": "virtualbox",
    "target": "uuu"
  },
  "build": {
    "image": "gar-build-env:ubuntu-24.04",
    "docker_socket": false
  },
  "simulation_host": {
    "provider": "virtualbox",
    "host": "gar-sim-local",
    "arch": "x86_64",
    "private_ip": "192.168.56.10",
    "bridge_port": 8080
  },
  "virtualbox": {
    "vm": "GAR Ubuntu Sim"
  },
  "target": {
    "serial": "COM5"
  }
}
```

`codespace: "local"`は旧schemaとの互換IDで、UIでは`Local Docker`と表示する。
この断片は説明用であり、実際は`gar config`がworkspace entry内へ保存する。

### Workspace設定モデル

`.gar/config.json`の`workspaces`配列が設定の正本である。Target、Build、Simulation、Sim Host、
machine-local接続値はworkspace要素ごとに保存され、別Productの設定と混ざらない。
workspaceの`id`はGARが生成する不変ID、`name`は`--workspace NAME`で指定する表示名である。
connectionは`local`、`codespaces`、`network`のいずれかで、複数登録時はcommandごとに
CWDまたは`--workspace`から対象を解決する。対話設定時に選んだworkspaceを、後続processへ
暗黙のglobal状態として持ち越さない。

```json
{
  "workspaces": [
    {
      "id": "ws_42f8c1",
      "name": "Local/Product",
      "connection": {"type": "local", "path": "C:/Work/Product"},
      "branch": "main",
      "selected_environments": {
        "codespace": "local",
        "simulator": "ssh_remote",
        "simulation_host": "virtualbox",
        "target": "uuu"
      },
      "selected_target": "frdm-imx91s",
      "build": {
        "image": "gar-build-env:ubuntu-24.04",
        "docker_socket": false
      },
      "simulation_host": {
        "provider": "virtualbox",
        "host": "gar-sim-local",
        "arch": "x86_64",
        "repo_dir": "/home/gar/GaplessAgentRuntime",
        "bridge_port": 8080
      },
      "virtualbox": {"vm": "GAR Ubuntu Sim"},
      "target": {"serial": "COM5"}
    }
  ]
}
```

`selected_environments.codespace`は歴史的なkeyで、`local`の現在の意味は`Local Docker`である。
`native`は既存workspace向けのlegacy BuildEnvironmentである。`build.image`の既定値は
`gar-build-env:ubuntu-24.04`、`build.docker_socket`の既定値は`false`である。
Linux device simulationでは`simulator=ssh_remote`と、接続先を表す
`simulation_host=virtualbox|aws_ec2`を独立して保存する。

## 人間が担当する作業

| 環境 | 人間が一度または実行前に行うこと |
|---|---|
| Windows | Python、Docker Desktop、VirtualBox、OpenSSH Client、UUU／USB／UART driverの入手とlicense／UACの承認 |
| Docker | daemonの起動、Product workspaceのfile sharing、socket mount権限の判断 |
| VirtualBox | Ubuntu VM作成、network、SSH key／host key、bootstrap、`gpio_sim`の実確認 |
| AWS | login、region／instance／課金の選択、secretとSSHの登録 |
| Physical Target | Board、配線、電圧、boot mode、USB／COM、書込みstorage、data消去の承認 |

人間が一度選んだmachine-local値は設定へ保存するが、USB／COMは差し直しで
変わり得る。破壊的なflashの直前には再確認する。

## Product workspaceの置き方

Product workspaceはGAR repositoryの外に置き、`sources/`で実装revisionを固定する。

```text
Yurufuwa/
├─ GAR/GaplessAgentRuntime/
├─ GAR/gar-tools/
└─ ProductWorkspace/
   ├─ scripts/
   ├─ hardware/
   ├─ scenarios/
   └─ sources/
```

Windowsがworkspaceを正本として持つ新規構成では、WSL filesystemをWindowsへ
mountするためのjunction／sshfsは不要である。旧WSL workspaceを移行せず参照する場合は
`\\wsl.localhost\...`を一時的に使えるが、新しいGARの階層には含めない。

## 判断基準

- Linux build dependencyはLocal DockerまたはCodespacesへ置く。
- `gpio_sim`とLinux kernel device stateはVirtualBox／AWS Sim Hostへ置く。
- machine-local接続情報は`.gar/config.json`とSSH configへ置く。
- Product behaviorと配線はProductへ置く。
- Board／OS／toolchain／provisioningはTarget Packへ置く。
- Windows固有のUSB／COM処理は`access/`の薄いadapterに閉じる。
- 同じ手操作を繰り返したら、適切なGAR commandまたはrecipeへ収容する。

Windows／Docker Desktop／VirtualBox／NXP実機のE2E確認状態は
[検証状態](07_VERIFICATION.md)を正本とする。

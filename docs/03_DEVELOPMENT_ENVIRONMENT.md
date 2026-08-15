# 開発環境の役割

GARは、すべてを一台へ詰め込まず、環境の役割を固定して同じ`gar`操作面から利用する。

| 環境 | 役割 | 置かないもの |
|---|---|---|
| VS Code + WSL2 | control plane、local build、artifact store、deploy起点 | 恒久的な実機設定の直書き |
| GitHub Codespaces | 再現可能なcloud build | physical deviceアクセス、runtime secret |
| Simulation host | 配布済みapplicationと仮想deviceの実行 | 場当たり的なcompile／source修正 |
| Physical Target | 配布済みapplicationとreal deviceの実行 | BuildEnvironment、simulation provider |
| Windows host | VS Code UI、browser、usbipd、必要なlocal peripheral bridge | GAR domain logic |

## WSL2をcontrol planeにする

WSL2は次を所有する。

- `gar` CLI
- `.gar/config.json`
- immutable artifact store
- SSH config aliasを使ったremote接続
- Codespacesとの接続
- Simulation／Targetへのdeployと診断
- system topologyのorchestration

IP addressやprivate key pathをProduct sourceやartifactへ埋め込まず、SSH config Host名を
machine-local設定として保存する。

## BuildEnvironment

BuildEnvironmentはProduct hookを実行し、GAR artifact contractへ変換する。

```text
Product source + fixed gar-tools
  → product-*-build.sh
  → staging artifact.json
  → WSL LocalArtifactStore.capture()
```

### Local

local toolchainで再現できるProductはWSL上でbuildする。Localであることは「手作業でcompileする」
意味ではなく、Product hookを`LocalBuildEnvironment`が実行するという意味である。

### GitHub Codespaces

大きいSDK、cross toolchain、devcontainerで固定した依存が必要なProductはCodespacesを利用する。

```bash
gar code boot --workspace Local/Product
gar code start --workspace Local/Product
gar code status --workspace Local/Product
```

`gar code start`のsshfs mountは一時的な視界であり、sourceやartifactの正本ではない。
build結果はGARが取得し、WSL側artifact storeへsnapshot化する。

Codespaces上でsourceを直接編集する必要がある場合も、どのrepository／branchが正本かを先に確認する。

## Simulation host

Simulation hostはBuildEnvironmentではない。runtimeとapplicationを実行するだけである。

```bash
gar sim host start --workspace Local/Product
gar sim runtime deploy --workspace Local/Product
gar sim app deploy --workspace Local/Product
gar sim runtime start --workspace Local/Product
gar sim runtime diag --workspace Local/Product --json
```

EC2 GravitonはLinux ARM64 referenceであるが、GARは`ssh_remote`というcapabilityとして扱う。
個別instance名やIPへ依存しない。

Local Docker、Wokwi、MuJoCoはlocal process／containerなので、EC2用port forwardやSSH hostへ
fallbackしない。

## Physical Target

Physical TargetもBuildEnvironmentではない。Target固有toolchainはProduct hookとTarget Packが管理し、
実機上での臨時compileを標準手順にしない。

```bash
gar target prepare --workspace Local/Product
gar target build --workspace Local/Product
gar target preflight --workspace Local/Product --json
gar target deploy --workspace Local/Product
gar target diag --workspace Local/Product --json
```

Raspberry Pi OSはSSH／systemd、RK3506 BuildrootはSSH／BusyBoxという違いがあるが、上位CLIは同じである。
実処理はTarget Packのprovisioning／lifecycle recipeへ委譲する。

## Windowsの役割

Windows nativeは、次のhost capabilityが必要なときだけ使う。

- VS Code integrated terminal
- Edge等のbrowser
- `usbipd-win`によるUSB device共有
- COM portやBluetooth等、WSLから直接扱いにくいlocal peripheral
- Windows側でしか利用できないvendor tool

Windows PowerShell helperへGAR workflowを重複実装しない。Windows固有操作は薄いadapterにし、
状態と結果をWSLのGARへ返す。

## USBとserial

Windowsに接続されたUSB deviceをWSL Target backendから使う場合:

```bash
gar usb list
gar usb attach --busid <busid>
gar usb status
```

ESP32等のserial portはworkspace設定へ保存する。Windowsの`COM3`とLinuxの`/dev/tty*`を
Product codeへ埋め込まず、選択backendが解決する。

Full-image flashでは、USB attachとTargetのrecovery／boot modeは別の状態である。GARは
transport、protocol、対象storage、verifyを区別し、単に「USB-C接続」と表現しない。

## 認証と人間入力

次はbackground processで無理に処理しない。

- cloud login
- sudo password
- GitHub device authentication
- host keyの初回確認
- secret／runner／protected environment登録
- image flash等の不可逆操作

必要な場合、Agent Terminal Bridgeで人間が見えるterminalへ渡し、完了後に元の`gar` commandを再実行する。

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

詳細は[リポジトリ配置](08_REPOSITORY_LAYOUT.md)を参照する。

## 判断基準

- build dependencyの再現性がProductに必要ならCodespaces／devcontainerへ置く。
- 実行中のdeviceやnetwork状態はSimulation／Targetへ置く。
- machine-local接続情報は`.gar/config.json`とSSH configへ置く。
- Product behaviorと配線はProductへ置く。
- Board／OS／toolchain／provisioningはTarget Packへ置く。
- 同じ手操作を繰り返したら、適切なGAR commandまたはrecipeへ収容する。

#!/bin/bash
# Gapless Agent Runtime — simulation host bootstrap
# EC2 初回起動時に user_data として実行される。
# - gpio-sim kernel module が modprobe できる状態にする
# - hardware bridge と診断・ABI 調査ツールを入れる
# アプリ成果物・systemd unit・runtime state は gar sim runtime deploy/start が担当する。

set -eux

apt-get update
apt-get install -y \
  linux-headers-"$(uname -r)" \
  linux-modules-extra-"$(uname -r)" \
  v4l2loopback-dkms \
  v4l2loopback-utils \
  gpiod \
  gir1.2-gstreamer-1.0 \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  python3-aiohttp \
  python3-gi \
  python3-periphery \
  python3-spidev \
  python3-websockets \
  strace

# gpio-sim を事前ロードしてインストール確認（失敗してもブートは止めない）
modprobe gpio-sim || true

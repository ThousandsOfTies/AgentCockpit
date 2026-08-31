#!/bin/bash
# Common Ubuntu bootstrap for local VirtualBox and remote AWS Sim Hosts.
# SIM_RUNTIME/SIM_APP artifacts and systemd units remain owned by `gar sim`.

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

modprobe gpio-sim
install -d -m 0755 /etc/modules-load.d
printf '%s\n' gpio-sim > /etc/modules-load.d/gar-simulation.conf

test -d /sys/kernel/config
mountpoint -q /sys/kernel/config || mount -t configfs configfs /sys/kernel/config

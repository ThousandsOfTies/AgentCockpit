FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GAR_BUILD_SPEC_FINGERPRINT=unknown

LABEL io.gapless-agent-runtime.build-spec=${GAR_BUILD_SPEC_FINGERPRINT}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        cmake \
        curl \
        device-tree-compiler \
        dfu-util \
        docker.io \
        file \
        gcc-aarch64-linux-gnu \
        gcc-arm-linux-gnueabihf \
        gcc-x86-64-linux-gnu \
        git \
        libc6-dev-arm64-cross \
        libc6-dev-armhf-cross \
        libffi-dev \
        libfuse3-dev \
        libssl-dev \
        libusb-1.0-0 \
        make \
        ninja-build \
        nodejs \
        npm \
        openssh-client \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        rsync \
        u-boot-tools \
        unzip \
        wget \
        xz-utils \
        zstd \
    && rm -rf /var/lib/apt/lists/*

# PlatformIO is used by the ESP32/Wokwi products. Keep it in the image so a
# target build does not depend on the Windows host's Python installation.
RUN python3 -m venv /opt/platformio \
    && /opt/platformio/bin/python -m pip install --no-cache-dir --upgrade pip platformio \
    && ln -s /opt/platformio/bin/pio /usr/local/bin/pio

WORKDIR /workspace

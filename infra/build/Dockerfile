FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GAR_BUILD_SPEC_FINGERPRINT=unknown

LABEL io.gapless-agent-runtime.build-spec=${GAR_BUILD_SPEC_FINGERPRINT}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        docker.io \
        file \
        gcc-aarch64-linux-gnu \
        gcc-x86-64-linux-gnu \
        git \
        make \
        python3 \
        python3-venv \
        rsync \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

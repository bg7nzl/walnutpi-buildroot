FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        make \
        git \
        wget \
        curl \
        ca-certificates \
        cpio \
        unzip \
        rsync \
        bc \
        bison \
        flex \
        python3 \
        python3-setuptools \
        python3-dev \
        file \
        libncurses-dev \
        device-tree-compiler \
        u-boot-tools \
        ccache \
        qemu-user-static \
        binfmt-support \
        dosfstools \
        mtools \
        e2fsprogs \
        fdisk \
        gdisk \
        parted \
        xz-utils \
        wget \
        patch \
        bzip2 \
        perl \
        libssl-dev \
        libgnutls28-dev \
        swig \
        python3-pyelftools \
        python3-setuptools \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/buildroot

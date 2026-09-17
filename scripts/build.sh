#!/usr/bin/env bash
# Build the WalnutPi 1B/Zero SD image inside Docker.
# Host: Ubuntu 24.04, 2 cores. Never writes to real disks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FACTORY="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT="${WALNUTPI_WORKSPACE:-$(cd "${FACTORY}/.." && pwd)}"
BR_SRC="${ROOT}/ref/buildroot"
UWE="${ROOT}/ref/uwe5622"
OUT="${ROOT}/output"
BUILD="${ROOT}/build"
IMAGE_NAME="${WALNUTPI_DOCKER_IMAGE:-walnutpi-factory:bookworm}"
JLEVEL="${BR2_JLEVEL:-2}"

if [[ ! -d "${BR_SRC}" ]]; then
	echo "missing ${BR_SRC}" >&2
	exit 1
fi
if [[ ! -d "${UWE}" ]]; then
	echo "missing ${UWE} (Unisoc UWE5622 tree)" >&2
	exit 1
fi

mkdir -p "${OUT}" "${BUILD}"

if ! sudo docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
	sudo docker build -t "${IMAGE_NAME}" "${FACTORY}/docker"
fi

sudo docker run --rm \
	-e HOME=/tmp \
	-e FORCE_UNSAFE_CONFIGURE=1 \
	-e BR2_JLEVEL="${JLEVEL}" \
	-e BR2_CCACHE_DIR=/ccache \
	-e BR2_DL_DIR=/dl \
	-e UWE5622_SRC=/uwe5622 \
	-v "${FACTORY}:/factory:ro" \
	-v "${BR_SRC}:/src/buildroot:ro" \
	-v "${UWE}:/uwe5622:ro" \
	-v "${BUILD}:/build" \
	-v "${OUT}:/output" \
	-v walnutpi-dl:/dl \
	-v walnutpi-ccache:/ccache \
	-w /src/buildroot \
	"${IMAGE_NAME}" \
	bash -lc '
set -euo pipefail
export FORCE_UNSAFE_CONFIGURE=1
make \
	BR2_EXTERNAL=/factory \
	O=/build \
	BR2_JLEVEL="${BR2_JLEVEL}" \
	BR2_CCACHE_DIR=/ccache \
	BR2_DL_DIR=/dl \
	walnutpi_1b_defconfig
# 已展开的内核树不会再走 POST_PATCH；增量构建时补打一次工厂补丁。
if [ -d /build/build/linux-6.12.44 ]; then
	python3 /factory/board/walnutpi-1b/linux/inject-h616.py \
		/build/build/linux-6.12.44 \
		/factory/board/walnutpi-1b/linux
fi
make \
	O=/build \
	BR2_JLEVEL="${BR2_JLEVEL}" \
	BR2_CCACHE_DIR=/ccache \
	BR2_DL_DIR=/dl
img="$(find /build/images -maxdepth 1 -name "*.img" | head -n1)"
if [[ -z "${img}" ]]; then
	echo "no .img in /build/images" >&2
	ls -la /build/images || true
	exit 1
fi
uboot_args=()
if [[ -f /build/images/u-boot-sunxi-with-spl.bin ]]; then
	uboot_args+=(--uboot /build/images/u-boot-sunxi-with-spl.bin)
fi
python3 /factory/scripts/publish-output.py \
	--out /output \
	--img "${img}" \
	--flash /factory/board/walnutpi-1b/FLASH.md \
	"${uboot_args[@]}"
ls -lh /output/walnutpi-1b.img.zip /output/FLASH.md
'

echo "image zip: ${OUT}/walnutpi-1b.img.zip"

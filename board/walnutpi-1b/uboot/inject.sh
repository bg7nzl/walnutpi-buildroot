#!/bin/sh
# Install WalnutPi U-Boot board files into a mainline U-Boot tree.
set -eu
UBOOT_DIR="${1:?u-boot dir}"
HERE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
install -m 0644 "${HERE}/walnutpi_1b_defconfig" \
	"${UBOOT_DIR}/configs/walnutpi_1b_defconfig"
install -m 0644 "${HERE}/sun50i-h616-walnutpi-1b.dts" \
	"${UBOOT_DIR}/dts/upstream/src/arm64/allwinner/sun50i-h616-walnutpi-1b.dts"
DRAM_C="${UBOOT_DIR}/arch/arm/mach-sunxi/dram_sun50i_h616.c"
DRAM_PATCH="${HERE}/../patches/uboot/0001-sunxi-h616-dram-lpddr4-ddr3-auto.patch"
if [ -f "${DRAM_C}" ] && [ -f "${DRAM_PATCH}" ] && \
	! grep -q walnutpi_para_ddr3 "${DRAM_C}"; then
	patch -p1 -d "${UBOOT_DIR}" < "${DRAM_PATCH}"
fi
echo "injected WalnutPi U-Boot board into ${UBOOT_DIR}"

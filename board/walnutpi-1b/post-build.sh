#!/bin/sh
set -eu

BOARD_DIR="$(dirname "$0")"

install -d "${TARGET_DIR}/boot" "${TARGET_DIR}/data"
install -d "${BINARIES_DIR}/data-empty"
sed "s|@DATA_EMPTY@|${BINARIES_DIR}/data-empty|g" \
	"${BOARD_DIR}/genimage.cfg" > "${BINARIES_DIR}/genimage.cfg"

# 40Pin overlays 进 FAT（BINARIES_DIR），不进 squashfs。
DTC="${HOST_DIR}/bin/dtc"
if [ ! -x "$DTC" ]; then
	echo "post-build: missing host dtc at $DTC" >&2
	exit 1
fi
install -d "${BINARIES_DIR}/overlays"
for dts in "${BOARD_DIR}/overlays/"*.dts; do
	[ -f "$dts" ] || continue
	name=$(basename "$dts" .dts)
	"$DTC" -@ -I dts -O dtb -o "${BINARIES_DIR}/overlays/${name}.dtbo" "$dts"
done

CC="${HOST_DIR}/bin/aarch64-buildroot-linux-gnu-gcc"
if [ ! -x "$CC" ]; then
	echo "post-build: missing $CC" >&2
	exit 1
fi
"$CC" -O2 -Wall -o "${TARGET_DIR}/usr/sbin/sprd-hciattach" \
	"${BOARD_DIR}/src/sprd-hciattach.c"
"$CC" -O2 -Wall -o "${TARGET_DIR}/usr/sbin/walnutpi-hex" \
	"${BOARD_DIR}/src/walnutpi-hex.c"

chmod 0755 \
	"${TARGET_DIR}/usr/sbin/overlay" \
	"${TARGET_DIR}/usr/sbin/wifi-setup" \
	"${TARGET_DIR}/usr/sbin/walnutpi-config" \
	"${TARGET_DIR}/usr/sbin/walnutpi-venv" \
	"${TARGET_DIR}/usr/sbin/walnutpi-hex" \
	"${TARGET_DIR}/usr/sbin/sprd-hciattach" \
	"${TARGET_DIR}/etc/init.d/S00data" \
	"${TARGET_DIR}/etc/init.d/S30uwe5622" \
	"${TARGET_DIR}/etc/init.d/S41linklocal" \
	"${TARGET_DIR}/etc/init.d/S45walnutpi-keys" \
	"${TARGET_DIR}/etc/init.d/S50dropbear" \
	"${TARGET_DIR}/etc/init.d/S60wifi" \
	"${TARGET_DIR}/etc/init.d/S99announce"

# 包自带的 S80 / 示例 conf 会在开机前台扫网，去掉。
rm -f "${TARGET_DIR}/etc/init.d/S80wpa_supplicant"
rm -f "${TARGET_DIR}/etc/init.d/S02configfs" \
	"${TARGET_DIR}/etc/init.d/S03overlay"
if [ -f "${TARGET_DIR}/etc/wpa_supplicant.conf" ]; then
	if grep -q 'YOUR_SSID' "${TARGET_DIR}/etc/wpa_supplicant.conf" ||
	   ! grep -q 'ssid=' "${TARGET_DIR}/etc/wpa_supplicant.conf"; then
		rm -f "${TARGET_DIR}/etc/wpa_supplicant.conf"
	fi
fi

# Unisoc WiFi looks for the board ini under /lib/firmware as well as uwe5622/.
if [ -f "${TARGET_DIR}/lib/firmware/uwe5622/wifi_2355b001_1ant.ini" ]; then
	ln -sfn uwe5622/wifi_2355b001_1ant.ini \
		"${TARGET_DIR}/lib/firmware/wifi_2355b001_1ant.ini"
fi
if [ -f "${TARGET_DIR}/lib/firmware/uwe5622/wcnmodem.bin" ]; then
	ln -sfn uwe5622/wcnmodem.bin \
		"${TARGET_DIR}/lib/firmware/wcnmodem.bin"
fi
if [ -f "${TARGET_DIR}/lib/firmware/uwe5622/wcnmodem-38222.bin" ]; then
	ln -sfn uwe5622/wcnmodem-38222.bin \
		"${TARGET_DIR}/lib/firmware/wcnmodem-38222.bin"
fi
# UWE5622 的 NVM 是 ini，不是独立 nvm.bin。
if [ -f "${TARGET_DIR}/lib/firmware/uwe5622/wifi_2355b001_1ant.ini" ]; then
	ln -sfn wifi_2355b001_1ant.ini \
		"${TARGET_DIR}/lib/firmware/uwe5622/nvm.bin"
	ln -sfn uwe5622/wifi_2355b001_1ant.ini \
		"${TARGET_DIR}/lib/firmware/wifi_2355b001_1ant.ini"
fi
# cfg80211 读 /lib/firmware/regulatory.db
if [ ! -f "${TARGET_DIR}/lib/firmware/regulatory.db" ]; then
	echo "post-build: missing regulatory.db (BR2_PACKAGE_WIRELESS_REGDB)" >&2
	exit 1
fi

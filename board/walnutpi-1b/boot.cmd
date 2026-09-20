# WalnutPi hardened：只从 SD p1 读，p3 conf 只导入 overlay_*。
setenv bootargs "root=PARTUUID=b0071b1b-02 rootfstype=squashfs ro rootwait console=ttyS0,115200 console=tty1 earlycon=uart8250,mmio32,0x05000000"

if test -z "${kernel_addr_r}"; then setenv kernel_addr_r 0x40080000; fi
if test -z "${fdt_addr_r}"; then setenv fdt_addr_r 0x4fa00000; fi
if test -z "${fdtoverlay_addr_r}"; then setenv fdtoverlay_addr_r 0x4fc00000; fi
if test -z "${ramdisk_addr_r}"; then setenv ramdisk_addr_r 0x4fe00000; fi

echo "WalnutPi hardened: load Image + DTB from mmc 0:1"
load mmc 0:1 ${kernel_addr_r} Image || reset
load mmc 0:1 ${fdt_addr_r} allwinner/sun50i-h616-walnutpi-1b.dtb || reset
fdt addr ${fdt_addr_r}
fdt resize 16384

setenv overlay_i2c1 0
setenv overlay_i2c2 0
setenv overlay_uart2 0
setenv overlay_uart4 0
setenv overlay_spi1 0
setenv overlay_pwm1 0
setenv overlay_pwm2 0
setenv overlay_pwm12 0
setenv overlay_pwm3 0
setenv overlay_pwm4 0
setenv overlay_pwm34 0

if ext4load mmc 0:3 ${ramdisk_addr_r} walnutpi.conf; then
	echo "import overlay_* from /data/walnutpi.conf"
	env import -t -r ${ramdisk_addr_r} ${filesize} overlay_i2c1 overlay_i2c2 overlay_uart2 overlay_uart4 overlay_spi1 overlay_pwm1 overlay_pwm2 overlay_pwm12 overlay_pwm3 overlay_pwm4 overlay_pwm34
fi

setenv apply_ov 'if test "${ov_en}" = "1"; then echo "fdt apply ${ov_name}"; load mmc 0:1 ${fdtoverlay_addr_r} overlays/${ov_name}.dtbo && fdt apply ${fdtoverlay_addr_r} || echo "overlay ${ov_name} failed"; fi'
setenv ov_name i2c1; setenv ov_en ${overlay_i2c1}; run apply_ov
setenv ov_name i2c2; setenv ov_en ${overlay_i2c2}; run apply_ov
setenv ov_name uart2; setenv ov_en ${overlay_uart2}; run apply_ov
setenv ov_name uart4; setenv ov_en ${overlay_uart4}; run apply_ov
setenv ov_name spi1; setenv ov_en ${overlay_spi1}; run apply_ov
setenv ov_name pwm1; setenv ov_en ${overlay_pwm1}; run apply_ov
setenv ov_name pwm2; setenv ov_en ${overlay_pwm2}; run apply_ov
setenv ov_name pwm12; setenv ov_en ${overlay_pwm12}; run apply_ov
setenv ov_name pwm3; setenv ov_en ${overlay_pwm3}; run apply_ov
setenv ov_name pwm4; setenv ov_en ${overlay_pwm4}; run apply_ov
setenv ov_name pwm34; setenv ov_en ${overlay_pwm34}; run apply_ov

echo "booti squashfs PARTUUID=b0071b1b-02"
booti ${kernel_addr_r} - ${fdt_addr_r}

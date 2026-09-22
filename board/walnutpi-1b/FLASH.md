WalnutPi 1B / Zero 干净 Linux 基线（hardened）
==============================================

串口：UART0 / ttyS0, 115200。默认 root 密码：walnutpi

1B 与 Zero 刷同一张镜像、同一份 DTB：
  FAT `/allwinner/sun50i-h616-walnutpi-1b.dtb`

发布物是 zip（`output/` 里不放裸 .img）：

  unzip walnutpi-1b.img.zip
  sudo dd if=walnutpi-1b.img of=/dev/sdX bs=4M conv=fsync status=progress
  sudo eject /dev/sdX

把 sdX 换成读卡器，不要写宿主机系统盘。

分区
----

MBR 签名 `0xb0071b1b`。U-Boot SPL 在 SD **8KiB**。

| 分区 | 类型 | 内容 |
| --- | --- | --- |
| p1 | FAT 64MiB | Image、DTB、dtbo、boot.scr。只读挂到 `/boot` |
| p2 | squashfs | 根文件系统。内核 `root=PARTUUID=b0071b1b-02`，始终 ro |
| p3 | ext4 标签 `walnutpi-data` | 镜像里 16MiB 空分区；**首次开机扩到卡尾**。挂 `/data` |

p1/p2 刷完后再也不写。U-Boot 不存环境（`ENV_IS_NOWHERE`），不 `saveenv`。
p3 损坏时 **不会自动 mkfs**（避免把半写的用户文件当坏盘格掉）。只可用：

  walnutpi-config reset-data YES

配置
----

唯一持久文件：`/data/walnutpi.conf`。

- 分区在、文件可读且检验通过 → 覆盖默认。
- 分区在、文件不存在 → 写入一份默认方便改。
- 文件坏了 → 留下原文件，写 `/data/walnutpi.conf.err`，本趟用默认。

键：`hostname`、`wifi_ssid`、`wifi_psk`（64 位 hex PSK，不存明文）、
`ssh_authorized_key`、`root_pw_hash`、`overlay_*`、`dropbear_ed25519`（本机生成的
ed25519 主机密钥，十六进制）。改 overlay 后 **reboot**，由 U-Boot `fdt apply`。

  walnutpi-config show
  walnutpi-config set hostname myboard
  wifi-setup 你的SSID 密码
  overlay enable i2c1 && reboot

插卡上电接网线
--------------

1. 串口应出现 U-Boot 然后 Linux。
2. 有 eth0（1B 板载；Zero 需 FPC 扩展板）则后台短试 DHCP，失败再试 169.254/16。
   没网卡、没网线、没 DHCP 都照样出串口登录，不堵开机。
3. 外部 SSH（密码 walnutpi，允许 root）——有地址之后：

       ssh root@walnutpi.local

   或看串口/HDMI 上打印的地址：`ssh root@<eth0>`。
   电脑要能解析 mDNS（Windows 通常可以；Linux 需本机 avahi/resolved）。
   第一次开机在 /data 里生成 **这台板独有** 的 Dropbear 密钥；之后掉电指纹不变。

4. 配 WiFi：

       wifi-setup scan
       wifi-setup 你的SSID 密码

   写入 `/data/walnutpi.conf`，立刻关联，开机也会连。

5. 板载蓝牙（UWE5622）：开机 `S30uwe5622` 会跑 `sprd-hciattach`（展锐 PSKEY/RF，不是裸 H4），并解开 `hci0` 的 rfkill、执行 `hciconfig hci0 up`。

       hciconfig -a          # 应看到 hci0 UP RUNNING
       bluetoothctl scan on

   蓝牙地址从 SID 推（与 eth0 错开最后一字节），每块板唯一。配对信息在 tmpfs，重启即丢。

6. GPIO / 配件（没有官方 set-device）：

       overlay pins
       overlay enable i2c1 && reboot
       overlay enable uart4          # 与 pwm3/4 互斥，需 reboot
       overlay enable spi1 && reboot
       overlay enable pwm12 && reboot
       overlay status
       overlay disable i2c1 && reboot

   40Pin 在 **gpiochip1**（`300b000.pinctrl`，288 线）。gpiochip0 是 R 口 PL，只有 32 线，不是排针。
   例：`gpioset gpiochip1 72=1`（PC8）。`i2cdetect -y 1`。`/dev/spidev1.0`。

7. HDMI 控制台在显示器连上时走 DRM fbcon。LED PC13；按键 PC12。

8. Python 3.12 在只读根上。现场装包必须用 `/data` 里的 venv（Buildroot 没有 ensurepip，不要直接 `python3 -m venv`）：

       walnutpi-venv myapp          # → /data/myapp
       . /data/myapp/bin/activate
       python -m pip install 包名

   纯 Python / 现成 aarch64 wheel 可以；要现场编译的包没有 gcc。整卡 `dd` 会冲掉 p3 上的环境。

40Pin（与 wiki 图一致）
----------------------

 1  3.3V           2  5V
 3  PI8  I2C1 SDA  4  5V
 5  PI7  I2C1 SCL  6  GND
 7  PC8            8  PI5  UART2 TX
 9  GND           10  PI6  UART2 RX
11  PC9           12  PC10
13  PC11          14  GND
15  PI11 PWM1     16  PI12 PWM2
17  3.3V          18  PC14
19  PH7  SPI MOSI 20  GND
21  PH8  SPI MISO 22  PC15
23  PH6  SPI SCLK 24  PH5  SPI CS0
25  GND           26  PH9  SPI CS1
27  PI10 I2C2 SDA 28  PI9  I2C2 SCL
29  PI0           30  GND
31  PI1           32  PI16
33  PI2           34  GND
35  PI3           36  PI15
37  PI4           38  PI13 PWM3 / UART4 TX
39  GND           40  PI14 PWM4 / UART4 RX

gpiochip1 行号 = bank×32+n（PA=0…PI=8）。PC8=72，PI8=264，PH7=231。

本镜像不包含 walnutpi-build / wpi-update / apt.walnutpi.com / set-device。

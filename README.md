# WalnutPi 1B / Zero 镜像工厂

给核桃派 **1B** 与 **Zero**（ZeroW）做可刷 SD 卡的干净 Linux 基线。同一套 SoC、同一张镜像、同一份 DTB。无桌面、无包管理器。

本仓库是 Buildroot 的 `BR2_EXTERNAL`。不包装、不依赖核桃派官方软件栈（`walnutpi-build`、`wpi-update`、`apt.walnutpi.com`、`set-device`）。

刷卡、串口、SSH、WiFi、蓝牙、40Pin：见 [board/walnutpi-1b/FLASH.md](board/walnutpi-1b/FLASH.md)。

## 构建

宿主机要有 **git** 和 **Docker**（`sudo docker`）。Ubuntu 24.04、约 2 核即可。编译进 Debian bookworm 容器，`BR2_JLEVEL=2`。

克隆本仓库后在仓库根目录：

```sh
./make-zip.sh
```

缺的上游会自动 clone（Buildroot `2025.02.6`、[armbian/uwe5622](https://github.com/armbian/uwe5622)），然后编出镜像。第一次会再下内核/U-Boot 等，要较久。

构建都在仓库内的 `workspace/`（已 gitignore）。每次运行会**先删除** `workspace/factory` 再整树拷贝，不用覆盖。`ref/`、`build/`、`output/` 留下做增量。

```
本仓库/
  make-zip.sh
  board/ …
  workspace/                 ← 不入库
    factory/                 ← 每次删掉再拷
    ref/buildroot
    ref/uwe5622
    build/
    output/walnutpi-1b.img.zip
```

产物：`workspace/output/walnutpi-1b.img.zip`（裸 `.img` 不留在 `output/`）。U-Boot SPL 已写在镜像 8KiB 偏移。

```sh
unzip walnutpi-1b.img.zip
sudo dd if=walnutpi-1b.img of=/dev/sdX bs=4M conv=fsync status=progress
```

把 `sdX` 换成读卡器，不要写宿主机系统盘。

## 目录

| 路径 | 用途 |
| --- | --- |
| `configs/walnutpi_1b_defconfig` | Buildroot defconfig |
| `board/walnutpi-1b/` | 板级：DTS、U-Boot、内核补丁、rootfs overlay |
| `board/walnutpi-1b/FLASH.md` | 刷卡与板上用法 |
| `docker/` | 构建容器 |
| `make-zip.sh` | 一键：在 `workspace/` 里出 zip |
| `scripts/build.sh` | Docker 内编译（由 `make-zip.sh` 调用拷贝后的这份） |

栈：ATF `sun50i_h616`、主线 U-Boot、Linux 6.12、BusyBox SysV、Dropbear。有线是 H616 AC300 MDIO EPHY；无线/蓝牙是板载 UWE5622（驱动开源，`wcnmodem.bin` 等为展锐闭源 blob，经 [armbian/firmware](https://github.com/armbian/firmware/tree/master/uwe5622) 再分发，不是 `walnutpi/firmware`）。

## 许可证

未另行标明的源码：**GPL-2.0-or-later**。全文见 [LICENSE](LICENSE)。

已带 `SPDX-License-Identifier` 的文件以文件头为准（DTS 为 `GPL-2.0+ OR MIT`）。

`board/walnutpi-1b/rootfs-overlay/lib/firmware/` 下的固件**不是**本仓库的 GPL 作品，按展锐原条款再分发。来源见该目录的 `SOURCE.txt`。

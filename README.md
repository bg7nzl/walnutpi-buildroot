# WalnutPi 1B / Zero 镜像工厂

给核桃派 **1B** 与 **Zero**（ZeroW）做可刷 SD 卡的干净 Linux 基线。同一套 SoC、同一张镜像、同一份 DTB。无桌面、无包管理器。

分支：

- `main`：单分区 ext4，可读写，适合折腾。
- `hardened`：**不可变设备**。p1 FAT（只读 `/boot`）+ p2 squashfs 根 + p3 `/data`。系统分区刷完后不再写入，U-Boot 不存环境，任意掉电不会把 root/boot 写坏。唯一持久配置是 `/data/walnutpi.conf`（主机名、WiFi、SSH 公钥、root 密码哈希、40Pin overlay、本机生成的 Dropbear 密钥），坏了就回退默认并保留原文件。带 CPython 3.12 / pip；项目用 `walnutpi-venv` 建在 `/data`。
- `full`：`main` + Python 3。

本仓库是 Buildroot 的 `BR2_EXTERNAL`。不包装、不依赖核桃派官方软件栈（`walnutpi-build`、`wpi-update`、`apt.walnutpi.com`、`set-device`）。

刷卡、串口、SSH、WiFi、蓝牙、40Pin：见 [board/walnutpi-1b/FLASH.md](board/walnutpi-1b/FLASH.md)。

相对官方镜像：官方 DTB 绑错 PMIC，CPU 调不了压，常停在约 **1.008 GHz**。本仓库按主线 H616 OPP 和原理图写 DCDC2，可到 **1.512 GHz**。同机对比（算力随频率上去，内存带宽几乎不变）：

| 项 | 修前约 1.008 GHz | 修后 1.512 GHz | 变化 |
| --- | --- | --- | --- |
| sysbench CPU primes | 792.78 ev/s | 1189.42 ev/s | +50.0% |
| stress-ng float | 751.77 bogo/s | 1128.88 bogo/s | +50.2% |
| stress-ng FFT | 477.03 bogo/s | 702.00 bogo/s | +47.2% |
| stress-ng matrix | 691.74 bogo/s | 1186.59 bogo/s | +71.5% |
| 内存带宽 | 529.77 MiB/s | 527.83 MiB/s | 持平 |

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

产物：`workspace/output/walnutpi-1b.img.zip`（裸 `.img` 不留在 `output/`）。U-Boot SPL 已写在镜像 8KiB 偏移。`hardened` 的 MBR 签名 `0xb0071b1b`：FAT boot、squashfs root（`PARTUUID=b0071b1b-02`）、16MiB 空 `walnutpi-data`（首次开机扩到卡尾）。

推到 `main` / `hardened` 会跑 GitHub Actions（`.github/workflows/image.yml`）编同一份 zip，并上传 artifact。第一次全量会很久。

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
| `board/walnutpi-1b/FLASH.md` | 刷卡、分区、`/data/walnutpi.conf`、板上用法 |
| `board/walnutpi-1b/boot.cmd` | U-Boot 引导脚本：读 conf 里的 `overlay_*` 叠 dtbo，`booti` squashfs |
| `board/walnutpi-1b/rootfs-overlay/usr/sbin/walnutpi-config` | conf 检验、原子写、开机落地 |
| `board/walnutpi-1b/rootfs-overlay/usr/sbin/walnutpi-venv` | 在 `/data` 建 venv（无 ensurepip） |
| `docker/` | 构建容器 |
| `make-zip.sh` | 一键：在 `workspace/` 里出 zip |
| `.github/workflows/image.yml` | `main` / `hardened` 推送时编 zip |
| `scripts/build.sh` | Docker 内编译（由 `make-zip.sh` 调用拷贝后的这份） |

栈：ATF `sun50i_h616`、主线 U-Boot、Linux 6.12、BusyBox SysV、Dropbear。有线是 H616 AC300 MDIO EPHY；无线/蓝牙是板载 UWE5622（驱动开源，`wcnmodem.bin` 等为展锐闭源 blob，经 [armbian/firmware](https://github.com/armbian/firmware/tree/master/uwe5622) 再分发，不是 `walnutpi/firmware`）。

## 许可证

未另行标明的源码：**GPL-2.0-or-later**。全文见 [LICENSE](LICENSE)。

已带 `SPDX-License-Identifier` 的文件以文件头为准（DTS 为 `GPL-2.0+ OR MIT`）。

`board/walnutpi-1b/rootfs-overlay/lib/firmware/` 下的固件**不是**本仓库的 GPL 作品，按展锐原条款再分发。来源见该目录的 `SOURCE.txt`。

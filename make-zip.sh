#!/usr/bin/env bash
# 在仓库根目录：./make-zip.sh
# 在 gitignore 的 workspace/ 里搭好 factory + ref + build + output，编出 zip。
# 每次先删掉 workspace/factory 再整树拷贝，不用覆盖。
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="${REPO}/workspace"
SNAP="${WORKSPACE}/factory"
BR_SRC="${WORKSPACE}/ref/buildroot"
UWE="${WORKSPACE}/ref/uwe5622"

BUILDROOT_URL="${BUILDROOT_URL:-https://github.com/buildroot/buildroot.git}"
BUILDROOT_REF="${BUILDROOT_REF:-2025.02.6}"
UWE5622_URL="${UWE5622_URL:-https://github.com/armbian/uwe5622.git}"
UWE5622_REF="${UWE5622_REF:-cc2835a3f935d5297e03cdce464c1785381a7b4d}"

if [[ ! -f "${REPO}/scripts/build.sh" ]] || [[ ! -f "${REPO}/configs/walnutpi_1b_defconfig" ]]; then
	echo "这不是工厂仓库根目录：${REPO}" >&2
	exit 1
fi

if ! command -v git >/dev/null 2>&1; then
	echo "需要 git" >&2
	exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
	echo "需要 Docker（本脚本用 sudo docker）" >&2
	exit 1
fi

mkdir -p "${WORKSPACE}"

expected="$(realpath -m "${REPO}/workspace/factory")"
actual="$(realpath -m "${SNAP}")"
if [[ "${actual}" != "${expected}" ]]; then
	echo "拒绝删除：${SNAP} 不是 ${expected}" >&2
	exit 1
fi

# 必须整目录删掉再拷，不能覆盖：源码里已删的文件否则会留在工作区里继续参与构建。
echo "删除 ${SNAP}"
rm -rf -- "${SNAP}"
if [[ -e "${SNAP}" ]]; then
	echo "未能删除 ${SNAP}" >&2
	exit 1
fi

echo "拷贝仓库 → ${SNAP}"
mkdir -p "${SNAP}"
tar -C "${REPO}" \
	--exclude=./workspace \
	--exclude=./.git \
	-cf - . | tar -C "${SNAP}" -xf -

if [[ ! -f "${SNAP}/scripts/build.sh" ]]; then
	echo "拷贝后缺少 ${SNAP}/scripts/build.sh" >&2
	exit 1
fi

fetch_buildroot() {
	if [[ -f "${BR_SRC}/Makefile" && -f "${BR_SRC}/Config.in" ]]; then
		echo "复用 ${BR_SRC}"
		return
	fi
	if [[ -e "${BR_SRC}" ]]; then
		echo "已存在但不是 Buildroot 源码树：${BR_SRC}" >&2
		exit 1
	fi
	echo "克隆 Buildroot ${BUILDROOT_REF} → ${BR_SRC}"
	mkdir -p "$(dirname "${BR_SRC}")"
	GIT_TERMINAL_PROMPT=0 git clone --depth 1 --branch "${BUILDROOT_REF}" \
		"${BUILDROOT_URL}" "${BR_SRC}"
}

fetch_uwe5622() {
	if [[ -f "${UWE}/Kconfig" && -f "${UWE}/Makefile" ]]; then
		echo "复用 ${UWE}"
		return
	fi
	if [[ -e "${UWE}" ]]; then
		echo "已存在但不是 UWE5622 驱动树：${UWE}" >&2
		exit 1
	fi
	echo "克隆 UWE5622 ${UWE5622_REF} → ${UWE}"
	mkdir -p "$(dirname "${UWE}")"
	GIT_TERMINAL_PROMPT=0 git clone --filter=blob:none --no-checkout \
		"${UWE5622_URL}" "${UWE}"
	git -C "${UWE}" fetch --depth 1 origin "${UWE5622_REF}"
	git -C "${UWE}" checkout --detach FETCH_HEAD
}

fetch_buildroot
fetch_uwe5622

echo "工作区 ${WORKSPACE}"
export WALNUTPI_WORKSPACE="${WORKSPACE}"
exec "${SNAP}/scripts/build.sh"

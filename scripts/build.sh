#!/bin/bash
# 本地构建脚本（v33：SYSVIPC + 完整命名空间 + task_struct 布局修复 + 原厂 CRC 表）
#
# 环境要求：
#   - Linux / WSL
#   - clang-18 工具链（clang / ld.lld / llvm-* 已装入 PATH）
#   - ACK 6.6.77 源码位于 /build/common
#   - 参考 vmlinux 可选：存在则从它生成 CRC 表，缺失时自动使用仓库内 crc_table_stock.txt
#   - 原厂 boot.img 位于 /build/stock/boot.img（打包时使用，可选）
set -e

cd /build/common
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== apply task_struct patch ==="
if grep -q 'SysV IPC per-task state' include/linux/sched.h; then
  echo "sched.h already patched, skip"
else
  git apply --check "$SCRIPT_DIR/../patches/sched-sysvipc-fields-to-end.patch"
  git apply "$SCRIPT_DIR/../patches/sched-sysvipc-fields-to-end.patch"
  echo "patch applied"
fi

echo "=== apply ipc init patch ==="
if grep -q 'device_initcall(ipc_ns_init)' ipc/shm.c; then
  echo "ipc/shm.c already patched, skip"
else
  git apply --check "$SCRIPT_DIR/../patches/ipc-ns-device-initcall.patch"
  git apply "$SCRIPT_DIR/../patches/ipc-ns-device-initcall.patch"
  echo "ipc patch applied"
fi

echo "=== config (SYSVIPC + namespaces) ==="
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 gki_defconfig > /build/defconfig_v33.log 2>&1
./scripts/config --file /build/out-v33/.config \
  -d CONFIG_TRIM_UNUSED_KSYMS \
  --set-str CONFIG_LOCALVERSION "-android15-8-4k" \
  -d CONFIG_MODULE_SIG_PROTECT \
  -e CONFIG_MODULE_ALLOW_MISSING_NAMESPACE_IMPORTS \
  -e CONFIG_PID_NS \
  -e CONFIG_DEVTMPFS \
  -e CONFIG_POSIX_MQUEUE \
  -e CONFIG_IPC_NS \
  -e CONFIG_USER_NS \
  -e CONFIG_SYSVIPC \
  -e CONFIG_SYSVIPC_SYSCTL
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 olddefconfig > /build/olddefconfig_v33.log 2>&1
grep -E 'CONFIG_(SYSVIPC|MODVERSIONS|RANDSTRUCT)' /build/out-v33/.config

echo "=== build Image ==="
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 -j"$(nproc)" Image > /build/build_v33.log 2>&1 || {
  echo "BUILD FAILED"; tail -30 /build/build_v33.log; exit 1; }
echo "BUILD OK"

echo "=== patch CRC table to stock values ==="
if [ -f /build/out-v16/vmlinux ]; then
  echo "using reference vmlinux: /build/out-v16/vmlinux"
  python3 "$SCRIPT_DIR/patch_crc_from_vmlinux.py" \
    /build/out-v16/vmlinux /build/out-v33/vmlinux /build/out-v33/vmlinux_patched
else
  echo "reference vmlinux not found, using committed stock CRC table"
  python3 "$SCRIPT_DIR/patch_crc_table.py" \
    /build/out-v33/vmlinux "$SCRIPT_DIR/crc_table_stock.txt" /build/out-v33/vmlinux_patched
fi
cp /build/out-v33/vmlinux_patched /build/out-v33/vmlinux
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 Image > /build/rebuild_v33.log 2>&1
ls -la /build/out-v33/arch/arm64/boot/Image

echo "=== QEMU module load test (optional) ==="
if [ -f /build/initramfs.cpio.gz ]; then
  timeout 50 qemu-system-aarch64 -M virt -cpu max -m 2G \
    -kernel /build/out-v33/arch/arm64/boot/Image \
    -initrd /build/initramfs.cpio.gz \
    -nographic -no-reboot \
    -append "console=ttyAMA0 loglevel=8 rdinit=/init panic=-1" \
    > /build/qemu_v33.log 2>&1 || true
  grep -E 'finit_module|===|Unknown symbol|version magic|disagrees|module verification|cfg80211|rfkill' /build/qemu_v33.log | head -20
else
  echo "initramfs not found, skip QEMU test"
fi

echo "=== splice boot image ==="
if [ -f /build/stock/boot.img ]; then
  python3 "$SCRIPT_DIR/splice_boot.py" \
    /build/stock/boot.img \
    /build/out-v33/arch/arm64/boot/Image \
    /build/boot_v33_splice.img
  mkdir -p "$SCRIPT_DIR/../images"
  cp /build/boot_v33_splice.img "$SCRIPT_DIR/../images/boot_6.6.77_v33_sysvipc.img"
  md5sum /build/boot_v33_splice.img
else
  echo "stock boot.img not found, skip splice"
fi

echo "DONE"

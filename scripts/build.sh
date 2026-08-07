#!/bin/bash
set -e
cd /build/common

echo "=== move SYSVIPC fields to end of task_struct ==="
if grep -q 'SysV IPC per-task state' include/linux/sched.h; then
  echo "sched.h already patched correctly"
elif grep -q 'Moved to the end of task_struct' include/linux/sched.h; then
  python3 /mnt/c/Users/Administrator/Documents/Codex/2026-08-06/ni-2/work/kbuild_fix_sched_patch.py
else
  python3 - <<'PYEOF'
path = 'include/linux/sched.h'
s = open(path).read()

old_block = '''#ifdef CONFIG_SYSVIPC
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
'''
assert old_block in s, 'mid-struct SYSVIPC block not found'
s = s.replace(old_block, '', 1)

anchor = '''	/*
	 * New fields for task_struct should be added above here, so that
	 * they are included in the randomized portion of task_struct.
	 */
	randomized_struct_fields_end'''
new_block = '''	/*
	 * New fields for task_struct should be added above here, so that
	 * they are included in the randomized portion of task_struct.
	 */
#ifdef CONFIG_SYSVIPC
	/*
	 * SysV IPC per-task state, placed at the end of the randomized
	 * region so every other field keeps the same offset as a
	 * !CONFIG_SYSVIPC build (prebuilt vendor modules depend on it).
	 */
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
	randomized_struct_fields_end'''
assert anchor in s, 'task_struct anchor not found'
s = s.replace(anchor, new_block, 1)
open(path, 'w').write(s)
print('sched.h patched')
PYEOF
fi

echo "=== config (v33: SYSVIPC + task_struct layout preserved) ==="
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

echo "=== build ==="
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 -j12 Image > /build/build_v33.log 2>&1 || { echo "BUILD FAILED"; tail -30 /build/build_v33.log; exit 1; }
echo "BUILD OK"

echo "=== patch CRC table to v16 values ==="
python3 /mnt/c/Users/Administrator/Documents/Codex/2026-08-06/ni-2/work/kbuild_patch_crc2.py \
  /build/out-v16/vmlinux /build/out-v33/vmlinux /build/out-v33/vmlinux_patched
cp /build/out-v33/vmlinux_patched /build/out-v33/vmlinux
make ARCH=arm64 LLVM=1 CROSS_COMPILE=aarch64-linux-gnu- O=/build/out-v33 Image > /build/rebuild_v33.log 2>&1
ls -la /build/out-v33/arch/arm64/boot/Image

echo "=== QEMU module load test ==="
timeout 50 qemu-system-aarch64 -M virt -cpu max -m 2G \
  -kernel /build/out-v33/arch/arm64/boot/Image \
  -initrd /build/initramfs.cpio.gz \
  -nographic -no-reboot \
  -append "console=ttyAMA0 loglevel=8 rdinit=/init panic=-1" \
  > /build/qemu_v33.log 2>&1 || true
grep -E 'finit_module|===|Unknown symbol|version magic|disagrees|module verification|cfg80211|rfkill' /build/qemu_v33.log | head -20

echo "=== splice ==="
python3 - <<'PYEOF'
import struct
stock = '/build/stock/boot.img'
kernel = '/build/out-v33/arch/arm64/boot/Image'
out = '/build/boot_v33_splice.img'
with open(stock, 'rb') as f:
    img = bytearray(f.read())
with open(kernel, 'rb') as f:
    k = f.read()
OFF = 0x1000
AVB0 = 0x22B5000
print('kernel size:', len(k), hex(len(k)))
assert OFF + len(k) < AVB0
img[8:12] = struct.pack('<I', len(k))
img[OFF:OFF+len(k)] = k
with open(out, 'wb') as f:
    f.write(img)
with open(out, 'rb') as f:
    f.seek(AVB0)
    assert f.read(4) == b'AVB0'
print('written:', out)
PYEOF
cp /build/boot_v33_splice.img /mnt/c/Users/Administrator/Documents/Codex/2026-08-06/ni-2/outputs/boot_6.6.77_K90_v33_sysvipc.img
md5sum /build/boot_v33_splice.img

# 红米 K90（annibale）自定义内核

基于 Android Common Kernel（ACK）6.6.77（commit `4a507830d890`）为红米 K90 构建的自定义内核。

## 特性

- **SYSVIPC**（System V IPC：消息队列 / 信号量 / 共享内存）已启用
- 完整命名空间支持：PID / IPC / UTS / Mount / User namespace
- `CONFIG_DEVTMPFS`、`CONFIG_POSIX_MQUEUE`
- 所有原厂预编译内核模块（vendor_dlkm / system_dlkm）正常加载
- WiFi 正常（6.6.77 内核 + 原厂 qca_cld3 驱动）
- 可搭配 KernelSU（FolkSU）获得 root

## 为什么需要修改 task_struct

内核开启 `CONFIG_SYSVIPC` 后，会在 `struct task_struct` 中部插入两个字段：

```c
#ifdef CONFIG_SYSVIPC
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
```

这会改变该结构体后续所有字段的偏移。而本机的厂商驱动模块是按**未开启 SYSVIPC** 的布局编译的，字段一旦错位，驱动访问进程信息就会出错，导致无法开机。

本仓库的补丁把这两个字段移动到 `task_struct` 随机化区域的**末尾**（KABI 预留字段之后），使所有既有字段偏移与原厂一致：

```c
	ANDROID_KABI_RESERVE(1);
	ANDROID_KABI_RESERVE(2);
	ANDROID_KABI_RESERVE(3);
	ANDROID_KABI_RESERVE(4);
#ifdef CONFIG_SYSVIPC
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
	randomized_struct_fields_end
```

另外，开启 SYSVIPC 会改变内核导出符号的版本号（CRC）。由于原厂模块是预编译的，必须把内核的 CRC 表恢复为原厂（v16）的值，模块校验才能正常通过（模块校验本身没有被绕过）。

## 文件说明

```
patches/
  0001-sched-sysvipc-fields-to-end.patch    task_struct 字段移位补丁
scripts/
  kbuild_v33_schedmove.sh                   完整构建脚本（配置 + 编译 + CRC 表修复 + QEMU 验证 + 打包）
  kbuild_patch_crc2.py                      将内核 CRC 表替换为原厂值的工具
images/
  boot_6.6.77_K90_v33_sysvipc.img           最终 boot 镜像（MD5 9faf6bcce6116cc05c7902fc6dc01581）
```

## 刷入方法

```bash
adb reboot bootloader
fastboot flash boot_a boot_6.6.77_K90_v33_sysvipc.img
fastboot reboot
```

> 仅适用于红米 K90（annibale），系统版本 OS3.0.307.0.WPKCNXM，内核 6.6.77。

## 构建方法

环境：WSL（Ubuntu）+ clang-18 交叉编译器，源码为 ACK 6.6.77（`4a507830d890`）。

```bash
cd /build/common
bash /path/to/scripts/kbuild_v33_schedmove.sh
```

脚本会依次完成：打补丁 → 生成配置（SYSVIPC + 命名空间）→ 编译 → 用原厂 CRC 表修复符号版本 → QEMU 验证模块加载 → 生成 boot 镜像。

## 验证结果

- 正常开机进入系统
- `/proc/sysvipc/` 存在 `msg`、`sem`、`shm`
- PID / IPC / User 命名空间可用
- WiFi 连接正常（Wi-Fi 6，2401Mbps）

## 免责声明

刷机有风险，请自行备份数据。自定义内核可能导致保修失效或设备异常，作者不对任何损失负责。

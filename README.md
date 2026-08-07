# 小米 / 红米 6.6.77 内核增强版（SYSVIPC + 完整命名空间）

基于 Android Common Kernel（ACK）6.6.77（commit `4a507830d890`）构建的增强内核，适用于小米 / 红米搭载 **6.6.77 内核**的设备。

> 本项目由 AI 辅助创作，专门适配 **Droidspaces** 等需要命名空间和 System V IPC 的容器环境。

## 已测试设备

| 设备 | 代号 | 系统版本 | 结果 |
| --- | --- | --- | --- |
| 红米 K90 | `annibale` | OS3.0.307.0.WPKCNXM | ✅ 完整验证通过（开机 / WiFi / SYSVIPC / 命名空间） |
| 红米 K80 Pro | - | 6.6.77 内核 | ✅ 测试通过 |

同一内核版本的其它小米 / 红米机型理论上基本可用；如果个别模块加载失败，请参考 [不同机型的适配](#不同机型的适配) 一节。

## 特性

- **SYSVIPC**（System V IPC）：消息队列 / 信号量 / 共享内存
- 完整命名空间：**PID / IPC / UTS / Mount / User namespace**
- `CONFIG_DEVTMPFS`、`CONFIG_POSIX_MQUEUE`
- 保留原厂预编译内核模块兼容性（vendor_dlkm / system_dlkm）：WiFi、相机、音频、传感器等均可正常加载
- 可搭配 **KernelSU / FolkSU** 获得 root（已在 K90 上验证）
- 满足 **Droidspaces** 环境要求

## 内核配置（v33）

```text
CONFIG_SYSVIPC=y
CONFIG_SYSVIPC_SYSCTL=y
CONFIG_SYSVIPC_COMPAT=y
CONFIG_MODVERSIONS=y
CONFIG_RANDSTRUCT_NONE=y
CONFIG_PID_NS=y
CONFIG_IPC_NS=y
CONFIG_USER_NS=y
CONFIG_DEVTMPFS=y
CONFIG_POSIX_MQUEUE=y
CONFIG_MODULE_ALLOW_MISSING_NAMESPACE_IMPORTS=y
```

## 背景：为什么需要这个内核

Android GKI（通用内核）默认关闭了部分命名空间和 System V IPC。以 Droidspaces 的环境检查为例：

```text
[✗] PID namespace      → 需要 CONFIG_PID_NS
[✗] IPC namespace      → 需要 CONFIG_IPC_NS
[✗] User namespace     → 需要 CONFIG_USER_NS（推荐）
[✗] devtmpfs           → 需要 CONFIG_DEVTMPFS
```

直接把 `CONFIG_SYSVIPC` 打开并不能正常工作，会遇到两个隐蔽的坑，下面详细说明。

## 难点一：task_struct 布局变化导致驱动错位

内核开启 `CONFIG_SYSVIPC` 后，`struct task_struct` 中部会多出两个字段：

```c
#ifdef CONFIG_SYSVIPC
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
```

这会**改变该结构体后续所有字段的偏移量**。而厂商的预编译驱动模块是按「未开启 SYSVIPC」的布局编译的，一旦字段错位：

- 驱动读写进程结构时拿到错误的内存位置 → 内存踩踏
- 轻则 WiFi / 相机等驱动异常，重则**卡开机画面或无法开机**

### 解决方案

把这两个字段移动到 `task_struct` 随机化区域的**末尾**（KABI 预留字段之后），使其它所有字段的偏移与原厂完全一致：

```c
	ANDROID_KABI_RESERVE(1);
	ANDROID_KABI_RESERVE(2);
	ANDROID_KABI_RESERVE(3);
	ANDROID_KABI_RESERVE(4);
#ifdef CONFIG_SYSVIPC
	/*
	 * SysV IPC per-task state, placed at the end of the randomized
	 * region so every other field keeps the same offset as a
	 * !CONFIG_SYSVIPC build (prebuilt vendor modules depend on it).
	 */
	struct sysv_sem			sysvsem;
	struct sysv_shm			sysvshm;
#endif
	randomized_struct_fields_end
```

前提条件：内核必须使用 **`CONFIG_RANDSTRUCT_NONE`**（本仓库的配置已满足），字段顺序等于源码顺序，挪动末尾才不会影响既有字段偏移。

## 难点二：符号版本号（CRC）不匹配导致模块被拒

开启 `CONFIG_SYSVIPC` 还会改变内核导出符号的版本号（CRC）。原厂模块是预编译的，它们的 `__versions` 表里记录的是**原厂内核的 CRC**：

```text
# 原厂模块期望的 CRC（以 cfg80211.ko 为例）
device_initialize  crc=0x00a09714
dev_set_name       crc=0x4cdd8744
module_layout      crc=0x4e276f37
```

直接编译的 SYSVIPC 内核生成的 CRC 完全不同（例如 `module_layout` 变成 `0x0d094af1`），模块加载时 `check_modstruct_version()` 失败，返回 `-ENOEXEC`，表现为**开机直接弹回 fastboot**。

### 解决方案

把编译产物的 `__kcrctab` / `__kcrctab_gpl` 表**按符号名逐项替换为原厂（v16）的值**，共 16134 个符号：

```text
module_layout 0x0d094af1 → 0x4e276f37
```

替换后模块校验**正常工作**（不是绕过），所有原厂模块都能通过版本校验并加载。`scripts/kbuild_patch_crc2.py` 实现了这一替换。

> 注意：不同机型 / 不同固件的原厂模块 CRC 可能不同。若在其它机型上遇到「disagrees about version of symbol」提示，需要以该机型可正常开机的内核导出表重新生成 CRC 表。

## 踩坑过程回顾

```text
v13/v16  无 SYSVIPC，所有功能正常（基准版本）
v17~v23  打开 SYSVIPC → module_layout CRC 不匹配 → 全部模块被拒 → fastboot 循环
v29      绕过 module_layout 检查 → 其它符号 CRC 仍不匹配 → 仍失败
v31      绕过全部 CRC 检查 → 模块能加载，但 task_struct 布局错位 → 卡开机
v32      恢复 CRC 表，但 task_struct 布局未修 → 仍无法开机
v33      布局修复 + CRC 表修复（本版本）→ ✅ 正常开机
```

## 文件说明

```text
patches/
  0001-sched-sysvipc-fields-to-end.patch   task_struct 字段移位补丁（核心）
scripts/
  kbuild_v33_schedmove.sh                  v33 完整构建脚本
  kbuild_patch_crc2.py                     CRC 表修复工具（替换为原厂值）
images/
  boot_6.6.77_K90_v33_sysvipc.img          K90 测试通过的 boot 镜像
                                          MD5: 9faf6bcce6116cc05c7902fc6dc01581
```

## 构建方法

### 环境要求

- WSL（Ubuntu）或任意 Linux 环境
- clang-18 交叉编译器（LLVM）
- ACK 6.6.77 源码（commit `4a507830d890`）
- QEMU（用于模块加载验证，可选）

### 构建步骤

```bash
# 1. 进入内核源码
cd /build/common

# 2. 运行完整构建脚本（打补丁 → 配置 → 编译 → CRC 表修复 → QEMU 验证 → 打包）
bash /path/to/scripts/kbuild_v33_schedmove.sh

# 3. 产物
#    /build/out-v33/arch/arm64/boot/Image        内核镜像
#    /build/boot_v33_splice.img                  最终 boot 镜像
```

脚本会自动完成：

1. 应用 `task_struct` 字段移位补丁
2. 以 `gki_defconfig` 为基础生成配置（SYSVIPC + 命名空间 + `LOCALVERSION="-android15-8-4k"`）
3. 编译 `Image`
4. 用 `kbuild_patch_crc2.py` 把 16134 个符号 CRC 替换为原厂值
5. 在 QEMU 中验证 rfkill / cfg80211 等模块可以正常加载
6. 按 boot 镜像布局（kernel 偏移 `0x1000`，保留 `0x22B5000` 处的 AVB 签名块）打包

## 刷机方法

> ⚠️ 刷机有风险，请先备份数据，并确认设备型号与内核版本。

```bash
# 1. 开启 USB 调试，重启到 bootloader
adb reboot bootloader

# 2. 确认设备在线、确认当前槽位
fastboot devices
fastboot getvar current-slot        # 期望输出: current-slot: a

# 3. 刷入内核（以 K90 为例）
fastboot flash boot_a images/boot_6.6.77_K90_v33_sysvipc.img

# 4. 重启
fastboot reboot
```

### 如果刷坏了怎么恢复

```bash
# 重新进入 fastboot（关机状态下长按 电源键 + 音量下键 约 10~15 秒）
fastboot flash boot_a <原厂或已知正常的 boot.img>
fastboot reboot
```

## 验证清单

刷机成功后，建议按以下步骤验证：

```bash
# 1. SYSVIPC 是否生效（应看到 msg / sem / shm）
ls /proc/sysvipc/

# 2. 命名空间是否可用（需要 root）
readlink /proc/self/ns/pid
readlink /proc/self/ns/ipc
readlink /proc/self/ns/user

# 3. WiFi 是否正常
cmd wifi status
dumpsys wifi | grep -m1 "Wifi is connected to"

# 4. root（如果已刷 KernelSU / FolkSU 版）
su -c id

# 5. 运行 Droidspaces 环境检查
```

K90 上的实测结果：

```text
/proc/sysvipc/  → msg, sem, shm ✅
命名空间        → PID / IPC / User 全部存在 ✅
WiFi            → Wi-Fi 6, 2401Mbps, 已连接 ✅
root            → uid=0 (KernelSU/FolkSU) ✅
```

## 获取 root 版本

仓库中的镜像为纯净内核。需要 root 时，可以用 KernelSU / FolkSU 管理器对 `images/` 下的 boot 镜像打补丁，再刷入即可（K90 已实测通过）。

## 不同机型的适配

同一 6.6.77 内核版本的小米 / 红米机型基本可直接使用。如果遇到以下现象：

```text
fastboot 循环 → 模块版本校验失败
```

说明该机型的原厂模块 CRC 与原表不同，需要：

1. 用该机型原厂（或可正常开机的）内核构建出参考 CRC 表
2. 修改 `kbuild_patch_crc2.py` 中的参考路径
3. 重新运行构建脚本生成对应机型的镜像

如果遇到「卡开机画面」，说明存在其它 ABI 差异，建议先抓取 pstore / last_kmsg 日志分析。

## 免责声明

本项目仅供学习研究。刷机可能导致设备变砖、数据丢失或保修失效，请自行评估风险。作者不对任何损失负责。

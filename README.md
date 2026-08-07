# 小米 / 红米 6.6.77 内核（SYSVIPC + 命名空间）

为小米 / 红米 6.6.77 内核设备打造的自定义内核：开启 **SYSVIPC** 与完整命名空间，完全兼容原厂预编译模块，专为 [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) 容器环境适配。

由 AI 辅助创作。

![Build](https://github.com/wanwanQWQ/xiaomi-6.6.77-kernel/actions/workflows/build.yml/badge.svg)

## ✨ 特性

- **SYSVIPC**：System V 消息队列 / 信号量 / 共享内存
- **完整命名空间**：PID / IPC / UTS / Mount / User
- `DEVTMPFS`、`POSIX_MQUEUE`
- **原厂模块全兼容**：WiFi、相机、音频、传感器等驱动正常加载

## 📱 支持设备

| 设备 | 代号 | 系统版本 | 状态 |
| --- | --- | --- | --- |
| 红米 K90 | `annibale` | OS3.0.307.0.WPKCNXM | ✅ 完整验证 |
| 红米 K80 Pro | - | OS3.0.303.0.WPKCNXM | ✅ 测试通过 |

同一 6.6.77 内核版本的小米 / 红米机型基本可用。

## 🚀 下载与刷入

每次云端构建成功后，成品会自动发布到 [Releases](https://github.com/wanwanQWQ/xiaomi-6.6.77-kernel/releases)。

**方式一：fastboot**

下载 `boot_6.6.77_v33_sysvipc.img`（已拼接好，可直接刷入）：

```bash
adb reboot bootloader
fastboot getvar current-slot        # 期望 a
fastboot flash boot_a boot_6.6.77_v33_sysvipc.img
fastboot reboot
```

**方式二：AnyKernel3**

下载 `kernel-6.6.77-ak3.zip`，在 TWRP / OrangeFox / KernelFlasher 中直接刷入（已实测 K90）。

**恢复方法**：长按电源 + 音量下进入 fastboot，刷回原厂 boot.img 即可。

> ⚠️ 刷机有风险，请先备份数据；需要已解锁 Bootloader。

## ⚙️ 技术要点

直接把 `CONFIG_SYSVIPC` 打开并不能正常使用，需要两个关键修复：

### 1. task_struct 布局

SYSVIPC 会在 `struct task_struct` 中部插入两个字段，导致原厂驱动字段错位、无法开机。补丁把字段移到结构体末尾，保持所有原厂字段偏移不变。

### 2. 符号版本号（CRC）

开启 SYSVIPC 会改变内核导出符号的 CRC，原厂预编译模块校验失败（fastboot 循环）。构建流程会把 16134 个符号的 CRC 表替换为原厂值，模块校验正常工作（不绕过）。

## 📁 仓库结构

```text
patches/
  sched-sysvipc-fields-to-end.patch        task_struct 布局补丁
scripts/
  build.sh                                 本地完整构建脚本
  patch_crc_from_vmlinux.py                从参考内核生成/修复 CRC 表
  patch_crc_table.py                       云端构建用 CRC 修复工具
  crc_table_stock.txt                      原厂 CRC 参考表
  splice_boot.py                           Image 与 boot.img 拼接工具
  ak3_anykernel.sh                         AK3 定制配置（自制刷机包参考）
images/
  boot_6.6.77_v33_sysvipc.img              v33 镜像（fastboot 刷入，MD5 9faf6bcce6116cc05c7902fc6dc01581）
  kernel-6.6.77-ak3.zip                    AK3 刷机包（Recovery / KernelFlasher 刷入）
  stock_boot.img                           原厂 boot（供自动拼接，可替换为其它机型）
.github/workflows/build.yml                GitHub Actions 云端构建
```

## 🛠️ 本地构建

环境：Linux / WSL + clang-18 工具链 + ACK 6.6.77 源码（commit `4a507830d890`）。

```bash
cd /build/common
bash /path/to/scripts/build.sh
```

脚本自动完成：打补丁 → 配置 → 编译 → CRC 表修复 → QEMU 模块验证（可选）→ 打包 boot 镜像。

## ✅ 验证清单

```bash
ls /proc/sysvipc/                   # 应看到 msg / sem / shm
readlink /proc/self/ns/pid          # 命名空间
cmd wifi status                     # WiFi 状态
```

K90 实测结果：SYSVIPC ✅ · 命名空间 ✅ · WiFi（Wi-Fi 6，2401Mbps）✅

## ❓ 常见问题

**卡在 fastboot / 模块校验失败**

报错 `disagrees about version of symbol` 说明该机型原厂模块 CRC 与参考表不同。用该机型可正常开机的内核导出表重新生成 CRC 表（修改 `patch_crc_from_vmlinux.py` 的参考路径后重新构建）。

**卡开机画面**

多为 ABI 错位或其它硬件差异，建议抓取 pstore / last_kmsg 日志分析。

**WiFi 异常**

确认原厂 WiFi 驱动模块（vendor_dlkm）未被修改或替换，必要时重新刷入原厂模块分区。

## 🤝 开源致谢

- [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) — 轻量级容器运行时
- [FolkPatch](https://github.com/LyraVoid/FolkPatch) / [KernelSU](https://github.com/tiann/KernelSU) — root 补丁与模块管理生态
- [Android Common Kernel](https://android.googlesource.com/kernel/common/) — 内核源码基础
- [AnyKernel3](https://github.com/osm0sis/AnyKernel3) — AK3 刷机模板
- [KernelFlasher](https://github.com/capntrips/KernelFlasher) — 内核刷写工具
- [LLVM / Clang](https://llvm.org/) — 交叉编译工具链

## 📄 许可证与免责声明

本项目基于 [GPL-2.0](LICENSE) 协议开源（内核本身遵循 GPL-2.0）。

仅供学习研究，刷机可能导致设备变砖、数据丢失或保修失效，请自行评估风险。

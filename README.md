# 小米 / 红米 6.6.77 内核增强版

为小米 / 红米 6.6.77 内核设备打造的增强内核：开启 **SYSVIPC** 与完整命名空间，完全兼容原厂预编译模块，专为 [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) 容器环境适配。

由 AI 辅助创作。

![Build](https://github.com/wanwanQWQ/xiaomi-6.6.77-kernel/actions/workflows/build.yml/badge.svg)

## 📱 已测试设备

| 设备 | 代号 | 系统版本 | 状态 |
| --- | --- | --- | --- |
| 红米 K90 | `annibale` | OS3.0.307.0.WPKCNXM | ✅ 完整验证 |
| 红米 K80 Pro | - | 6.6.77 | ✅ 测试通过 |

同一 6.6.77 内核版本的小米 / 红米机型基本可用。

## ✨ 特性

- **SYSVIPC**：System V 消息队列 / 信号量 / 共享内存
- **完整命名空间**：PID / IPC / UTS / Mount / User
- `DEVTMPFS`、`POSIX_MQUEUE`
- **原厂模块全兼容**：WiFi、相机、音频、传感器等驱动正常加载
- 可搭配 [FolkPatch](https://github.com/LyraVoid/FolkPatch) 补丁获取 root
- 适配 [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS)

## 🚀 快速开始（云端构建）

无需本地环境，GitHub 云端自动完成：拉取源码 → 打补丁 → 配置 → 编译 → CRC 修复 → 模拟器验证。

```text
1. 打开仓库 Actions 页面
2. 选择 Build Kernel → Run workflow
3. 约 1～2 小时后在 Artifacts 下载 kernel-Image-6.6.77
4. 解压得到 Image，拼接原厂 boot.img 后刷入
```

```bash
# 拼接（把 Image 放回原厂 boot 镜像）
python3 scripts/splice_boot.py 原厂boot.img Image boot_custom.img

# 刷入
adb reboot bootloader
fastboot flash boot_a boot_custom.img
fastboot reboot
```

## ⚙️ 关键修复

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
images/
  boot_6.6.77_v33_sysvipc.img              v33 镜像（MD5 9faf6bcce6116cc05c7902fc6dc01581）
.github/workflows/build.yml                GitHub Actions 云端构建
```

## 🛠️ 本地构建

环境：Linux / WSL + clang-18 工具链 + ACK 6.6.77 源码（commit `4a507830d890`）。

```bash
cd /build/common
bash /path/to/scripts/build.sh
```

脚本自动完成：打补丁 → 配置 → 编译 → CRC 表修复 → QEMU 模块验证（可选）→ 打包 boot 镜像。

## 🔑 获取 root

使用 [FolkPatch](https://github.com/LyraVoid/FolkPatch)（基于 KernelPatch 的 Root 管理工具）对 `images/` 下的 boot 镜像打补丁，刷入后即可获得 root（已实测）。

## ✅ 验证清单

```bash
ls /proc/sysvipc/                   # 应看到 msg / sem / shm
readlink /proc/self/ns/pid          # 命名空间（需 root）
cmd wifi status                     # WiFi 状态
su -c id                            # root（已刷 FolkPatch 时）
```

K90 实测结果：SYSVIPC ✅ · 命名空间 ✅ · WiFi（Wi-Fi 6，2401Mbps）✅ · root ✅。

## ⚠️ 其它机型适配

若遇到模块校验失败（`disagrees about version of symbol`），说明该机型原厂模块 CRC 与参考表不同。用该机型可正常开机的内核导出表重新生成 CRC 表（修改 `patch_crc_from_vmlinux.py` 的参考路径后重新构建）。

## 🤝 开源致谢

- [Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) — 轻量级容器运行时（作者 [ravindu644](https://github.com/ravindu644)）
- [FolkPatch](https://github.com/LyraVoid/FolkPatch) — Root 补丁与模块管理工具（作者 [LyraVoid](https://github.com/LyraVoid)）
- [Android Common Kernel](https://android.googlesource.com/kernel/common/)（[GitHub 镜像](https://github.com/aosp-mirror/kernel_common)）— 内核源码基础
- [KernelSU](https://github.com/tiann/KernelSU) / [KernelPatch](https://github.com/bmax121/KernelPatch) — root 生态
- [LLVM / Clang](https://llvm.org/) — 交叉编译工具链
- 所有为 Linux / Android 开源生态做出贡献的开发者

## 📄 免责声明

仅供学习研究，刷机可能导致设备变砖、数据丢失或保修失效，请自行评估风险。

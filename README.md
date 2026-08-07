# 小米 / 红米 6.6.77 内核增强版

基于 Android Common Kernel（ACK）6.6.77（commit `4a507830d890`）构建，开启 **SYSVIPC** 与完整命名空间，兼容原厂预编译模块，适配 **Droidspaces**。

由 AI 辅助创作。

![Build](https://github.com/wanwanQWQ/xiaomi-6.6.77-kernel/actions/workflows/build.yml/badge.svg)

仓库：<https://github.com/wanwanQWQ/xiaomi-6.6.77-kernel>

## 已测试

- 红米 K90（`annibale`）✅
- 红米 K80 Pro ✅

同一 6.6.77 内核版本的小米 / 红米机型基本可用。

## 特性

- SYSVIPC（消息队列 / 信号量 / 共享内存）
- PID / IPC / UTS / Mount / User 命名空间
- DEVTMPFS、POSIX_MQUEUE
- 原厂模块全兼容（WiFi、相机、音频等）
- 可搭配 KernelSU / FolkSU 获取 root

## 关键修复

### 1. task_struct 布局

开启 SYSVIPC 后，内核默认会在 `struct task_struct` 中部插入两个字段，导致原厂驱动访问进程结构时字段错位、无法开机。补丁将这两个字段移到结构体末尾，保持所有原厂字段偏移不变。

### 2. 符号版本号（CRC）

开启 SYSVIPC 会改变内核导出符号的 CRC，原厂预编译模块因此校验失败（fastboot 循环）。构建脚本会把内核 CRC 表逐项替换为原厂值，模块校验正常工作（不绕过）。

## 文件

```text
patches/
  0001-sched-sysvipc-fields-to-end.patch   task_struct 布局补丁
scripts/
  kbuild_v33_schedmove.sh                  完整构建脚本
  kbuild_patch_crc2.py                     CRC 表修复工具
  patch_crc_table.py                       云端构建用 CRC 表修复工具
  crc_table_v16.txt                        原厂 CRC 参考表（16134 个符号）
  splice_boot.py                           把 Image 拼回原厂 boot.img 的工具
images/
  boot_6.6.77_K90_v33_sysvipc.img          K90 镜像（MD5 9faf6bcce6116cc05c7902fc6dc01581）
.github/workflows/build.yml                GitHub Actions 云端构建
```

## 构建

环境：Linux / WSL + clang-18 + ACK 6.6.77 源码。

```bash
cd /build/common
bash /path/to/scripts/kbuild_v33_schedmove.sh
```

脚本自动完成：打补丁 → 配置（SYSVIPC + 命名空间）→ 编译 → CRC 表修复 → QEMU 模块验证 → 打包 boot 镜像。

## GitHub Actions 云端构建

不需要本地环境，直接在 GitHub 云端编译（免费）。构建内容与本地 v33 完全一致：同版本源码（commit `4a507830d890`）→ 同补丁 → 同配置 → 同 CRC 表修复。

1. 打开仓库的 **Actions** 页面
2. 左侧选择 **Build Kernel**，点击 **Run workflow**
3. 等待约 1～2 小时
4. 构建完成后在 **Artifacts** 下载 `kernel-Image-6.6.77`
5. 解压得到 `Image`，用原厂 boot.img 拼接成可刷入的镜像：

```bash
python3 scripts/splice_boot.py 原厂boot.img Image boot_custom.img
```

6. 刷入：

```bash
adb reboot bootloader
fastboot flash boot_a boot_custom.img
fastboot reboot
```

## 刷机

```bash
adb reboot bootloader
fastboot getvar current-slot        # 期望 a
fastboot flash boot_a images/boot_6.6.77_K90_v33_sysvipc.img
fastboot reboot
```

刷坏恢复：长按电源 + 音量下进入 fastboot，重新刷回原厂 boot 即可。

## 验证

```bash
ls /proc/sysvipc/                   # 应看到 msg / sem / shm
readlink /proc/self/ns/pid          # 命名空间（需 root）
cmd wifi status                     # WiFi 正常
```

K90 实测：SYSVIPC ✅、命名空间 ✅、WiFi（Wi-Fi 6）✅、KernelSU root ✅。

## 其它机型适配

若遇到模块校验失败（`disagrees about version of symbol`），用该机型可正常开机的内核导出表重新生成 CRC 表（修改 `kbuild_patch_crc2.py` 中的参考路径后重新构建）。

## 免责声明

仅供学习研究，刷机风险自负。

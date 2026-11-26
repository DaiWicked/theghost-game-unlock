# 分发给别人 —— 每种机器要做什么

## 唯一硬门槛：root

patch 后的壳必须写进**已安装包的私有 lib 目录**：

```
/data/app/com.Gameplier.TheGhost-xxxx/lib/arm64/
```

该目录归 `system:system`、SELinux 上下文 `apk_data_file`，只有 root 能写。

| 对方的机器 | 能用吗 | 走哪条路 |
|---|---|---|
| 有 root（Magisk / KernelSU / APatch）+ 官方版 APK | ✅ | 跑 `deploy.sh`，自动识别为 `official` |
| 有 root + kill shot 版 APK（无卡密） | ✅ | 同一个 `deploy.sh`，自动识别为 `killshot` |
| 没 root | ❌ | 只能重打包 APK 重签名（必须卸载原版，存档有风险） |
| 模拟器（雷电 / MuMu，自带 root） | ✅ | 同上，需 arm64 镜像 |
| 32 位设备 / 非 arm64 | ❌ | 壳只有 arm64-v8a |

---

## 场景 A：有 root + 官方版 APK（最常见）

1. 从自己持有的 APK 里取原始壳并打补丁：

   ```bash
   unzip -p "kill shot.apk" lib/arm64-v8a/libTool.so > libTool.so
   python patches/patch_shell.py libTool.so -o libToolShell.so
   ```

2. 把下列文件放进设备的同一个目录（例如 `/sdcard/killshot/`）：

   ```
   deploy.sh
   libmain.so          ← prebuilt/
   libTool.so          ← prebuilt/
   libToolShell.so     ← 第 1 步产物
   ```

3. 执行：

   ```bash
   su -c "sh /sdcard/killshot/deploy.sh"
   ```

4. 清后台重开游戏 → 直接出现 KILL SHOT 面板，**不用输卡密**。

`deploy.sh` 会自动完成：检查包路径 → 识别版本 → 备份原文件 → 放入 so →
修 `chmod` / `chcon`。幂等，可重复执行。

---

## 场景 B：有 root + kill shot 版 APK（无卡密）

流程完全一样。`deploy.sh` 检测到 `lib/arm64/libTool.so` 是 6 MB 原壳，
自动走 `killshot` 模式，替换目标是 `libTool.so` 而不是 `libmain.so`——
因为 kill shot 版的 dex 里有 `System.loadLibrary("Tool")`，官方版没有。

---

## 场景 C：没 root

写 `/data/app/.../lib/` 必须有 root，绕不过去（Zygisk / LSPosed 本质也是 root）。

只能重打包：

```
底包：kill shot 版 APK（它 dex 里有 loadLibrary("Tool")）
  → 替换 lib/arm64-v8a/libTool.so      为 prebuilt/libTool.so
  → 新增 lib/arm64-v8a/libToolShell.so 为 patch 后的壳
  → zipalign -P 16 -f 4
  → apksigner 用自签证书签
```

代价：签名变了 → 必须先卸载原版 → 本地存档清零（除非有云存档）；
官方更新会覆盖；部分机型会拦自签名包。仓库里提供了 `tools/` 与 patch 脚本，
但**不提供成品 APK**。

---

## 更省事的分发形态：Magisk 模块

让对方敲 `su -c "sh ..."` 不太现实。可以做成模块（Magisk → 从本地安装 → 重启）：

| 做法 | 原理 | 优劣 |
|---|---|---|
| 开机脚本替换 | `post-fs-data.sh` 检测到目标包就把 so 覆盖进它的 `lib/arm64/` | 简单；游戏更新 APK 后需重装模块 |
| Zygisk 注入 | 在游戏进程里经 memfd 传 fd 直接 `dlopen` 壳，完全不碰 APK 文件 | 最干净、不受 `extractNativeLibs` 影响；需 Zygisk 环境 + 写 native 模块 |

（本仓库未内置模块，实现思路见 Zygisk 官方文档。）

---

## 三个技术提醒

**1. 服务端看不到你。** patch 后的壳在建立 `sabi.cc` 连接**之前**就短路了认证分支，
请求根本不会发出，`runtime_id` 不会上传。

**2. 但 payload 仍会连 `wy.llua.cn`。** 内层卡密请求照发（只是判定被改成恒成功）。
想全静默：hosts 里把 `wy.llua.cn` 指向 `127.0.0.1`。

**3. 只对当前壳版本有效。** `libToolShell.so` 对应原始壳 md5
`896cc83f7de4e6b4875bd310cf41f530`。作者换壳后偏移会变，需按
[`docs/01-shell-analysis.md`](../docs/01-shell-analysis.md) 重新定位。

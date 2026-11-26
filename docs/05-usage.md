# 使用手册

三种情况，按你的设备挑一条走。**先在「第 0 步」确认自己属于哪一种。**

---

## 第 0 步：确认设备与版本

```bash
# 1) CPU 架构必须是 arm64-v8a（32 位 / x86 模拟器无效）
adb shell getprop ro.product.cpu.abi

# 2) 包名与安装路径
adb shell pm path com.Gameplier.TheGhost
# 输出形如：
# package:/data/app/~~xxxx==/com.Gameplier.TheGhost-yyyy==/base.apk

# 3) 看 lib 目录里有什么，判断你装的是哪一版
adb shell su -c 'ls -l /data/app/*/com.Gameplier.TheGhost*/lib/arm64/'
```

| lib 目录里的现象 | 你的版本 | 走哪套 |
| --- | --- | --- |
| 有 `libTool.so`（6.19 MB），有 `libmain.so` | **kill shot 版** | 第 2 章 |
| 没有 `libTool.so`，只有 `libmain.so`（6.7 KB） | **官方版** | 第 1 章 |

没有 root 的手机上 `su -c` 会失败，`ls` 也可能读不到 `/data/app/`——这种情况直接看第 3 章。

> 记下第 2 步输出的那个 `~~xxxx==/com.Gameplier.TheGhost-yyyy==` 路径，后面所有操作都在它的
> `lib/arm64/` 子目录里。每次重装/更新 APK，这串随机名都会变。

---

## 第 1 章：有 root + 官方版 APK（推荐）

官方版的 `classes.dex` 里**没有** `System.loadLibrary("Tool")`，所以走 `libmain.so` 这个 Unity 一定会加载的入口。

### 1.1 自动部署

```bash
# 把 killshot 整个目录推到手机
adb push killshot/ /sdcard/killshot/

# 一键部署（脚本自己判断版本，官方版会走 official 分支）
adb shell su -c 'sh /sdcard/killshot/install.sh'

# 重启游戏（脚本不会自动重启，避免杀到正在跑的对局）
adb shell am force-stop com.Gameplier.TheGhost
adb shell am start -n com.Gameplier.TheGhost/com.unity3d.player.UnityPlayerActivity
```

`install.sh` 干的事：把自己复制到 `/data/local/tmp/killshot`（因为 `/sdcard` 不是可执行路径），提权，然后调用 `deploy.sh`。

也可以直接调 `deploy.sh`，带不同参数：

| 命令 | 作用 |
| --- | --- |
| `sh deploy.sh official` | 官方版部署 |
| `sh deploy.sh killshot` | kill shot 版部署 |
| `sh deploy.sh status` | 只查看当前状态，不改文件 |
| `sh deploy.sh restore` | 还原成原始文件 |

### 1.2 手动部署（不跑脚本，一步步来）

在电脑上：

```bash
PKG=com.Gameplier.TheGhost
D=$(adb shell pm path $PKG | head -1 | sed 's|package:||; s|/base.apk||')
echo "目标目录: $D/lib/arm64"

adb push killshot/libmain.so      /data/local/tmp/
adb push killshot/libToolShell.so /data/local/tmp/
```

在手机上或 adb shell 里：

```bash
su
D=/data/app/~~xxxx==/com.Gameplier.TheGhost-yyyy==        # 换成你第 0 步查到的
cd $D/lib/arm64

# ① 先备份原版（这步别跳，这是唯一的回滚保险）
cp libmain.so libmain_orig.so

# ② 用 loader 覆盖 libmain.so
cp /data/local/tmp/libmain.so ./libmain.so

# ③ 放入打过补丁的加固壳
cp /data/local/tmp/libToolShell.so ./libToolShell.so

# ④ 权限与 SELinux 上下文——两步都要做，漏掉第二步会闪退
chmod 755 libmain.so libmain_orig.so libToolShell.so
chcon u:object_r:apk_data_file:s0 libmain.so libmain_orig.so libToolShell.so

ls -lZ   # 确认三个文件都是 rwxr-xr-x + u:object_r:apk_data_file:s0
exit
```

然后用手机上的文件管理器（MT 管理器 / Root Explorer）也可以做 ①②③，但 **④ 的 `chcon` 必须用终端**，
文件管理器改不了 SELinux 标签。手机上装个 Termux 就能执行上面的命令。

最后强停游戏再打开：

```bash
adb shell am force-stop com.Gameplier.TheGhost
adb shell am start -n com.Gameplier.TheGhost/com.unity3d.player.UnityPlayerActivity
```

### 1.3 怎么确认成功了

```bash
adb logcat -d | grep MainLoader
```

正常输出（真机实测）：

```
I MainLoader: forwarding to .../lib/arm64/libmain_orig.so
I MainLoader: libmain_orig JNI_OnLoad -> 0x10006
I MainLoader: loading shell: .../lib/arm64/libToolShell.so
I MainLoader: shell JNI_OnLoad -> 0x10006
I MainLoader: payload module: /memfd:e1ad255a... (deleted) base=0x722fe0d000
I MainLoader: patched 0x723032a49c: 0x540001a1 -> 0x1400016f
```

看到 `patched ... 0x540001a1 -> 0x1400016f` 就代表内层卡密判定已被打掉，**不需要输入任何卡密**。
进游戏主界面后，外挂面板（视觉绘制 / 玩家绘制 / 物品绘制 / 公寓 …）会直接浮在右上区域。

---

## 第 2 章：有 root + kill shot 版 APK

kill shot 版的 `classes.dex` 第一行就是 `System.loadLibrary("Tool")`，入口是 `libTool.so`，不用碰 `libmain.so`。

### 2.1 自动部署

```bash
adb push killshot/ /sdcard/killshot/
adb shell su -c 'sh /sdcard/killshot/install.sh'    # 自动识别，走 killshot 分支
adb shell am force-stop com.Gameplier.TheGhost
```

### 2.2 手动部署

```bash
su
D=/data/app/~~xxxx==/com.Gameplier.TheGhost-yyyy==
cd $D/lib/arm64

cp libTool.so libTool.so.orig          # 备份
cp /data/local/tmp/libTool.so ./libTool.so            # loader 覆盖
cp /data/local/tmp/libToolShell.so ./libToolShell.so  # 补丁壳
chmod 755 libTool.so libTool.so.orig libToolShell.so
chcon u:object_r:apk_data_file:s0 libTool.so libTool.so.orig libToolShell.so
exit
```

日志关键字变成 `ToolLoader`：

```
I ToolLoader: loader constructed
I ToolLoader: loading real shell: .../lib/arm64/libToolShell.so
I ToolLoader: shell JNI_OnLoad -> 0x10006
I ToolLoader: payload module: /memfd:... base=0x709ac80000
I ToolLoader: patched 0x709b19d49c: 0x540001a1 -> 0x1400016f
```

> **两种模式不要混用。** 官方版不要放 `libTool.so`，kill shot 版不要动 `libmain.so`——
> 两个 loader 同时生效会让加固壳被 `JNI_OnLoad` 加载两次，表现是卡死或闪退。

---

## 第 3 章：无 root

`lib/arm64/` 属于 `system:system` + `apk_data_file` 上下文，普通应用没有写权限，**没法免改包**。
唯一的路是把 so 打进 APK 里重新签名。代价：

- 签名变了 → 必须先卸载原版 → **本地存档会清空**（存档在 `/sdcard/Android/data/com.Gameplier.TheGhost/`，卸载前先拷出来）
- 游戏有签名校验的话会直接拒启动（本游戏实测无校验，但更新后可能变）

### 3.1 准备

需要 Android SDK build-tools（`zipalign`、`apksigner`）和 JDK。

```bash
# 生成一个自己的签名密钥（一次性，之后所有版本都用它）
keytool -genkeypair -v -keystore my.keystore -alias ks \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass 123456 -keypass 123456 -dname "CN=test"
```

### 3.2 取出三个 APK

```bash
PKG=com.Gameplier.TheGhost
adb shell pm path $PKG
# package:/data/app/.../base.apk
# package:/data/app/.../split_config.arm64_v8a.apk
# package:/data/app/.../split_UnityDataAssetPack.apk

adb pull /data/app/.../base.apk
adb pull /data/app/.../split_config.arm64_v8a.apk
adb pull /data/app/.../split_UnityDataAssetPack.apk
```

### 3.3 只改 arm64 那个 split

so 都在 `split_config.arm64_v8a.apk` 里。

**官方版：** 把 `lib/arm64-v8a/` 下的 `libmain.so` 换成 loader，并把 `libmain_orig.so`、`libToolShell.so` 一起塞进去。
```bash
mkdir x && cd x && unzip ../split_config.arm64_v8a.apk
cp ../killshot/libmain.so      lib/arm64-v8a/libmain.so
cp ../killshot/libToolShell.so lib/arm64-v8a/
cp <原版libmain.so>            lib/arm64-v8a/libmain_orig.so     # 从原 APK 里取
zip -r ../split_config.arm64_v8a_new.apk . -x '.*'
```

**kill shot 版：**
```bash
cp ../killshot/libTool.so      lib/arm64-v8a/libTool.so
cp ../killshot/libToolShell.so lib/arm64-v8a/
```

`AndroidManifest.xml` 里 `extractNativeLibs` 已经是 true（实测 so 会解压到 lib 目录），不用改。

### 3.4 对齐 + 三个包全部重签

```bash
for f in base split_config.arm64_v8a split_UnityDataAssetPack; do
  zipalign -P 16 -f 4 $f.apk ${f}_al.apk
  apksigner sign --ks my.keystore --ks-pass pass:123456 \
                 --key-pass pass:123456 --out ${f}_signed.apk ${f}_al.apk
done
```

> 三个 split 必须用**同一个** key 签，否则安装时报 `INSTALL_FAILED_INVALID_APK`。

### 3.5 卸载原版 → 装改包

```bash
# 存档先备份（卸载会删 /sdcard/Android/data/<pkg>）
adb pull /sdcard/Android/data/com.Gameplier.TheGhost ./save_backup

adb uninstall com.Gameplier.TheGhost
adb install-multiple base_signed.apk split_config.arm64_v8a_signed.apk split_UnityDataAssetPack_signed.apk
```

装完直接运行，不需要 adb、不需要 frida、不需要 root。

### 3.6 无 root 的替代思路（不改包）

- **模拟器**：雷电 / MuMu / 夜神都有自带 root，直接按第 1、2 章做
- **Magisk 模块**：有 root 就不用这条了；如果你只有临时 root（比如某些一键 root），可以做一个开机脚本
  模块在 `post-fs-data.sh` 里做 `mount --bind` 把改好的 so 挂到目标路径——比直接覆盖更干净，
  但仍然是 root 方案

---

## 第 4 章：还原

```bash
adb shell su -c 'sh /sdcard/killshot/deploy.sh restore'
```

或手动：

```bash
su
D=/data/app/~~xxxx==/com.Gameplier.TheGhost-yyyy==
cd $D/lib/arm64
mv libmain_orig.so libmain.so          # 官方版
# mv libTool.so.orig libTool.so        # kill shot 版
rm -f libToolShell.so
chmod 755 libmain.so
chcon u:object_r:apk_data_file:s0 libmain.so
exit
```

游戏更新 / 重装 APK 之后，`lib/arm64/` 会被重建，所有改动消失，需要重新跑一次部署。

---

## 第 5 章：常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 游戏闪退，logcat 里没有 `MainLoader` | so 没被加载（dex 没触发）或权限/上下文不对 | 确认版本走对了章节；`ls -lZ` 看是不是 `apk_data_file` |
| 闪退，有 `MainLoader` 但停在 `forwarding` | `libmain_orig.so` 缺失或损坏 | 重新从原 APK 提取 `libmain.so` 改名放回 |
| 有 `loading shell` 但没有 `payload module` | 壳 patch 没生效 / 壳文件不对 | 核对 `libToolShell.so` 的 md5 应为 `b8804fce112bf1b701ceb07920a0dca6` |
| 面板出现但功能没效果 | 游戏版本与 payload 不匹配（特征码失效） | 只能等对应的外挂版本；本包只对当前样本有效 |
| 出现"未登录"且点不动 | 内层 patch 没打上 | logcat 搜 `patched ... 0x540001a1`，没有就重跑部署 |
| 部署后游戏变卡/掉帧 | 面板每帧重绘，属正常开销 | 关掉不需要的绘制项 |
| `chcon: Operation not permitted` | 不是真 root（只是 adb root / 用户命名空间） | 需要 Magisk / KernelSU 这类完整 root |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 重签包与原版签名不一致 | 必须先 `adb uninstall` |

---

## 附：文件清单

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `libmain.so` | 8,432 B | 官方版用的转发 loader（导出 `JNI_OnLoad`） |
| `libTool.so` | 8,384 B | kill shot 版用的转发 loader |
| `libToolShell.so` | 6,191,747 B | 打过补丁的加固壳，md5 `b8804fce112bf1b701ceb07920a0dca6` |
| `deploy.sh` | 3.3 KB | 部署/还原/查状态，自动识别版本 |
| `install.sh` | 734 B | 从 `/sdcard` 自复制到 `/data/local/tmp` 再调 `deploy.sh` |
| `loader.c` / `loader_main.c` | — | 两个 loader 的源码，可自行用 NDK 重编 |
| `shot*.png` | — | 真机实测截图（面板与菜单） |

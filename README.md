# TheGhost / kill shot 外挂逆向分析（ChiPROTECT 壳 + 双层卡密）

## ⬇️ 只想用，不想看分析？

**[→ 下载 v1.0.0 部署包](https://github.com/DaiWicked/theghost-game-unlock/releases/latest)**（`killshot.zip` 6.2 MB）

解压后看 **`USAGE.md`**，照你的设备挑一条走：

| 你的情况 | 看哪一节 |
| --- | --- |
| 有 root + 官方版 APK | 第 1 章（自动 `install.sh` 或手动替换 3 个文件） |
| 有 root + kill shot 版 APK | 第 2 章（替换 `libTool.so`） |
| 没有 root | 第 3 章（重签 APK，需先卸载原版） |
| 想还原 | 第 4 章（`deploy.sh restore`） |

仓库内 [docs/05-usage.md](docs/05-usage.md) 是同一份手册的在线版。

---

> 对一个"游戏本体 + 内嵌修改器 + 双层服务端卡密"的样本做完整静态/动态分析，
> 给出可复现的定位方法与最小化补丁（共 3 条指令）。
>
> ⚠️ 本项目仅包含**分析文档、patch 脚本与我们自己写的 loader 源码/编译产物**。
> 不包含任何第三方二进制（原 APK、加固壳、payload dump 均未收录），
> 也不提供破解成品。请自备你合法持有的样本。

---

## 这套东西是什么

样本伪装成《The Ghost》恐怖捉鬼游戏的安装包（`com.Gameplier.TheGhost`），
实际上在游戏里塞了一个自制修改器（UI 品牌名 **kill shot**）。三层结构：

```
┌──────────────────────────────────────────────────────────────────┐
│ ① game APK (993 MB)                                               │
│    classes.dex  ← 唯一改动：UnityPlayerActivity.onCreate()         │
│                   System.loadLibrary("Tool");                     │
├──────────────────────────────────────────────────────────────────┤
│ ② libTool.so  ChiPROTECT 加固壳  6,191,747 B                       │
│    • 节表抹除 / 符号抹除 / 6 MB 密文（熵 8.000）                    │
│    • JNI_OnLoad 状态机，裸 svc 直接系统调用（反 hook）              │
│    • 完整性校验：自身映像大小必须 == 0x5E2000，否则 exit_group(134)  │
│    • ★ 外层卡密：明文 HTTP → www.sabi.cc/api/runtime-gate/…        │
│    • 通过后 ChaCha20 本地解密 → memfd → android_dlopen_ext         │
├──────────────────────────────────────────────────────────────────┤
│ ③ payload  6,168,576 B（解密后）                                   │
│    • 真正的修改器：ImGui + GLES2 自绘 UI                            │
│    • ESP / 透视 / 无限子弹 / 加速 / 传送门 / 各关谜题解密 …          │
│    • ★ 内层卡密：明文 HTTP → wy.llua.cn/api/?id=kmlogon&app=71987  │
│                  响应字段必须 == "10505"                            │
└──────────────────────────────────────────────────────────────────┘
```

## 三条核心发现

| # | 发现 | 意义 |
|---|---|---|
| 1 | **解密密钥全在 `.rodata` 明文里，且不参与认证派生** | 认证只是一道门禁，本地就能解开 payload，不需要服务器点头 |
| 2 | **完整性校验比的是映像总大小 `0x5E2000`，不是内容哈希** | 同长度指令替换可完美通过校验（我们的补丁就是这样） |
| 3 | **两层卡密的成功判定都是单条条件跳转** | 外层 2 条指令、内层 1 条指令即可全部短路 |

## 补丁表（全部改动）

| # | 目标 | 偏移 | 原值 | 改后 | 作用 |
|---|---|---|---|---|---|
| 1 | 加固壳（文件） | `0x5E30EC` | `c0 01 00 34` `cbz` | `1f 20 03 d5` `nop` | 认证失败不自杀 |
| 2 | 加固壳（文件） | `0x5E3114` | `c0 01 00 54` `b.eq` | `0e 00 00 14` `b` | 无条件走"通过"分支 |
| 3 | payload（内存） | `0x51D49C` | `a1 01 00 54` `b.ne` | `6f 01 00 14` `b` | 卡密校验恒成功 |

1、2 由 `patches/patch_shell.py` 一次性完成；3 由 loader 在进程启动时自动完成。

## 快速开始

```bash
# 0) 从你自己持有的 APK 里取出原始壳
unzip -p "kill shot.apk" lib/arm64-v8a/libTool.so > libTool.so

# 1) 打补丁（输出 md5 应为 b8804fce112bf1b701ceb07920a0dca6）
python patches/patch_shell.py libTool.so -o libToolShell.so

# 2) 编译 loader（需要 NDK r21+）
cd loader && ANDROID_NDK_HOME=/path/to/ndk ./build.sh && cd ..

# 3) 部署（需 root，自动识别官方版 / kill shot 版）
adb push deploy /data/local/tmp/killshot/
adb push prebuilt/*.so libToolShell.so /data/local/tmp/killshot/
adb shell su -c "sh /data/local/tmp/killshot/deploy.sh"
adb shell am force-stop com.Gameplier.TheGhost
```

详细步骤见 [`docs/04-deploy-verify.md`](docs/04-deploy-verify.md)。

## 已验证环境

| 项 | 值 |
|---|---|
| 设备 | 三星 SM-G9866（S20 5G） |
| 系统 | Android 10 / arm64-v8a |
| root | Magisk（`uid=0`, `u:r:magisk:s0`） |
| 样本 | kill shot APK，`libTool.so` md5 `896cc83f7de4e6b4875bd310cf41f530` |
| 结果 | 官方版 APK 与 kill shot 版 APK 均验证通过；纯文件替换 + 重启即生效，无需改包重装，无需输入卡密 |

## 目录

```
.
├── docs/
│   ├── 01-shell-analysis.md      加固壳：ELF 结构、svc 表、完整性校验、.rodata 明文协议
│   ├── 02-auth-protocol.md       双层卡密：sabi.cc 与 wy.llua.cn 的完整报文与判定逻辑
│   ├── 03-payload-analysis.md    payload：dump 方法（Frida 17 坑）、功能清单、落盘痕迹
│   └── 04-deploy-verify.md       部署与真机验证、完整补丁表、限制
├── patches/
│   └── patch_shell.py            壳 patch（输入原始 libTool.so，输出 patch 版）
├── loader/
│   ├── loader.c                  libTool.so 转发 loader（kill shot 版 APK 用）
│   ├── loader_main.c             libmain.so 转发 loader（官方版 APK 用）
│   ├── build.sh                  一键编译（无 make 依赖）
│   └── Makefile
├── prebuilt/
│   ├── libmain.so                8,432 B，导出 JNI_OnLoad，仅依赖 libdl/liblog/libc
│   └── libTool.so                8,384 B，同上
├── deploy/
│   ├── deploy.sh                 自动识别版本 / 备份 / 部署 / 还原
│   ├── install.sh                手机端一键入口
│   └── SHARE.md                  分发给不同机型的说明
├── tools/
│   ├── fix_shdr.py               重建被抹除的节表
│   ├── elf_info.py               PHDR / DYNAMIC / 导入导出 / 熵
│   ├── entropy.py                分段熵扫描
│   ├── dex_strdiff.py            dex string_ids 差集（定位注入点）
│   └── frida_dump_payload.js     运行时 dump 解密后的 payload
└── screenshots/
```

## 限制

- 补丁**只对当前壳版本有效**。作者换壳后偏移会变，需按 `docs/01` 的方法重新定位。
- 只有 arm64-v8a。
- 部署需要 root（`/data/app/<pkg>/lib/` 是 `system:system` + `apk_data_file`，非 root 不可写）。
- payload 仍会向 `wy.llua.cn` 发请求（patch 只改判定）；想静默可在 hosts 指到 `127.0.0.1`。

## 声明

本项目用于**逆向工程学习与技术研究**：分析商业加固方案（ChiPROTECT）的实现缺陷、
演示"客户端权威判定"为何不可靠、以及给出相应的检测/加固建议。

- 仓库**不包含**任何第三方二进制：无原 APK、无加固壳、无 payload dump、无全量字符串表。
- `patches/` 是**修改你自己文件的工具**，不是破解成品。
- 请遵守你所在地区的法律与软件许可协议。作者不对任何使用后果负责。
- 如果你是样本作者并希望本项目移除相关内容，请开 issue。

## 参考

- `fix_shdr` 思路：手工重建 SHT，让 `llvm-objdump` 接受无节表的 ELF
- ChaCha20 常量 `expand 32-byte k` + 本地 4×32 B 密钥
- 完整性校验绕过：等长指令替换（`cbz`→`nop`，`b.eq`→`b`）

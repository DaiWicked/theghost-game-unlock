# 01 · 加固壳结构分析

> 样本：`kill shot(MD提示).apk`（993 MB，`com.Gameplier.TheGhost`）
> 目标文件：`lib/arm64-v8a/libTool.so`，6,191,747 B，md5 `896cc83f7de4e6b4875bd310cf41f530`

## 1.1 这套 APK 改了什么

拿官方 TheGhost 1.85.x 安装包（`.apks` 拆分包）逐文件对比，结论很干净：

| 文件 | 官方 md5 | 目标 md5 | 结论 |
|---|---|---|---|
| `libil2cpp.so` | `8acd5870…` | 同 | 未改 |
| `libunity.so` | `ec97edfa…` | 同 | 未改 |
| `libmain.so` | `b4adfa91…` | 同 | 未改 |
| `libAudioPluginDissonance` `lib_burst_generated` `libnative-googlesignin` `libopus` | — | 全同 | 未改 |
| `classes2.dex` | `2f8dd150…` | 同 | 未改 |
| `classes3.dex` | `e8ddf2ab…` | 同 | 未改 |
| **`classes.dex`** | `006b4cf9…` (9,186,388 B) | `6f02d40f…` (9,277,772 B) | **改了 +91 KB** |
| **`libTool.so`** | 不存在 | `896cc83f…` | **新增 6.19 MB** |

dex 字符串池差集（解析 `string_ids` 表）：

- 目标独有：**只有 1 项 —— `Tool`**
- 官方独有：3 项 R8/D8 元数据串（`~~D8{"backend":"dex"...}`）

→ 唯一的 Java 层改动就是 `UnityPlayerActivity.onCreate()` 的第一行：

```java
java.lang.System.loadLibrary("Tool");
```

全包范围内（`global-metadata.dat`、`libil2cpp.so`、全部 dex）搜 `libTool` / `Tool.so` /
`runtime-gate` / `native-authorize` / `ChiPROTECT`，**0 命中**。注入点只有这一处。

## 1.2 ELF 结构：一个"只剩代码"的壳

```
ELF64 AArch64, e_entry = 0, 节表被破坏（4 个假节，e_shoff 指向文件末），符号表已抹除
```

程序头 8 个，真正有内容的 4 个：

| # | 类型 | flags | 文件偏移 | vaddr | filesz | 说明 |
|---|---|---|---|---|---|---|
| 1 | LOAD | R | 0 | 0 | 6,172,672 | **熵 8.000，全密文** |
| 2 | LOAD | RX | 0x5E3000 | 0x5E7000 | 14,704 | **全部真实代码，只有 14 KB** |
| 3 | LOAD | RW | 0x5E6970 | 0x5EE970 | 448 | 数据 |
| 4 | LOAD | RW | 0x5E6B30 | 0x5F2B30 | 4 | 占位 |

- 第 1 段（6 MB 密文）在运行时被 ChaCha20 解密 → 写进 `memfd` → `android_dlopen_ext` 加载
- 第 2 段 vaddr ↔ 文件偏移 **delta = 0x4000**（补丁时要用到）
- `PT_DYNAMIC` 只 3 个导入：`android_dlopen_ext`、`dlsym`、`dladdr`；`NEEDED` 仅 `libdl`/`libc`
- 导出符号只有 `JNI_OnLoad @0x5E7028`（size 36）
- 文件尾有 `ChiPROTECT` 签名标记

节表被破坏导致 `llvm-objdump` 拒绝读取，需要先用脚本重建节表：

```bash
python tools/fix_shdr.py libTool.so libTool_fixed.so
llvm-objdump -d --no-show-raw-insn libTool_fixed.so > shell.dis
```

## 1.3 JNI_OnLoad：状态机 + 裸 syscall

36 字节的 `JNI_OnLoad` 只做一件事：跳进 `0x5E704C` 的状态机，用一个状态字
（`stlr` 写入 `1 / 0x78 / 0x7A / 0x79 / 0x64 / 0x67 / 0x5E`）驱动流程。

**刻意绕过 libc，全部用 `svc` 直接系统调用**（反 hook、反 LD_PRELOAD）：

| x8 | syscall | 用途 |
|---|---|---|
| 278 | `getrandom` | 生成 16 B 随机数 → 32 位 hex 的 `runtime_id` |
| 279 | `memfd_create` | 承载解密后的 payload |
| 25 | `mprotect` | 改段权限 |
| 56 / 63 / 68 / 57 | `openat` / `read` / `pread64` / `close` | 读自身文件做校验 |
| 198 / 206 / 207 | `socket` / `sendto` / `recvfrom` | 走认证接口（明文 HTTP） |
| 203 | `sched_setaffinity` | 反调试（绑核干扰调试器） |
| 113 | `clock_gettime` | 计时 |
| 94 | `exit_group` | **自杀**（完整性校验失败时 `code=134`） |

完整性自校验在 `0x5E710C`：

```asm
sub  x8, x8, #0x5e2000      ; 取自身映像大小
cmp  x8, #0x710             ; 与常量 0x710 比对
b.ne <exit_group(134)>      ; 不符直接死
```

> 注意：校验的是映像总大小 `0x5E2000`，不是文件内容哈希。所以**同段大小的指令替换
> 不会被发现**——这正是我们的补丁能生效的原因。

## 1.4 .rodata 明文区：协议全裸

0x400–0x900 是明文，直接暴露整条认证协议：

```
0x400  "expand 32-byte k"            ← ChaCha20 常量
0x41C  "6701858235600c3a"            ← 8 B hex（密钥材料之一）
0x42C  32 B 二进制 nonce
0x44C  {"runtime_id":"…"artifact_sha256":"…"nonce":"…"|1|1|continu…
0x4D0  "R5FRAG2"                     ← payload 分片容器魔数
0x4D8  "hmac"    0x4DD "build_id"   0x4E6 "issued_at"   0x4F0 "result"
0x538  "runtime_id"    0x548 "nonce"
0x5B0  "POST /api/runtime-gate/native-authorize HTTP/1.1\r\nHost: www.sabi.cc\r\n…"
0x5D2  "failure_action"   0x5E1 "allowed"
0x5E9  "libpubgm.so"                 ← 真正被加载的 payload 名
0x5F5  "policy_version"   0x604 "expires_at"   0x60F "JNI_OnLoad"
0x61A  "artifact_sha256"  0x62A "0123456789abcdef"
0x63B  "6701858235600c3a531fc09e258e517c"
0x64B  "f515600c65cc1f37326c664eff9b8110d29296bdec013e72f3f7560ea429745b"
0x65B  起 SHA-256 / SHA-512 常量表
0x900  起 6 MB 全密文
```

内嵌了完整 SHA-256 / SHA-512 / ChaCha20 实现。

## 1.5 关键结论：密钥与认证解耦

解密函数 `0x5E8A60` 的密钥材料**全部来自本地 `.rodata`**：

```
ldr q0, [x8, #0x430]      ; 32 B
ldr q1, [x8, #0x480]      ; 32 B
ldr q0, [x8, #0x3F0]      ; 32 B
ldr q1, [x8, #0x440]      ; 32 B
+ 0x400 "expand 32-byte k"（ChaCha20 sigma）
+ 0x42C 32 B nonce
```

服务器返回的 `allowed` / `expires_at` / `policy_version` **不参与密钥派生**。
也就是说：认证只是"门禁"，payload 解密是"纯本地操作"。

→ **只要让流程走到解密那一步，离线就能拿到 payload。** 这就是整个绕过方案的立足点。

## 1.6 补丁点

| 位置 | 文件偏移 | 原值 | 改后 | 语义 |
|---|---|---|---|---|
| A | `0x5E30EC` | `c0 01 00 34` `cbz w0, 0x5e7124` | `1f 20 03 d5` `nop` | 认证返回 0（成功）时不再落进失败分支 |
| B | `0x5E3114` | `c0 01 00 54` `b.eq 0x5e714c` | `0e 00 00 14` `b 0x5e714c` | 无条件跳"通过" |

只改 7 字节，段长度不变 → `cmp x8,#0x710` 完整性校验照样通过。

复现：

```bash
python patches/patch_shell.py libTool.so -o libToolShell.so
# 期望输出 md5 b8804fce112bf1b701ceb07920a0dca6
```

## 1.7 分析用的工具

| 脚本 | 作用 |
|---|---|
| `tools/fix_shdr.py` | 重建被抹掉的节表，让 `llvm-objdump` 能读 |
| `tools/elf_info.py` | 打印 PHDR / DYNAMIC / 导入导出 / 熵 |
| `tools/entropy.py` | 分段熵扫描，定位密文区 |
| `tools/dex_strdiff.py` | 解析两个 dex 的 `string_ids` 做差集 |
| `tools/frida_dump_payload.js` | 运行时 dump 解密后的 payload（见 03） |

> 环境备注：`capstone` 在本机装不上（无 MSVC），全程用"重建节表 + llvm-objdump"路线。

# 03 · payload 分析

壳解密出的 6 MB payload 才是外挂本体。这里记录怎么把它 dump 出来、它是什么、能干什么。

## 3.1 怎么 dump

壳把解密结果写进 `memfd`（名字 = 32 位 hex 的 `runtime_id`）再 `android_dlopen_ext` 加载，
所以内存里有一份完整的 ELF。fd 在加载后立刻关闭，只剩映射 → 不能从 `/proc/PID/fd` 捞。

**正确姿势（Frida 17）**：

```python
# tools/frida_dump_payload.js 的核心
Process.enumerateRanges('---')
  .filter(r => r.file && r.file.path.indexOf('/memfd:') >= 0 && r.file.path.indexOf('jit') < 0)
  .sort((a, b) => a.file.offset - b.file.offset)
  .forEach(r => {
      for (let got = 0; got < r.size; got += CHUNK) {
          const n = Math.min(CHUNK, r.size - got);
          send({ off: r.file.offset + got, len: n }, r.base.add(got).readByteArray(n));
      }
  });
```

Python 端收 `send` 回调，`f.seek(off); f.write(data)` 拼文件。

踩过的坑（省得别人再踩）：

| 坑 | 现象 | 正解 |
|---|---|---|
| `new File('/data/local/tmp/x','wb')` | `Error: Permission denied` | frida-server 被 SELinux 拦，改用 `send()` 回传 |
| `Memory.readByteArray(ptr, n)` | `TypeError: not a function` | Frida 17 已删，用实例方法 `ptr.readByteArray(n)` |
| `Module.getExportByName(m, n)` | `TypeError` | 改 `Process.getModuleByName(m).getExportByName(n)` |
| agent 里用 `Java` / `require` | `ReferenceError` | Frida 17 不再内置，只能走纯 native |

产物：6,168,576 B（`0x5E2000`），三段：

| 偏移 | 权限 | 大小 | 内容 |
|---|---|---|---|
| 0 | `r-x` | 6,135,808 | 代码 + rodata |
| 6,131,712 | `r--` | 36,864 | 只读数据 |
| 6,164,480 | `rw-` | 4,096 | 数据 |

## 3.2 ELF 结构

```
ELF64 AArch64, e_type = DYN, 9 个 PHDR
SONAME = libTool.so        ← 注意：payload 自己的 soname 也叫 libTool.so
JNI_OnLoad @ 0x4F2A8C (196 B)
```

- `e_shoff = 0x5E1FD0` 指向文件末端，29 个节表项越界 → `llvm-readelf` 报
  `section header table goes past the end of the file`（壳故意抹的）
- `DT_NEEDED`：`liblog libandroid libEGL libGLESv2 libc libm libdl`
- 重定位极少：`DT_RELA` 0xA8 字节 → **0 条 RELATIVE**，7 条 `GLOB_DAT`，219 条 `JUMP_SLOT`
  → 纯 PIC + PLT
- 导入 226 个，关键：
  `_ZTH12g_crashStage`、`android_set_abort_message`、`dl_iterate_phdr`、
  `fork` / `exec*` / `socket` / `connect` / `sendto` / `getrandom`、
  全套 `glCreateProgram` / `glShaderSource` / `glUniform*`、
  `eglGetCurrentContext` / `eglQuerySurface`

**为什么不能直接 `dlopen` dump 出来的文件**（试过三种修法都失败）：

1. Android linker namespace 只允许 app lib 目录或 `apk!/lib` 路径
2. 补节表 → `has invalid shdr offset/size`
3. 补 `.dynamic` 节 → `abort was called`（payload 内部有 `dl_iterate_phdr` / `dladdr` 自检）

→ 结论：payload 只能由壳加载，不能脱离壳独立运行。

## 3.3 它是什么

**《The Ghost》（恐怖捉鬼游戏）的内置修改器**，不是 PUBG 类。
包名 `com.Gameplier.TheGhost` 就是游戏本身，UI 品牌名 **kill shot**。

技术栈：**ImGui + GLES2 自绘 UI**（字符串里有 `github.com/ocornut/imgui`），
通过 Unity 的 `NativeInputSystem.NotifyUpdate` 接管输入。

日志实证（`Android/data/com.Gameplier.TheGhost/files/tool_log.txt`）：

```
[TUH] Unity bridge class found=UnityPlayer
[TUH] install FAIL method=- sig=- api=29          ← 主 hook 失败，走了降级路径
[TUH] InputSystem hook OK route=NativeInputSystem.NotifyUpdate
[TUH] ImGui render thread drained first input batch events=3 display=800x480
unityScreen=800x480 surface=800x480
```

## 3.4 功能清单

| 分类 | 项目 |
|---|---|
| **ESP** | 玩家绘制、物品绘制、方框、射线、距离、人数、昵称、状态标签、分数、雷达、背敌指示、ESP 大小 / 距离、过滤队友、过滤死人、物品过滤 |
| **地图** | 鬼房绘制（单机可用）、钥匙盒绘制、下水道电闸 ESP、下水道压力表 ESP、保险盒 ESP、温度计绘制（手持）、自身温度计 |
| **玩法** | 无限子弹、无限子弹（万圣节）、人物加速、移速倍率、无碰撞、物品传送门、幽灵传送门、幽灵路径 `ghostPath`、一键获胜、自动记录证据 |
| **画面** | 视角亮度、雾气亮度、关闭雾气、移除动画、移除音效、下雪特效 |
| **解密助手** | 医院密码盒、学校解密、学校谜语、电闸谜语、压力表谜语、公寓异常 |
| **其它** | 各类钥匙名（蓝 / 绿 / 红 / 黄 / 粉 / 紫 / 皇家 / 深处枢纽 / 工具箱 / 笼室 / 储藏室 / 排水室 / 维护 / 模块2 / 模块4 / 下水道阀门…）、Telegram 频道、去广告、获取卡密 |

## 3.5 落盘痕迹

| 路径 | 内容 |
|---|---|
| `Android/data/com.Gameplier.TheGhost/files/mod_config.txt` | 各开关配置 |
| `…/files/wy_card.txt` | 上次输入的卡密 |
| `…/files/tool_log.txt` | 运行日志（hook 状态、UI 尺寸） |
| `/sdcard/.imei` | 设备码缓存（内层卡密 `device` 字段用） |

## 3.6 值得注意的设计

- payload 会 `fork` / `exec*`：可能是反调试探测（读 `/proc/self/status` 的 `TracerPid`）
- `_ZTH12g_crashStage`（thread-safe static init of `g_crashStage`）：崩溃阶段标记，
  用于统计"崩在哪一步"
- `android_set_abort_message`：abort 时给系统日志带自定义信息
- 大量 `glUniform*`：所有 UI 元素都是即时绘制的，没有图片资源，所以 6 MB 全是代码 + 字体

# 02 · 双层卡密协议

这个外挂有两套**互不相关**的卡密系统，都在本地被一条条件跳转决定生死。

```
┌─────────────────────────────────────────────────────────────┐
│ ① 外层：加固壳授权（ChiPROTECT）                              │
│    host : www.sabi.cc                                        │
│    path : /api/runtime-gate/native-authorize                 │
│    作用 : 决定"要不要解密并加载 payload"                      │
│    失败 : exit_group(134) 自杀                                │
├─────────────────────────────────────────────────────────────┤
│ ② 内层：外挂功能授权（payload 自己做）                        │
│    host : wy.llua.cn                                         │
│    path : /api/?id=kmlogon&app=71987                         │
│    作用 : 决定"UI 要不要解锁功能"                             │
│    成败 : 响应字段 == "10505"                                 │
└─────────────────────────────────────────────────────────────┘
```

两个都是**明文 HTTP**，没有 TLS。

---

## 2.1 外层：sabi.cc runtime-gate

### 请求

```
POST /api/runtime-gate/native-authorize HTTP/1.1
Host: www.sabi.cc
Connection: close
Content-Type: application/json
Content-Length: <len>

{"runtime_id":"<32 hex>","nonce":"<hex>","artifact_sha256":"<hex>",
 "build_id":"…","issued_at":…,"hmac":"…","policy_version":…}
```

- `runtime_id`：`getrandom(16)` 转 32 位 hex，同时也是 `memfd` 的名字
  （`/memfd:1a12873a6e99c987922ea6c785d73e7a`）
- `artifact_sha256`：对自身映像做 SHA-256
- `hmac`：用 `.rodata` 里的 `6701858235600c3a` / `531fc09e258e517c` 等材料算

### 响应

```json
{"allowed": true, "expires_at": 1234567890, "policy_version": 1,
 "result": "…", "failure_action": "continue"}
```

### 判定逻辑（实证）

`0x5E74A0` 处的响应解析：

1. `0x5E7F94 bl 0x5E9C2C` —— 字段提取，字段名 `failure_action`（缓冲区 512 B）
2. `0x5E7FAC` —— 值的长度必须 `== 9`
3. `0x5E7FB8`–`0x5E7FD0` —— 前 8 字节与常量 `0x6f63/0x746e/0x6e69/0x6575` 比较
   → 必须是 ASCII **`"continue"`**

所以只要 `failure_action == "continue"`，壳就认为"继续"，直接解密 payload。
另有两处常量比对在 `sp+0x41C`、`sp+0x26FE`。

### 破解方式

不需要伪造服务器。两条指令让流程无条件走到"通过"，见
[`patches/patch_shell.py`](../patches/patch_shell.py) 与
[01-shell-analysis.md §1.6](01-shell-analysis.md)。

> 顺带：`work/kill/fake_gate.py` 里也留了一个本地 HTTP 200 伪造服务端，
> 用于验证"如果只想骗过联网检查该返回什么"。实际不需要，patch 更干净。

---

## 2.2 内层：wy.llua.cn 卡密登录

payload 自己实现了一套独立的卡密系统，跟壳完全无关。

### 请求构造（`0x51BD9C`）

```
host = "wy.llua." + "cn"                    ; 0x52EF 处 8 B + 立即数 0x6e63
line = "api/?id=kmlogon&app=71987"          ; 25 B，从 0x52FA / 0x52F2 拼

socket(AF_INET, SOCK_STREAM, 0)             ; 0x5D9790
SO_RCVTIMEO / SO_SNDTIMEO = 12 s            ; timeval 在 0x4AF0
```

完整报文：

```
POST /api/?id=kmlogon&app=71987 HTTP/1.1
Host: wy.llua.cn
Content-Type: application/x-www-form-urlencoded
User-Agent: Mozilla/4.0(compatible)
```

请求体字段（从字符串引用点推出）：`<card>`（卡密）、`<device>`（设备码 / IMEI）、
`TokenTrigger`、`code:k7:token`。

### 成功判定（`0x51D484`–`0x51D4CC`）

```asm
; 取响应字段（std::string，tst w9,#1 判是否 SSO）
cmp   x10, #5                     ; 长度必须 == 5
mov   w12, #0x3035
movk  w12, #0x3031, lsl #16       ; 拼出 "1050"
ldrb  w8,  [x8, #4]
cmp   w8,  #0x35                  ; '5'
b.eq  0x51DA58                    ; → 成功分支
b.ne  0x51D4D0                    ; → 失败分支（UI 显示 验证失败(code=…)
```

→ 响应字段必须精确等于 **`"10505"`**。

### 破解方式

把 `base+0x51D49C` 的 `b.ne` 改成无条件 `b`：

| 偏移 | 原值 | 改后 |
|---|---|---|
| `0x51D49C`（payload 内存） | `a1 01 00 54` `b.ne` | `6f 01 00 14` `b 0x51DA58` |

这就是 loader 在运行时干的事（见 [`loader/loader.c`](../loader/loader.c)）：

```c
uint8_t *p = (uint8_t *)(base + 0x51d49c);
mprotect(page, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC);
uint32_t insn = 0x1400016F;   /* b 0x51da58 */
memcpy(p, &insn, 4);
```

### 副作用

- 判定被短路后，UI 直接进功能菜单，**不需要输入任何卡密**。
- payload 仍会照常发出那次 HTTP 请求（patch 只改判定不改网络），日志里能看到
  `POST /api/?id=kmlogon | 等待服务器返回...`。想完全静默就在 hosts 里把
  `wy.llua.cn` 指到 `127.0.0.1`。
- 存档目录会缓存上次输入的卡密（`wy_card.txt`），即使不 patch 也可能"记住"上次成功。

---

## 2.3 一句话总结

| 层 | 服务端权威？ | 本地能否绕过 | 绕过代价 |
|---|---|---|---|
| 外层 sabi.cc | 名义上是，但密钥不参与认证 | ✅ 能 | 2 条指令（nop + b） |
| 内层 wy.llua.cn | 名义上是，判定是纯字符串比较 | ✅ 能 | 1 条指令（b.ne → b） |

壳写得挺讲究（裸 `svc`、抹符号、自杀式完整性校验、状态机），
但协议模板、密钥、nonce 全在 `.rodata` 明文里 —— 等于把钥匙挂在门上。

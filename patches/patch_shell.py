#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_shell.py —— 给 ChiPROTECT 加固壳 libTool.so 打补丁，跳过服务端卡密认证。

原理
----
壳的 JNI_OnLoad 会先向 http://www.sabi.cc/api/runtime-gate/native-authorize
提交 {runtime_id, nonce, artifact_sha256, hmac} 做二次授权，服务端回
{"allowed":..., "failure_action":"continue"} 才继续解密 payload。

两处分支决定生死：
  A) 认证调用返回后 cbz w0, fail      —— 返回 0（成功）时跳过 fail
  B) 校验 .rodata 字符串失败则 b.eq    —— 应改为无条件跳"通过"

补丁把 A 改成 nop、B 改成无条件 b，认证被短路，壳直接用本地 ChaCha20
密钥解密内嵌的 6 MB payload。密钥不参与认证，所以本地不需要服务器点头。

用法
----
    python patch_shell.py <原始 libTool.so> [-o 输出路径]

    例：python patch_shell.py libTool.so -o libToolShell.so

支持的版本
----------
    原始 md5  896cc83f7de4e6b4875bd310cf41f530  (6,191,747 B)
    输出 md5  b8804fce112bf1b701ceb07920a0dca6

其他版本会报偏移不匹配，此时需用 tools/elf_info.py + llvm-objdump 重新定位
（方法见 docs/01-shell-analysis.md）。
"""

import argparse
import hashlib
import os
import sys

# (文件偏移, 原始 4 字节, 补丁后 4 字节, 说明)
PATCHES = [
    (0x5E30EC, b"\xc0\x01\x00\x34", b"\x1f\x20\x03\xd5",
     "cbz w0, fail  ->  nop      (认证返回值不再触发失败分支)"),
    (0x5E3114, b"\xc0\x01\x00\x54", b"\x0e\x00\x00\x14",
     "b.eq  fail    ->  b  pass  (无条件跳，直接进入解密流程)"),
]

KNOWN_MD5 = "896cc83f7de4e6b4875bd310cf41f530"
EXPECTED_OUT_MD5 = "b8804fce112bf1b701ceb07920a0dca6"


def md5_of(data):
    return hashlib.md5(bytes(data)).hexdigest()


def main():
    ap = argparse.ArgumentParser(
        description="patch ChiPROTECT shell (libTool.so) to skip server-side license auth")
    ap.add_argument("input", help="原始 libTool.so（从 APK 的 lib/arm64-v8a/ 提取）")
    ap.add_argument("-o", "--output", help="输出路径，默认 <input>.patched.so")
    ap.add_argument("--force", action="store_true", help="md5 不匹配也按偏移尝试打补丁")
    args = ap.parse_args()

    src = args.input
    if not os.path.isfile(src):
        print("[!] 找不到文件: %s" % src)
        return 1

    with open(src, "rb") as f:
        data = bytearray(f.read())

    print("[*] input : %s (%d bytes)" % (src, len(data)))
    in_md5 = md5_of(data)
    print("[*] md5   : %s" % in_md5)

    if in_md5 != KNOWN_MD5:
        print("[!] 不是已知版本（期望 %s）" % KNOWN_MD5)
        if not args.force:
            print("[!] 偏移可能不同，已中止。确认要试请加 --force")
            return 2

    changed = 0
    for off, old, new, desc in PATCHES:
        if off + 4 > len(data):
            print("[!] 偏移 0x%x 超出文件长度" % off)
            return 3
        cur = bytes(data[off:off + 4])
        if cur == new:
            print("[=] 0x%06x 已是补丁状态，跳过" % off)
            continue
        if cur != old:
            print("[!] 0x%06x 期望 %s 实际 %s（版本不符）"
                  % (off, old.hex(), cur.hex()))
            if not args.force:
                return 4
        data[off:off + 4] = new
        changed += 1
        print("[+] 0x%06x  %s -> %s   %s" % (off, old.hex(), new.hex(), desc))

    out = args.output or (src + ".patched.so")
    with open(out, "wb") as f:
        f.write(data)

    out_md5 = md5_of(data)
    print("[*] output: %s (%d bytes)" % (out, len(data)))
    print("[*] md5   : %s" % out_md5)
    if changed and out_md5 == EXPECTED_OUT_MD5:
        print("[OK] 与已知补丁产物一致")
    print("[*] 部署名建议: libToolShell.so（放进 <包名>/lib/arm64/，见 deploy/SHARE.md）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用法: python dex_strdiff.py <a.dex> <b.dex>
# 作用: 解析两个 dex 的 string_ids 表做差集，用来定位注入点。
import struct, sys

def read_uleb(d, o):
    r = 0
    s = 0
    while True:
        b = d[o]
        o += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80):
            break
        s += 7
    return r, o

def dex_strings(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'dex\n'
    n, off = struct.unpack_from('<II', d, 0x38 + 4)  # 0x3C? careful
    str_size, str_off = struct.unpack_from('<II', d, 0x38)
    # dex header: 0x38 = string_ids_size, 0x3C = string_ids_off
    str_size, str_off = struct.unpack_from('<II', d, 0x38)
    out = []
    for i in range(str_size):
        so = struct.unpack_from('<I', d, str_off + i * 4)[0]
        ln, p = read_uleb(d, so)
        # utf8 string, may be MUTF-8
        e = d.index(b'\x00', p)
        out.append(d[p:e].decode('utf-8', 'replace'))
    return out

a = dex_strings(sys.argv[1])
b = dex_strings(sys.argv[2])
sa, sb = set(a), set(b)
print("A(orig)=%d B(new)=%d" % (len(sa), len(sb)))
only = sorted(sb - sa)
print("\n=== only in NEW (%d) ===" % len(only))
for s in only:
    print(repr(s)[:300])
cnt = 0
print("\n=== only in ORIG (%d) ===" % len(sa - sb))
for s in sorted(sa - sb)[:40]:
    print(repr(s)[:200])

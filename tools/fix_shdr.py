#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用法: python fix_shdr.py <输入.so> <输出.so>
# 作用: 加固壳的节表被抹除，llvm-objdump 拒绝读取；本脚本按 PHDR 重建最小可用 SHT。
import struct, sys, os

src = sys.argv[1]
dst = sys.argv[2]
d = bytearray(open(src, 'rb').read())

e_phoff = struct.unpack_from('<Q', d, 0x20)[0]
e_phentsize = struct.unpack_from('<H', d, 0x36)[0]
e_phnum = struct.unpack_from('<H', d, 0x38)[0]

loads = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    p_type, p_flags, p_off, p_va, p_pa, p_fsz, p_msz, p_al = struct.unpack_from('<IIQQQQQQ', d, o)
    if p_type == 1:
        loads.append((p_flags, p_off, p_va, p_fsz))

# build section headers: null, .text(exec load), .data(other load), .shstrtab
shstr = b'\x00.text\x00.data\x00.shstrtab\x00'
shstr_off = len(d)
d += shstr

secs = [bytes(64)]  # null
def add(name_off, typ, flags, addr, off, size, align=16):
    secs.append(struct.pack('<IIQQQQIIQQ', name_off, typ, flags, addr, off, size, 0, 0, align, 0))

for flags, off, va, fsz in loads:
    if flags & 1:  # X
        add(0x01, 1, 0x6, va, off, fsz)
    else:
        add(0x07, 1, 0x2, va, off, fsz)  # PROGBITS ALLOC
add(0x0d, 3, 0, 0, shstr_off, len(shstr), 1)  # shstrtab

while len(d) % 8:
    d += b'\x00'
shoff = len(d)
for s in secs:
    d += s
struct.pack_into('<Q', d, 0x28, shoff)
struct.pack_into('<H', d, 0x3C, len(secs))
struct.pack_into('<H', d, 0x3E, len(secs) - 1)
open(dst, 'wb').write(bytes(d))
print("wrote", dst, "shoff", hex(shoff), "sections", len(secs))
print("loads", [(hex(f), hex(o), hex(v), z) for f, o, v, z in loads])

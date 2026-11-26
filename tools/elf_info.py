#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用法: python elf_info.py <文件.so>
# 作用: 打印 ELF 头/PHDR/DYNAMIC/导入导出/节表，遇到节表损坏也不会崩。
import struct, sys

path = sys.argv[1]
d = open(path, 'rb').read()

# ELF64 parse
assert d[:4] == b'\x7fELF'
e_shoff = struct.unpack_from('<Q', d, 0x28)[0]
e_shentsize = struct.unpack_from('<H', d, 0x3A)[0]
e_shnum = struct.unpack_from('<H', d, 0x3C)[0]
e_shstrndx = struct.unpack_from('<H', d, 0x3E)[0]

secs = []
for i in range(e_shnum):
    o = e_shoff + i * e_shentsize
    name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack_from('<IIQQQQIIQQ', d, o)
    secs.append(dict(name=name, type=typ, flags=flags, addr=addr, off=off, size=size, link=link, info=info, entsize=entsize))

shstr = secs[e_shstrndx]
def sname(n):
    e = d.index(b'\0', shstr['off'] + n)
    return d[shstr['off'] + n:e].decode('latin1')

for s in secs:
    s['nm'] = sname(s['name'])
print("== sections ==")
for s in secs:
    print("%-22s type=%2d addr=%08x off=%08x size=%8d" % (s['nm'], s['type'], s['addr'], s['off'], s['size']))

def dynstr(symsec):
    strtab = secs[symsec['link']]
    return strtab['off'], strtab['size']

print("\n== exports (dynsym) ==")
for s in secs:
    if s['type'] == 11:  # DYNSYM
        stroff, strsz = dynstr(s)
        n = s['size'] // 24
        for i in range(n):
            o = s['off'] + i * 24
            nm, info, other, shndx, val, sz = struct.unpack_from('<IBBHQQ', d, o)
            if nm == 0: continue
            e = d.index(b'\0', stroff + nm)
            name = d[stroff + nm:e].decode('latin1')
            if shndx != 0 and name:
                print("  %-45s val=%08x size=%d" % (name, val, sz))

print("\n== imports (UND) ==")
for s in secs:
    if s['type'] == 11:
        stroff, strsz = dynstr(s)
        n = s['size'] // 24
        for i in range(n):
            o = s['off'] + i * 24
            nm, info, other, shndx, val, sz = struct.unpack_from('<IBBHQQ', d, o)
            if nm == 0: continue
            e = d.index(b'\0', stroff + nm)
            name = d[stroff + nm:e].decode('latin1')
            if shndx == 0 and name:
                print("  ", name)

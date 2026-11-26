#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用法: python entropy.py <文件>
# 作用: 按 1 MB 分块算香农熵，用于快速定位密文段（熵≈8.0）。
import sys, math, collections
d = open(sys.argv[1], 'rb').read()
n = len(d)
print("size", n)
print("head:", d[:64].hex())
# entropy per 1MB block
def ent(b):
    if not b: return 0
    c = collections.Counter(b)
    return -sum((v/len(b)) * math.log2(v/len(b)) for v in c.values())
bs = 1024*1024
for i in range(0, min(n, 8*bs), bs):
    blk = d[i:i+bs]
    print("blk %d off=%08x entropy=%.3f head=%s" % (i//bs, i, ent(blk), blk[:16].hex()))
# tail
print("tail:", d[-64:].hex())

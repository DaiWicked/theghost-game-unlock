#!/usr/bin/env sh
# 编译两个 loader（不依赖 make）
#
#   ANDROID_NDK_HOME=/path/to/ndk ./build.sh
#
set -e

NDK="${ANDROID_NDK_HOME:-}"
if [ -z "$NDK" ]; then
  echo "[!] 请先设置 ANDROID_NDK_HOME（NDK r21+ 即可，推荐 r27c）"
  exit 1
fi

case "$(uname -s)" in
  Linux*)   HOST=linux-x86_64 ;;
  Darwin*)  HOST=darwin-x86_64 ;;
  MINGW*|MSYS*|CYGWIN*) HOST=windows-x86_64 ;;
  *)        HOST=linux-x86_64 ;;
esac

TOOLBIN="$NDK/toolchains/llvm/prebuilt/$HOST/bin"
CC="$TOOLBIN/aarch64-linux-android21-clang"

[ -x "$CC" ] || { echo "[!] 找不到 $CC"; exit 1; }

OUT="$(cd "$(dirname "$0")" && pwd)/../prebuilt"
mkdir -p "$OUT"

echo "[*] CC = $CC"
"$CC" -shared -fPIC -O2 -Wall -Wextra -o "$OUT/libmain.so" loader_main.c -ldl -llog
"$CC" -shared -fPIC -O2 -Wall -Wextra -o "$OUT/libTool.so" loader.c     -ldl -llog

echo "[OK] 产物:"
ls -l "$OUT"/libmain.so "$OUT"/libTool.so

if [ -x "$TOOLBIN/llvm-readelf" ]; then
  echo "--- 导出与依赖 ---"
  "$TOOLBIN/llvm-readelf" -d --dyn-syms "$OUT/libmain.so" | grep -E "NEEDED|JNI_OnLoad" || true
  "$TOOLBIN/llvm-readelf" -d --dyn-syms "$OUT/libTool.so" | grep -E "NEEDED|JNI_OnLoad" || true
fi

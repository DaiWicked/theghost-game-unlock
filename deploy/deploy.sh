#!/system/bin/sh
# kill shot 外挂 —— 自动部署（自动识别官方版 / kill shot 版）
#
# 手机端直接用（root）：
#   把本目录放到 /data/local/tmp/killshot/，然后
#   su -c "sh /data/local/tmp/killshot/deploy.sh"
#   或指定模式：deploy.sh official | killshot | restore | status
set -e
PKG=com.Gameplier.TheGhost
D=$(dirname "$0")

command -v pm >/dev/null 2>&1 || { echo "[!] 不是 Android 环境"; exit 1; }

APKDIR=$(pm path $PKG 2>/dev/null | head -1 | sed 's/package://; s|/base.apk||')
if [ -z "$APKDIR" ]; then
  echo "[!] 没装 $PKG（或 pm 无权限）。请先安装游戏。"; exit 1
fi
LIB=$APKDIR/lib/arm64
[ -d "$LIB" ] || { echo "[!] 找不到 $LIB（设备可能是 32 位或 extractNativeLibs=false）"; exit 1; }

# 自动识别：kill shot 版 APK 自带 libTool.so（6.19 MB 加固壳，或已备份为 .orig）；
# 官方版 APK 里没有这个文件。loader 只有 8 KB，不会误判。
KS=0
[ -f "$LIB/libTool.so.orig" ] && KS=1
if [ -f "$LIB/libTool.so" ]; then
  SZ=$(stat -c %s "$LIB/libTool.so" 2>/dev/null || echo 0)
  [ "$SZ" -gt 1000000 ] && KS=1
fi

if [ -n "$1" ]; then
  MODE=$1
elif [ $KS -eq 1 ]; then
  MODE=killshot
else
  MODE=official
fi

echo "[*] package : $PKG"
echo "[*] lib dir : $LIB"
echo "[*] mode    : $MODE  (自动识别；可手动指定 official|killshot)"

fixperm() {
  for f in "$@"; do
    [ -f "$f" ] || continue
    chown system:system "$f" 2>/dev/null || true
    chmod 755 "$f"
    chcon u:object_r:apk_data_file:s0 "$f" 2>/dev/null || true
  done
}

case "$MODE" in
  status)
    ls -lZ "$LIB"/libmain*.so "$LIB"/libTool*.so 2>/dev/null
    echo "---- dumpsys 检查 ----"
    dumpsys package $PKG 2>/dev/null | grep -E "versionName|firstInstallTime|lastUpdateTime" | head -4
    exit 0;;

  restore)
    [ -f "$LIB/libmain_orig.so" ] && cp -f "$LIB/libmain_orig.so" "$LIB/libmain.so"
    [ -f "$LIB/libTool.so.orig" ] && cp -f "$LIB/libTool.so.orig" "$LIB/libTool.so"
    rm -f "$LIB/libToolShell.so"
    fixperm "$LIB/libmain.so" "$LIB/libTool.so"
    echo "[OK] 已还原为原版。"
    exit 0;;

  official)
    if [ ! -f "$LIB/libmain_orig.so" ]; then
      SZ=$(stat -c %s "$LIB/libmain.so" 2>/dev/null || echo 0)
      if [ "$SZ" -gt 4000 ] && [ "$SZ" -lt 8000 ]; then
        cp -f "$LIB/libmain.so" "$LIB/libmain_orig.so"
        echo "[*] 备份原版 libmain.so ($SZ B)"
      else
        echo "[!] libmain.so 既不是原版($SZ B) 也没有 libmain_orig.so，中止"; exit 1
      fi
    fi
    cp -f "$D/libmain.so"      "$LIB/libmain.so"
    cp -f "$D/libToolShell.so" "$LIB/libToolShell.so"
    fixperm "$LIB/libmain.so" "$LIB/libmain_orig.so" "$LIB/libToolShell.so"
    ;;

  killshot)
    if [ -f "$LIB/libTool.so" ] && [ ! -f "$LIB/libTool.so.orig" ]; then
      cp -f "$LIB/libTool.so" "$LIB/libTool.so.orig"
      echo "[*] 备份原版 libTool.so"
    fi
    cp -f "$D/libTool.so"      "$LIB/libTool.so"
    cp -f "$D/libToolShell.so" "$LIB/libToolShell.so"
    fixperm "$LIB/libTool.so" "$LIB/libToolShell.so"
    ;;

  *)
    echo "用法: deploy.sh [official|killshot|restore|status]"; exit 1;;
esac

ls -lZ "$LIB"/libmain*.so "$LIB"/libTool*.so 2>/dev/null
echo "[OK] 部署完成。"
echo "     下一步：am force-stop $PKG 然后重新打开游戏，进入后直接出现 KILL SHOT 面板（无需卡密）。"

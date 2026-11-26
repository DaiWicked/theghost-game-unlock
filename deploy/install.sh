#!/system/bin/sh
# 一键安装入口（根目录跑这个，不用电脑）
#
#   su -c "sh /sdcard/killshot/install.sh"
#
# 会自动：检查 root → 拷到 /data/local/tmp/killshot → 识别版本 → 部署 so
D=$(dirname "$0")

if [ "$(id -u)" != "0" ]; then
  echo "[!] 需要 root。请用： su -c \"sh $0\""
  exit 1
fi

echo "[*] source: $D"
T=/data/local/tmp/killshot
mkdir -p "$T"
cp -f "$D"/*.so "$D"/deploy.sh "$T"/ 2>/dev/null
chmod 755 "$T"/*.so "$T"/deploy.sh

sh "$T"/deploy.sh "$@"

echo ""
echo "==============================================="
echo " 完成。强制停止游戏后重新打开即可。"
echo " 还原：su -c \"sh $T/deploy.sh restore\""
echo "==============================================="

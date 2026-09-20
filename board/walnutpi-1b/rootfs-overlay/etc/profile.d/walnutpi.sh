# shown on serial/SSH login
if [ -f /run/walnutpi-net.txt ]; then
	cat /run/walnutpi-net.txt
fi
# 只读根，不要写 ash 历史。
export HISTFILE=/dev/null

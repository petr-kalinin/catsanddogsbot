rm -f result.txt
convert $1 PNG32:source_%02d.png || exit 1
./analyze source_%02d.png || exit 1


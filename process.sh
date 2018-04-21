rm -f result.txt
mkdir -p work
cd work
convert ../$1 PNG32:source_%02d.png || exit 1
echo start analyze
../analyze source_%02d.png || exit 1
cp ./result.txt ..


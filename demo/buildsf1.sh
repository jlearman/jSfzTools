# Bash script to build demo

# python ../source/jCutSamps.py -f notes layers/*.wav
# mkdir -p notes
mkdir -p notes
# rm -f notes/*
set -e
set -x
# /usr/bin/python3 ../source/jCutSamps.py -f notes "layers/*.wav"
/usr/bin/python3 ../source/jMap.py sf1 "notes/*.wav"

#!/usr/bin/env bash

# Normalize latency (time before note attack) based on output from jFindOffset.py

OFFSETFILE=${1:-offsets.txt}
EXT=${2:-flac}

SAMPLE_RATE=48000 # samples/sec
PREROLL=20 # desired ms of audio prior to attack

let "DESIRED_OFFSET = (SAMPLE_RATE * PREROLL) / 1000"
echo "desired offset =" $DESIRED_OFFSET samples

set -e # exit on any error

cat "$OFFSETFILE" | while read PLUS FILE OFFSET JUNK ; do
    if [[ "$PLUS" != "+" ]] ; then
        continue
    fi

    # printf "%-30s %s\n" "$FILE" "$TRIM"
    let "TRIM = OFFSET - DESIRED_OFFSET" || true # if expr yields zero, 'let' returns an error (1)
    if [[ $TRIM == 0 ]] ; then
        continue
    fi

    if [[ $TRIM -lt 0 ]] ; then
        # pad rather than trim
        let "PAD = -TRIM"
        echo "+ sox $FILE tmpfile.$EXT pad ${PAD}s"
                sox $FILE tmpfile.$EXT pad ${PAD}s
    else
        echo "+ sox $FILE tmpfile.$EXT trim 0s ${TRIM}s"
                sox $FILE tmpfile.$EXT trim 0s ${TRIM}s
    fi
    mv tmpfile.$EXT $FILE
done


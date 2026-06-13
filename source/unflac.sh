#!/usr/bin/env bash

# convert all FLAC files to WAV but save originals

set -e
for D in `find . -type d` ; do
(
    if compgen -G "$D/*.flac" >/dev/null ; then
        echo "+ flac -d $D/*.flac"
                flac -d $D/*.flac > /dev/null 2>&1
        # rm $D/*.flac
    fi
)
done

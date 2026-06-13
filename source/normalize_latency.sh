#!/usr/bin/env bash

# Normalize latency in sampled note files

FLAC_SOURCE=true
COLLECT_FILES=false
FIND_OFFSETS=false
NORMALIZE_LATENCY=false
CHECK_LATENCY=true

set -e

if $COLLECT_FILES ; then
    if $FLAC_SOURCE ; then
        # Find dirs containing FLAC files
        DIRS=`find . -type f -name "*.flac" -printf '%h\n' | sort -u`
        # echo $DIRS
    else
        # Find dirs containing wav files
        DIRS=`find . -type f -name "*.wav" -printf '%h\n' | sort -u`
    fi

    # collect files
    echo "+ tar cf sampfiles.tar $DIRS"
            tar cf sampfiles.tar $DIRS

    # unpack into tmp dir
    rm -rf tmp
    mkdir tmp
    cd tmp
    echo "+ tar xf ../sampfiles.tar"
            tar xf ../sampfiles.tar
    cd -
fi

cd tmp

if $FIND_OFFSETS ; then
    if $FLAC_SOURCE ; then
        # convert to wav because jFindOffset.py only handles wav
        ../unflac.sh
    fi

    GLOBS=`find . -type f -name "*.wav" -printf '%h/*.wav\n' | sort -u`
    echo "+ jFindOffset.py $GLOBS > ../offsets.txt"
    if $FLAC_SOURCE ; then
        jFindOffset.py $GLOBS | sed -e 's/\.wav /.flac /' > ../offsets.txt
    else
        jFindOffset.py $GLOBS > ../offsets.txt
    fi
fi

if $NORMALIZE_LATENCY ; then
    if $FLAC_SOURCE ; then
        EXT=flac
    else
        EXT=wav
    fi
    ../fix_offsets.sh ../offsets.txt $EXT
fi

if $FLAC_SOURCE ; then
    # remove .wav files
    GLOBS=`find . -type f -name "*.wav" -printf '%h/*.wav\n' | sort -u`
    echo "+ rm $GLOBS"
            rm $GLOBS
fi

if $CHECK_LATENCY ; then
    if $FLAC_SOURCE ; then
        # convert fixed flac files to wav because jFindOffset.py only handles wav
        ../unflac.sh
    fi
    GLOBS=`find . -type f -name "*.wav" -printf '%h/*.wav\n' | sort -u`

    echo "=== CHECKING OFFSETS"
    jFindOffset.py $GLOBS | tee ../offset-check.txt
fi


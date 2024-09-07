#!/usr/bin/python3

# Trim a sample wave file to remove latency (relative silence before first transient).
# Suitable for sampled instruments like piano which have a percussive start.

import sys
import math
import time
import profile
import warnings
import glob
import os.path

import jwave
import jtime
import jmidi
import jtrans

# Algorithm
#   scan for peak (max of both channels)
#   scan forward from beginning to find 1st level over THRESH1 (-24dB)
#   back up until both sides are below THRESH2 (-24-18dB = -42dB) for N samples in a row
#   Back up FADE_IN samples
#   apply fade-in over FADE_IN samples and output
#   output rest of track unchanged

# user configurable parameters

_trig_db        = -30.0         # dB, trigger level
_default_noise  = -40.0         # dB, default noise level -- FIXME

# constants

# tweak parameters

_calcs_per_sec  = 5             # Number of RMS calcs per second, to detect note end
_lead_crossings = 2             # Number of zero crossings to find start of note

# Operating controls

_dry_run        = False         # if True, don't actually create any files.
_debug          = False
_verbose        = False

# find peak level, absolute value
def find_peak(wave):
    peak = 0
    samp_num = 0
    peak_samp_num = 0
    wave.seekSample(samp_num)
    while True:
        try:
            samp = wave.readSample()
        except IndexError:
            return wave.v2dB(peak)
        cur = abs(samp[0])
        if cur > peak:
            peak = cur
            peak_samp_num = samp_num

        # if we haven't hit a new peak in a second or more, we're done
        # TODO: make this configurable in seconds
        if samp_num > peak_samp_num + 48000:
            return wave.v2dB(peak)


# Find the start, old way (use this for now!)
def find_trigger(wave, trig_dB):
    trigger = wave.dB2v(trig_dB)
    samp_num = 0
    wave.seekSample(samp_num)
    while True:
        try:
            samp = wave.readSample()
        except IndexError:
            return 0
        if abs(samp[0]) > trigger:
            break;
        samp_num += 1

    # we've found a trigger.
    return samp_num

#
# Measure the RMS level starting at the given sample, for the given duration.
#
def measure_rms(wave, start_sn, duration):

    if duration < wave.fmt.sampleRate / 200:
        return 0.0

    wave.seekSample(start_sn)
    buf = jwave.Rmsbuf(wave)

    for samp_num in range(start_sn, start_sn + duration):
        samp = wave.readSample()
        buf.add(buf, samp[0])

    return buf.getRms()

# find nth zero crossing (looking forward or backward)
#
# Note: only backwards has been used yet

def find_nth_zero(wave, start_sn, end_sn, slope=1, count=_lead_crossings):

    if start_sn < end_sn:
        first_sn = start_sn
        last_sn = end_sn + 1
        start_ix = 0
        stop_ix = last_sn - first_sn
        incr = 1
    else:
        first_sn = end_sn
        last_sn = start_sn + 1
        start_ix = last_sn - first_sn - 1
        stop_ix = 0
        slope = -slope
        incr = -1

    # read samples into buffer
    samps = []
    wave.seekSample(first_sn)
    for sn in range(first_sn, last_sn):
        samps.append(wave.readSample()[0])

    last = samps[start_ix]
    best = 0
    for ix in range(start_ix + incr, stop_ix, incr):
        this = samps[ix]
        # print(first_sn + ix, this)     ##################################
        if last * slope < 0 and this * slope >= 0:
            # print(first_sn + ix, last, this, slope)
            count -= 1
            best = first_sn + ix
            if count == 0:
                return(first_sn + ix)
        last = this

    if best != 0:
        return best

    if True:
        print("  start_sn ", start_sn)
        print("  end_sn   ", end_sn)
        print("  slope    ", slope)
    raise Exception("No zero crossing found with required slope")


def fade_in_and_copy_wave(iwave, outf, filter_start_sn, start_sn, peakdb):

    samp_count = iwave.get_sample_count()
    if _dry_run:
        print("  Copy orig samples %d to %d" % (filter_start_sn, samp_count))
        return

    # set up output file
    owave = jwave.WaveChunk(outf = outf)
    owave.copyHeader(iwave)
    owave.writeHeader(samp_count - start_sn)

    # fade-in
    samps = []
    iwave.seekSample(filter_start_sn)
    for sn in range(filter_start_sn, start_sn):
        samps.append(iwave.readSample())
    end_ix = len(samps) - 1

    # initialize output vector (two elements for stereo)
    # -- I'd use this for a lowpass but I'm keeping it simpler
    # outsamp = samps[0]
    # for chan in range(len(outsamp)):
    #    outsamp[chan] = 0

    factor = 1.0
    span = float(len(samps))
    for samp in samps:
        scale = factor / span
        outsamp = []
        for chan in range(len(samp)):
            outsamp.append(int(samp[chan] * scale))
        owave.writeSample(outsamp)
        factor = factor + 1.0

    if False:
        peakv = owave.dB2v(peakdb)
        for ix in range(50):
            owave.writeSample([peakv, peakv])

    # Copy the rest
    owave.copySamples(iwave, start_sn, samp_count-1)


# find first zero crossing before trig_sn, where
# the difference bewteen two successive samples is less than
# twice the default noise level.

def find_start_old(wave, trig_sn, start_sn):

    vbose = True
    if vbose:
        print("   ", end="")

    # read channel 1 samples into buffer

    samps = []
    wave.seekSample(start_sn)
    for sn in range(start_sn, trig_sn):
        samps.append(wave.readSample())

    end_ix = len(samps) - 1
    last = samps[end_ix]

    noise = wave.dB2v(_default_noise) * 8       # %%% 8 should be 2?

    for ix in range(end_ix - 1, 0, -1):

        samp = samps[ix]

        for chan in range(len(samp)):
            ok = True
            if -noise < samp[chan] < noise and abs(samp[chan] - last[chan]) < noise:
                pass
            else:
                ok = False
        if ok:
            return start_sn + ix

        last = samp

    raise Exception("Can't find start of sample")

# find first zero crossing before trig_sn, where
# the difference bewteen two successive samples is less than
# twice the default noise level.

def find_start(wave, trig_sn, start_sn, peakdb):

    vbose = True
    if vbose:
        print("   ", end="")

    # read channel 1 samples into buffer

    samps = []
    wave.seekSample(start_sn)
    for sn in range(start_sn, trig_sn):
        samps.append(wave.readSample())

    end_ix = len(samps) - 1
    last = samps[end_ix]

    noise = wave.dB2v(_default_noise + peakdb) * 8

    for ix in range(end_ix - 1, 0, -1):

        samp = samps[ix]

        for chan in range(len(samp)):
            ok = True
            if -noise < samp[chan] < noise and abs(samp[chan] - last[chan]) < noise:
                pass
            else:
                ok = False
        if ok:
            return start_sn + ix

        last = samp

    raise Exception("Can't find start of sample")


def process_sample(inf, outf):
    global _default_noise

    riff = jwave.RiffChunk(inf)
    riff.readHeader()
    riff.printHeader()
    # if riff.type != "riff":
    #     print("Unsupported format (only wave files supported)")
    #     return 1

    wave = jwave.WaveChunk(riff=riff, inf=inf)
    wave.readHeader()
    wave.printHeader()
    rate = wave.fmt.sampleRate

    if wave.fmt.compCode != 1 and wave.fmt.compCode != 0xfffe:
        print("Compressed formats unsupported")
        sys.exit(1)

    print()
    end_sn = 1          # sample number at end of last note

    t = jtime.start()

    # 0) find peak level
    peakdb = find_peak(wave)
    trig_db = peakdb + _trig_db

    # 1) find the next peak that exceeds the trigger level

    trig_sn = find_trigger(wave, trig_dB=trig_db)

    if trig_sn == 0:
        return 0                ## EOF, we're done.

    if _verbose:
        print()
        print("    trig_sn      ", trig_sn, jtime.hmsm(trig_sn, rate))

    # 2) Starting from the trigger point, search backwards to find the
    #    first positive sloped zero crossing.  Search at most a fraction of a second.

    window_sn = max(0, trig_sn - rate/10)
    # start_sn = find_nth_zero(wave, trig_sn, window_sn, slope=1)
    start_sn = find_start(wave, trig_sn, window_sn, peakdb)

    if _verbose:
        print("    start_sn     ", start_sn, jtime.hmsm(start_sn, rate))

    # Back up at most 1 msec to allow room for fade in
    rate = wave.fmt.sampleRate
    filt_start_sn = max(0, start_sn - rate / 1000)

    msec_trimmed = ((filt_start_sn * 1000) / rate)
    print("    trimming %3d msec" % msec_trimmed)

    # HERE
    fade_in_and_copy_wave(wave, outf, filt_start_sn, start_sn, peakdb)

    t = jtime.end(t)
    print()
    print("    Elapsed time:", jtime.msm(t, 1))

    return msec_trimmed

def usage(prog):
    print(file=sys.stderr)
    print("%s: Trim start of wave file" % prog, file=sys.stderr)
    print(file=sys.stderr)
    print("  Usage: %s {[-f <outfolder>] {<wavefile>}}" % prog, file=sys.stderr)
    print(file=sys.stderr)
    print("where:", file=sys.stderr)
    print("  { x } means 'any number of x'", file=sys.stderr)
    print("  -f <outfolder> specifies the output folder for", file=sys.stderr)
    print("     sample files for following input wave files.", file=sys.stderr)
    print("  <wavefile> is a wave file containing a single sample.", file=sys.stderr)
    print("     Unix-style globbing is permitted,", file=sys.stderr)
    print("     that is, you can use '*.wav' or 'samp*/my*foo.wav'.", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)


def main(prog, args):
    global _fn_prefix
    global _fn_suffix
    global _folder
    global _pitchlog

    prof = False                # don't profile

    rCode = 0

    if len(args) < 1:
        usage(prog)
        return 1

    t1 = jtime.start()
    file_count = 0

    tot_msecs_trimmed = 0
    tot_files_trimmed = 0
    max_msecs_trimmed = 0

    while len(args) > 0:

        if len(args) > 2 and args[0] == "-f":
            _folder = args[1] + "/"
            print("Output folder:", args[1])
            del args[0]
            del args[0]

        if len(args) < 1:
            return rCode

        fspec = args[0]
        del args[0]


        for ifname in glob.glob(fspec):

            file_count += 1
            basename = jtrans.tr(ifname, "\\", "/")
            basename = basename.split("/")[-1]          # strip path
            ofname = _folder + "/" + basename
            print("\nProcessing", ifname, "to", ofname, "===================================")
            print()
            try:
                inf  = open(ifname, "rb")
            except IOError as msg:
                raise IOError(msg)

            try:
                outf = open(ofname, "wb")
            except IOError as msg:
                raise IOError(msg)

            t2 = jtime.start()
            try:
                if prof:
                    rCode = profile.run("process_sample(inf, outf)")
                else:
                    msecs_trimmed = process_sample(inf, outf)
            except IOError as msg:
                print msg
                if len(args) > 0:
                    print "Skipping ..."
                    continue

            max_msecs_trimmed = max(msecs_trimmed, max_msecs_trimmed)
            tot_msecs_trimmed += msecs_trimmed
            tot_files_trimmed += 1

            print()
            print("Elapsed time for %s: " % ifname, jtime.hms(jtime.end(t2), 1))

    if file_count > 1:
        print()
        print("Elapsed time for all files:", jtime.hms(jtime.end(t1), 1))
        print("Average of %3d msec trimmed" % (tot_msecs_trimmed/tot_files_trimmed))
        print("Max     of %3d msec trimmed" % max_msecs_trimmed)

    return rCode


prof = False
if __name__ == "__main__":

    warnings.filterwarnings("default", ".*")
    # warnings.filterwarnings("error", ".*")

    args = sys.argv
    prog = args[0].split("\\")[-1]
    del args[0]

    rCode = main(prog, args)

    sys.exit(rCode)

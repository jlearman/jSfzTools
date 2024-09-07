#!/usr/bin/python3
# Chop a wave file into separate sample files.
# For use in building soundfonts.
#
# If we add an option to omit detecting the pitch, it could
# be used for chopping a set into individual songs.  We'd
# also want to adjust the lead time to a second or two.

# added "maybe" when not sure of pitch
# added index to filename if it exists
# move "maybe" to after round-robin suffix

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

# user configurable parameters

_trig_db        = -36.0         # dB, trigger level
_measure_noise  = True
_default_noise  = -60.0         # dB, default noise level when can't measure it.
_noise_delta    = 2.0           # dB, level above initial noise level to find sample end
_dwell_time     = 0.1           # seconds of sample to keep after level reaches noise level
_lead_time      = 0.0           # seconds to keep before start of note
_min_duration   = 1.00          # seconds, minimum note duration.
_max_duration   = 10.5          # seconds, maximum note duration.

_folder         = ""
_fn_prefix      = ""
_fn_suffix      = ""


# constants

_min_freq       = 27            # Hz, lowest note frequency
_max_freq       = 4410          # Hz, highest note frequency (4186.0 = C8)

# tweak parameters

_calcs_per_sec  = 5             # Number of RMS calcs per second, to detect note end
_lead_crossings = 2             # Number of zero crossings to find start of note


# Operating controls

_log_pitch      = False
_dry_run        = False         # if True, don't actually create any files.
_find_note      = True          # whether to add note number to file names

_debug          = False
_verbose        = True

# Find the next sample
def find_trigger(wave, start_sn, trig_dB):
    trigger = wave.dB2v(trig_dB)
    samp_num = start_sn
    wave.seekSample(samp_num)
    while True:
        try:
            samp = wave.readSample()
        except EOFError:
            print("indexError")
            return 0
        except Exception as e:
            print(e)
            sys.exit(1)
        if abs(samp[0]) > trigger:
            break;
        samp_num += 1

    # we've found a trigger.
    return samp_num

#
# Measure the RMS level starting at the given sample, for the given duration.
#
def measure_rms(wave, start_sn, duration):

    if duration < wave.fmt.sampleRate // 200:
        return 0.0

    wave.seekSample(start_sn)
    buf = jwave.Rmsbuf(wave)

    for samp_num in range(start_sn, start_sn + duration):
        samp = wave.readSample()
        buf.add(buf, samp[0])

    return buf.getRms()


def r(samps, delta, length):
    sum = 0
    for sn in range(1, length):
        sum += abs(samps[sn] - samps[sn + delta])
    return sum

def find_pitch(wave, start):
    global _pitchlog
    guess = False

    start += wave.fmt.sampleRate // 4

    # Get a buffer of samples for finding the pitch
    end = min(wave.numSamples-1, start + 4 * wave.fmt.sampleRate)
    samps = wave.readChan(0, start, end)
    buflen = len(samps)

    # autocorrelation method for finding pitch
    # Define the autocorrelation function r(delta) defined as the sum of the
    # pointwise absolute difference between the val(t) and val(t + delta).
    # Find the lowest local minimum in r(delta).
    # Ignore noise in r(delta) using a latch filter with a miniumum deadband
    # (# samples elapsed since the minimum changed)

    # find the first sustained maximum.

    latch = 3

    maxr = 0
    maxt = 0
    step = 12.0
    rate = 1.0 * wave.fmt.sampleRate
    note = 100.0

    delta = 4

    # for delta in range(wave.fmt.sampleRate / _max_freq, wave.fmt.sampleRate / _min_freq):
    while delta < wave.fmt.sampleRate // _min_freq:

        cur = r(samps, delta, buflen // 2)
        if _log_pitch:
            print(wave.fmt.sampleRate / delta, ",", cur, file=_pitchlog)
        if cur > maxr:
            maxr = cur
            maxt = delta
        if maxt != 0 and delta - maxt >= latch:
            break

        d2 = int(rate / pow(2, (step * math.log(rate / delta, 2) - 1) / step))
        delta = max(d2, delta + 1)
        last_note = note
        note = 12 * math.log(rate/delta)
        # print("delta = %d, f = %d, note = %5.1f, diff = %5.1f" % (
        #     delta, rate/delta, note, last_note - note))

    else:
        print("    Can't find pitch (1).")
        print("    maxt", maxt)
        print("    delta", delta)
        print("    latch", latch)
        return 0
        # raise Exception("Sample too short (1)")

    # find the next local minumum.

    minr = 0x7fffffffffffffff
    mint = 0
    limit = maxr // 3
    # for delta in range(delta + 1, wave.fmt.sampleRate / _min_freq):
    while delta < wave.fmt.sampleRate // _min_freq:

        cur = r(samps, delta, buflen // 2)
        if _log_pitch:
            print(wave.fmt.sampleRate // delta, ",", cur, file=_pitchlog)

        if cur < minr:
            minr = cur
            mint = delta
        if mint != 0 and delta - mint >= latch:
            if minr < limit:
                if not _log_pitch:
                    break

        d2 = int(rate / pow(2, (step * math.log(rate / delta, 2) - 1) / step))
        delta = max(d2, delta + 1)
        last_note = note
        note = 12 * math.log(rate/delta)
        # print("delta = %d, f = %d, note = %5.1f, diff = %5.1f" % (
        #     delta, rate/delta, note, last_note - note))

    else:
        guess = True
        print()
        print("    Can't find pitch (2).  Returning best guess.")
        print("    start", start)
        print("    maxr", maxr)
        print("    maxt", maxt)
        print("    minr", minr)
        print("    mint", mint)
        print("    delta", delta)
        print("    latch", latch)
        # return 0
        # if not _log_pitch:
            # raise Exception("Sample too short (2)")

    return wave.fmt.sampleRate / float(mint), guess


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
        # print(first_sn + ix, this)    ##################################
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


# Find the end of the note.
#
# Return (end_sn, limit_sn, peak), where
#   end_sn is sample number of the actual end of the note.
#   limit_sn is the place to end the sample file.
#   When the note exceeds _max_duration, limit_sn is less than end_sn.
#   Otherwise, limit_sn exceeds end_sn, because it includes _dwell_t
#   at the end of the note.

def find_end(wave, start_sn, noise, dwell_t, max_t):
    calc_interval = wave.fmt.sampleRate // _calcs_per_sec
    noise = max(noise, -60.0)

    dwell_t = int(dwell_t * wave.fmt.sampleRate)
    max_t   = int(max_t   * wave.fmt.sampleRate)
    # print("### max_t =", jtime.sm(max_t, wave.fmt.sampleRate))

    buf = jwave.Rmsbuf(wave, 0)
    wave.seekSample(start_sn)
    sn = 0
    limit_sn = None

    while True:
        try:
            buf.add(buf, wave.readSample()[0])
        except IndexError:
            print("  Sample file ends before silence")
            return (start_sn + sn, start_sn + sn, buf.getPeak())
        if sn % calc_interval == 0:
            rms = buf.getRms()
            if rms < noise:
                end_sn = start_sn + sn
                if limit_sn == None:
                    limit_sn = min(end_sn + dwell_t, wave.numSamples - 1)
                return (end_sn, limit_sn, buf.getPeak())
        if not limit_sn and sn > max_t:
            limit_sn = buf.findPrevCrossing() + start_sn
            # print("### found limit at", jtime.sm(limit_sn, wave.fmt.sampleRate))
        sn += 1

    raise Exception("Can't find sample end")

def wavename(folder, fn_prefix, mnote, notename, guess, suffix):
    fname = (
        folder
        + fn_prefix
        + "%03d_" % mnote
        + notename
        + suffix
        + ("_maybe" if guess else ""))

    if os.path.exists(fname + ".wav"):
        index = 1
        while os.path.exists("%s-%d.wav" % (fname, index)):
            index += 1
        fname = "%s-%d" % (fname, index)

    fname = fname + ".wav"
    return fname


def copy_wave(iwave, start_sn, end_sn, file_num, freq, guess, sn_ratio, peak, duration):
    global _logfile

    if freq == 0:
        mnote = 0
        notename = "X%02d" % file_num
        cents = 0
    else:
        (mnote, notename, cents) = jmidi.midi_note_for_freq(freq)

    fname = wavename(_folder, _fn_prefix, mnote, notename, guess, _fn_suffix)
    print("File %3d:" % file_num, fname)
    print(_fn_prefix                    \
        ,",", file_num                  \
        ,",", mnote                     \
        ,",", notename.strip("_")       \
        ,",", "%+03d" % cents           \
        ,",", "%7.2f" % freq            \
        ,",", "%4.1f" % sn_ratio        \
        ,",", "%4.1f" % peak            \
        ,",", jtime.sm(duration, iwave.fmt.sampleRate) + "s",
        file=_logfile)

    if not _dry_run:
        ofile = open(fname, "wb")
        owave = jwave.WaveChunk(outf = ofile)
        owave.copyHeader(iwave)
        # owave.setNote(mnote)
        owave.writeHeader(end_sn + 1 - start_sn)
        owave.copySamples(iwave, start_sn, end_sn)
        ofile.close()


# find first zero crossing before trig_sn, where
# the difference bewteen two successive samples is less than
# twice the default noise level.

def find_start(wave, trig_sn, start_sn):

    vbose = True
    if vbose:
        print("   ", end="")

    # read channel 1 samples into buffer

    samps = []
    wave.seekSample(start_sn)
    for sn in range(start_sn, trig_sn):
        samps.append(wave.readSample()[0])

    end_ix = len(samps) - 1
    last = samps[end_ix]

    noise = wave.dB2v(_default_noise) * 8

    for ix in range(end_ix - 1, 0, -1):

        this = samps[ix]

        if -noise < this < noise:
            if vbose:
                print(".", end="")
            if abs(this - last) < noise:
                if vbose:
                    print()
                return start_sn + ix

        last = this

    raise Exception("Can't find start of sample")


def old_find_start(wave, trig_sn, start_sn):

    # read channel 1 samples into buffer

    samps = []
    wave.seekSample(start_sn)
    for sn in range(start_sn, trig_sn):
        samps.append(wave.readSample()[0])

    # find N samples in a row whose values are less than default noise

    N = 3
    count = 0

    start_ix = len(samps)

    noise = wave.dB2v(_default_noise)

    for ix in range(start_ix - 1, 0, -1):

        # print("%6d %6d" % (ix, this))

        if abs(samps[ix]) < noise:
            # print(".", end="")
            count += 1
            if count == N:
                return start_sn + ix
        else:
            count = 0

    raise Exception("Start of sample not found")

def process_samples():
    global _default_noise

    with open(_infile, "rb") as inf:

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

        if wave.fmt.compCode != 1:
            print("Compressed formats unsupported")
            inf.close()
            print(" ### %s CLOSE" % _infile)
            sys.exit(1)

        print()
        file_num = 1
        end_sn = 1          # sample number at end of last note
        while True:
            t = jtime.start()

            # 1) find the next peak that exceeds the trigger level

            trig_sn = find_trigger(wave, end_sn, trig_dB=_trig_db)
            if trig_sn == 0:
                inf.close()
                print(" ### %s CLOSE on return" % _infile)
                return              ## EOF, we're done.

            if _verbose:
                print()
                print("    trig_sn      ", trig_sn, jtime.hmsm(trig_sn, rate))

            # 2) Starting from the trigger point, search backwards to find the
            #    first positive sloped zero crossing.  Search at most a fraction of a second.

            end_sn = max(end_sn, trig_sn - rate//10)
            # print("    end_sn", end_sn, "trig_sn", trig_sn)
            # start_sn = find_nth_zero(wave, trig_sn, end_sn, slope=1)
            start_sn = find_start(wave, trig_sn, end_sn)
            start_sn = max(1, start_sn - int(_lead_time * rate))

            if _verbose:
                print("    start_sn     ", start_sn, jtime.hmsm(start_sn, rate))

            # 3) Back up at most a second and measure a half-second of noise

            if _measure_noise:
                noise_sn = max(1, start_sn - rate)
                dur = min(rate // 2, (start_sn - noise_sn) // 2)
                noise_lev = measure_rms(wave, noise_sn, dur)
                if noise_lev == None or noise_lev == 0.0:
                    print("  Can't measure noise, using %5.2f dB" % _default_noise)
                    noise_lev = _default_noise
                else:
                    # use this value if we can't measure it later
                    _default_noise = noise_lev
            else:
                noise_lev = _default_noise

            if _verbose:
                print("    noise_lev    ", noise_lev)

            # 4) Find where the sample ends:
            #    where the RMS level matches the initial noise level plus a delta,
            #    plus a dwell time.
            (end_sn, limit_sn, peak_lev) = find_end(wave, trig_sn, noise_lev + _noise_delta,
                _dwell_time, _max_duration)

            sdur = limit_sn - start_sn
            ndur = end_sn - start_sn
            if _verbose:
                print("    end_sn       ", end_sn, jtime.hmsm(end_sn, rate))
                print("    limit_sn     ", limit_sn, jtime.hmsm(end_sn, rate))
                print("    note duration", jtime.sm(ndur, rate))
                print("    samp duration", jtime.sm(sdur, rate))

            if ndur < _min_duration * wave.fmt.sampleRate:
                if _verbose:
                    print("    Skipping .. too short")
                    print()
                continue


            # 5) Find which note the sample is
            if _find_note:
                freq, guess = find_pitch(wave, trig_sn)

            if _verbose:
                print("    freq         ", freq)
                print()

            # 6) Record results & copy wave data

            if _debug:
                print()
                print("%3d freq: %-6.1f floor:%5.1f peak:%5.1f S/N: %-5.1f start:%d=%9s dur:%9s" % (
                    file_num,
                    freq,
                    noise_lev,
                    peak_lev,
                    peak_lev - noise_lev,
                    start_sn, jtime.msm(start_sn, rate),
                    jtime.msm(sdur, rate),
                    jtime.msm(ndur, rate),
                    ))

            copy_wave(wave, start_sn, limit_sn, file_num, freq, guess, peak_lev - noise_lev, peak_lev, sdur)
            file_num += 1

            t = jtime.end(t)
            print()
            print("    Elapsed time:", jtime.msm(t, 1))

def usage(prog):
    print(file=sys.stderr)
    print("%s: cut wave file into individual samples" % prog, file=sys.stderr)
    print(file=ys.stderr)
    print("  Usage: %s {[-f <outfolder>] {<wavefile>}}" % prog, file=sys.stderr)
    print(file=sys.stderr)
    print("where:", file=sys.stderr)
    print("  { x } means 'any number of x'", file=sys.stderr)
    print("  -f <outfolder> specifies the output folder for", file=sys.stderr)
    print("     sample files for following input wave files.", file=sys.stderr)
    print("  <wavefile> is a wave file containing mutliple", file=sys.stderr)
    print("     samples.  Unix-style globbing is permitted,", file=sys.stderr)
    print("     that is, you can use '*.wav' or 'samp*/my*foo.wav'.", file=sys.stderr)
    print(file=sys.stderr)
    sys.exit(1)


def main(prog, args):
    global _fn_prefix
    global _fn_suffix
    global _infile
    global _folder
    global _pitchlog
    global _logfile

    rCode = 0

    if len(args) < 1:
        usage(prog)
        return 1

    if _log_pitch:
        print("OPENING PITCH LOG")
        _pitchlog = open("pitch.csv", "w")

    t1 = jtime.start()
    file_count = 0

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

        for _infile in glob.glob(fspec):

            file_count += 1
            print("\nProcessing", _infile, "===================================")
            print()

            # Split the file name into prefix (inst name) and suffix (velocity)

            basename = _infile.split(".")[0]            # strip ".wav"
            basename = jtrans.tr(basename, "\\", "/")
            basename = basename.split("/")[-1]          # strip path

            parts = basename.split("_")
            _fn_prefix = parts[0] + "_"
            del parts[0]
            _fn_suffix = "_" + "_".join(parts)
            print("prefix =", _fn_prefix)
            print("suffix =", _fn_suffix)

            _logfile = open(_folder + _fn_prefix + _fn_suffix[1:] + "_log.csv", "w")
            print("fn_prefix"           \
                ,",", "file_num"        \
                ,",", "mnote"           \
                ,",", "notename"        \
                ,",", "cents"           \
                ,",", "freq"            \
                ,",", "sn_ratio"        \
                ,",", "peak"            \
                ,",", "duration"        \
                , file=_logfile)

            t2 = jtime.start()
            try:
                if prof:
                    rCode = profile.run("process_samples()")
                else:
                    rCode = process_samples()
            except IOError as msg:
                print(msg)
                if len(args) > 0:
                    print("Skipping ", _infile, file=sys.stderr)
                    _logfile.close()
                    continue

            print()
            print(("Elapsed time for %s: " % _infile), jtime.hms(jtime.end(t2), 1))

            _logfile.close()

    if file_count > 1:
        print()
        print("Elapsed time for all files:", jtime.hms(jtime.end(t1), 1))

    return rCode


prof = False
if __name__ == "__main__":

    warnings.filterwarnings("default", ".*")
    # warnings.filterwarnings("error", ".*")

    args = sys.argv
    prog = args[0].split("\\")[-1]
    del args[0]

    # command line mode
    rCode = main(prog, args)
    sys.exit(rCode)


    ### Maybe later.  Works but I don't like it.

    while True:

        print("Args: (^C to exit)", end="")

        try:
            print()
            main(sys.stdin.readline())
            print()
        except KeyboardInterrupt:
            sys.exit(0)


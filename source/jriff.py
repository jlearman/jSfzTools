#!/usr/bin/python3
#
# LIcense: CC0
#
# NOT a good example of python coding!
#
# Read & dump RIFF file.
# Make guesses about chunks
# decode smpl chunk
# option to extract a chunk

import sys
import jio

majors = (
    "RIFF",
    "LIST",
    "INFO",
    # "fLaC",   # sorry, no dice
    )

dbg = True

def roundup(ln):
    if ln & 1:
        return ln + 1
    return ln

class Chunk:
    def __init__(self, riffFile, parent):
        self.parent = parent
        self.riff   = riffFile
        self.subchunks = []

        if parent == None:
            self.level = 0
        else:
            self.level = parent.level + 1

    def ind(self):
        str = ""
        for ix in range(0, self.level):
            str += " "
        return str

    def iseek(self):
        self.riff.inf.seek(self.inf_loc)

    def inf(self):
        return self.riff.inf

    def read(self, extract=None):
        self.format     = self.riff.inf.read(4)
        self.len        = jio.get_uint32(self.riff.inf)
        self.inf_loc    = self.riff.inf.tell()  # location of value

        if dbg:
            print("[d] 0x%08x: %s %s" %(self.inf_loc - 8, self.ind(), self.format), end=" ")
            print("len: 0x%08x" % self.len, end=" ")
            if extract:
                print("Extract:", extract, end=" ") # %%%

        if self.format == extract:
            if dbg:
                print("[d] extracting!")
                sys.exit(0)
            sys.stdout.write(self.format[0])
            sys.stdout.write(self.format[1])
            sys.stdout.write(self.format[2])
            sys.stdout.write(self.format[3])
            put_uint32(sys.stdout, self.len)
            for ix in range(self.len):
                byte = self.riff.inf.read(1)
                sys.stdout.write(byte)
            sys.exit(0)

        if self.format == "smpl" and self.len >= 0x2c:
            print("loc: 0x%08x" % self.inf_loc)
            manu = jio.get_uint32(self.riff.inf)
            prod = jio.get_uint32(self.riff.inf)
            period = jio.get_uint32(self.riff.inf)
            unity = jio.get_uint32(self.riff.inf)
            pitchfrac = jio.get_uint32(self.riff.inf)
            smpte_fmt = jio.get_uint32(self.riff.inf)
            smpte_offset = jio.get_uint32(self.riff.inf)
            num_loops = jio.get_uint32(self.riff.inf)
            sampler_data = jio.get_uint32(self.riff.inf)
            print(("  manu          = 0x%x" % manu))
            print(("  prod          = 0x%x" % prod))
            print(("  period        = 0x%x" % period))
            print(("  unity         = 0x%x" % unity))
            print(("  pitchfrac     = 0x%x" % pitchfrac))
            print(("  smpte_fmt     = 0x%x" % smpte_fmt))
            print(("  smpte_offset  = 0x%x" % smpte_offset))
            print(("  num_loops     = 0x%x" % num_loops))
            print(("  sampler_data  = 0x%x" % sampler_data))
            ix = 0
            len = 0
            while ix < num_loops and len + 4 <= self.len:
                cue_id = jio.get_uint32(self.riff.inf)
                type = jio.get_uint32(self.riff.inf)
                start = jio.get_uint32(self.riff.inf)
                end = jio.get_uint32(self.riff.inf)
                fraction = jio.get_uint32(self.riff.inf)
                play_count = jio.get_uint32(self.riff.inf)
                print(("    cue_id       = 0x%x" % cue_id))
                print(("    type         = 0x%x" % type))
                print(("    start        = 0x%x" % start))
                print(("    end          = 0x%x" % end))
                print(("    fraction     = 0x%x" % fraction))
                print(("    play_count   = 0x%x" % play_count))
                ix += 1
                len += 6 * 4

            while False and len <= self.len:
                stuff = self.riff.inf.read(4)
                print(("    data         = 0x%x" % data))

        if self.format not in majors:
            if dbg:
                print("loc: 0x%08x" % self.inf_loc)
            self.riff.inf.seek(self.inf_loc + roundup(self.len), 0)
            return 8 + roundup(self.len)

        self.type = self.riff.inf.read(4)
        self.inf_loc += 4
        if dbg:
            print("type:", self.type,)
            print("loc: 0x%08x" % self.inf_loc)

        ln = 4
        while ln < self.len - 1:
            chunk = Chunk(self.riff, self)
            chunklen = chunk.read(extract)
            if ln + chunklen > self.len:
                print("Error: last chunk exceeded parent's len")
                sys.exit(1)
            self.subchunks.append(chunk)
            ln += chunklen
            # print(self.ind(), "-- %s at 0x%08x, ln = 0x%08x" % (self.format, self.inf_loc + ln, ln))

        if self.len != roundup(ln):
            print("Error: insufficient data")

        return roundup(self.len + 8)

    def printHdr(self):
        print("0x%08x: %s %s" %(self.inf_loc - 8, self.ind(), self.format), end=" ")
        print("len: 0x%08x" % self.len, end=" ")
        if "type" in dir(self):
            print("type:", self.type)
        else:
            print()

    def skip(self):
        self.riff.inf.seek(self.inf_loc + self.len)

    def walk(self, func, arg=None):
        func(self, arg)
        for chunk in self.subchunks:
            chunk.walk(func, arg)

    def prn(self, text):
        print("%11s %s %s" % ("", self.ind(), text))

    def prnLoc(self, text):
        print("0x%08x %s %s" % (self.inf_loc, self.ind(), text))

class RiffFile:

    def __init__(self, inf=None, outf=None):
        self.inf        = inf
        self.inf_ix     = 0
        self.outf       = outf
        self.outf_ix    = 0
        self.vsize      = None

    def read(self, extract=None):
        if not self.inf:
            return
        self.chunk = Chunk(self, None)
        self.chunk.read(extract)

    def walk(self, func, arg=None):
        if "chunk" in dir(self):
            self.chunk.walk(func, arg)


def main(args):
    global dbg

    extract = None

    if len(args) < 2:
        print("usage: %s <infile> -- dumps RIFF file")
        print()
        sys.exit(1)

    while len(args) > 1 and args[1].startswith("-"):
        option = args[1]
        del args[1]
        if option == "-x":
            extract = args[1] # should check for 2nd option
            del args[1]
            dbg = False

    infname = args[1]
    del args[1]

    try:
        inf  = open(infname, "rb")
    except IOError as msg:
        print(msg)
        sys.exit(1)

    riff = RiffFile(inf)
    riff.read(extract)

if __name__ == "__main__":

    main(sys.argv)

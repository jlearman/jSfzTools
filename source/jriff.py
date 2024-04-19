#!/usr/local/bin/python
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

majors = (
    "RIFF",
    "LIST",
    "INFO",
    # "fLaC",   # sorry, no dice
    )

dbg = True

def get_sint16(file):
    val = get_uint16(file)
    if val >= 0x8000:
        return val - 0x10000
    return val

def put_sint16(file):
    bytes = ""
    bytes += chr(val & 0xff)
    val = val >> 8
    bytes += chr(val & 0xff)
    ofile.write(bytes)

def get_sint8(file):
    print "8-bit format unsupported"
    sys.exit(1)

def get_uint32(file):
    bytes = file.read(4)
    if len(bytes) < 4:
        print "expecting 4 bytes, got", len(bytes)
        sys.exit(1)
    return ((((0L
        + ord(bytes[3]) << 8)
        + ord(bytes[2]) << 8)
        + ord(bytes[1]) << 8)
        + ord(bytes[0]))

def put_uint32(ofile, val):
    bytes = ""
    bytes += chr(val & 0xff)
    val = val >> 8
    bytes += chr(val & 0xff)
    val = val >> 8
    bytes += chr(val & 0xff)
    val = val >> 8
    bytes += chr(val & 0xff)
    ofile.write(bytes)

def get_uint24(file):
    bytes = file.read(3)        
    return (((
        ord(bytes[2]) << 8)
        + ord(bytes[1]) << 8)
        + ord(bytes[0]))

def get_uint16(file):
    bytes = file.read(2)
    return (ord(bytes[1]) << 8) + ord(bytes[0])

def put_uint16(ofile, val):
    bytes = ""
    bytes += chr(val & 0xff)
    val = val >> 8
    bytes += chr(val & 0xff)
    ofile.write(bytes)

def get_uint8(file):
    return ord(file.read(1))

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
        self.len        = get_uint32(self.riff.inf)
        self.inf_loc    = self.riff.inf.tell()  # location of value

        if dbg:
            print "[d] 0x%08x: %s %s" %(self.inf_loc - 8, self.ind(), self.format),
            print "len: 0x%08x" % self.len,
            if extract:
                print "Extract:", extract,       # %%%

        if self.format == extract:
            if dbg:
                print "[d] extracting!"
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
            print "loc: 0x%08x" % self.inf_loc
            manu = get_uint32(self.riff.inf)
            prod = get_uint32(self.riff.inf)
            period = get_uint32(self.riff.inf)
            unity = get_uint32(self.riff.inf)
            pitchfrac = get_uint32(self.riff.inf)
            smpte_fmt = get_uint32(self.riff.inf)
            smpte_offset = get_uint32(self.riff.inf)
            num_loops = get_uint32(self.riff.inf)
            sampler_data = get_uint32(self.riff.inf)
            print ("  manu          = 0x%x" % manu)
            print ("  prod          = 0x%x" % prod)
            print ("  period        = 0x%x" % period)
            print ("  unity         = 0x%x" % unity)
            print ("  pitchfrac     = 0x%x" % pitchfrac)
            print ("  smpte_fmt     = 0x%x" % smpte_fmt)
            print ("  smpte_offset  = 0x%x" % smpte_offset)
            print ("  num_loops     = 0x%x" % num_loops)
            print ("  sampler_data  = 0x%x" % sampler_data)
            ix = 0
            len = 0
            while ix < num_loops and len + 4 <= self.len:
                cue_id = get_uint32(self.riff.inf)
                type = get_uint32(self.riff.inf)
                start = get_uint32(self.riff.inf)
                end = get_uint32(self.riff.inf)
                fraction = get_uint32(self.riff.inf)
                play_count = get_uint32(self.riff.inf)
                print ("    cue_id       = 0x%x" % cue_id)
                print ("    type         = 0x%x" % type)
                print ("    start        = 0x%x" % start)
                print ("    end          = 0x%x" % end)
                print ("    fraction     = 0x%x" % fraction)
                print ("    play_count   = 0x%x" % play_count)
                ix += 1
                len += 6 * 4
                
            while False and len <= self.len:
                stuff = self.riff.inf.read(4)
                print ("    data         = 0x%x" % data)

        if self.format not in majors:
            if dbg:
                print "loc: 0x%08x" % self.inf_loc
            self.riff.inf.seek(self.inf_loc + roundup(self.len), 0)
            return 8 + roundup(self.len)

        self.type = self.riff.inf.read(4)
        self.inf_loc += 4
        if dbg:
            print "type:", self.type,
            print "loc: 0x%08x" % self.inf_loc

        ln = 4
        while ln < self.len - 1:
            chunk = Chunk(self.riff, self)
            chunklen = chunk.read(extract)
            if ln + chunklen > self.len:
                print "Error: last chunk exceeded parent's len"
                sys.exit(1)
            self.subchunks.append(chunk)
            ln += chunklen
            # print self.ind(), "-- %s at 0x%08x, ln = 0x%08x" % (self.format, self.inf_loc + ln, ln)

        if self.len != roundup(ln):
            print "Error: insufficient data"

        return roundup(self.len + 8)

    def printHdr(self):
        print "0x%08x: %s %s" %(self.inf_loc - 8, self.ind(), self.format),
        print "len: 0x%08x" % self.len,
        if "type" in dir(self):
            print "type:", self.type
        else:
            print

    def skip(self):
        self.riff.inf.seek(self.inf_loc + self.len)
        
    def walk(self, func, arg=None):
        func(self, arg)
        for chunk in self.subchunks:
            chunk.walk(func, arg)

    def prn(self, text):
        print "%11s %s %s" % ("", self.ind(), text)

    def prnLoc(self, text):
        print "0x%08x %s %s" % (self.inf_loc, self.ind(), text)

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
        print "usage: %s <infile> -- dumps RIFF file"
        print
        sys.exit(1)

    while len(args) > 1 and args[1].startswith("-"):
        option = args[1]
        del args[1]
        if option == "-x":
            extract = args[1]
            del args[1]
            dbg = False

    infname = args[1]
    del args[1]

    try:
        inf  = file(infname, "rb")
    except IOError, msg:
        print msg
        sys.exit(1)

    riff = RiffFile(inf)
    riff.read(extract)

if __name__ == "__main__":

    main(sys.argv)

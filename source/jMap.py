#!/usr/bin/python
# Build keyboard map for samples
#
# Builds soundfont key map given a set of sample files
# and a little config data.
#
# Sample files must be named according to a convention:
#
#  xxxx_<mnote>_xxxx_<layer>.wav
#
#  where
#    <mnote> is the MIDI note number
#    <layer> is arbitrary text identifying the layer (see layer config below)

# 2a
#   Set VEL_LOC and NOTE_LOC to specify format
#   add globals
#   For piano: ampeg-release = 5.0 for regions staring over Gb6 (need to make a config option.)
#   low-note range for release
#   removed "for piano" no-damper release range.  Do that using release ranges.
#   use <master> instead of "global", add "master"

# 2a-1
#   Support round-robins
#   use "key" instead of "lokey", "hikey", and "pitch_keycenter" when possible
#   support crossfades (!)

# 2a-2
#   add "header", "control", and "final" commands

# 2a-3
#   -nx option: omit crossfades (and add "-no-xfade" to sfz name)

# 2a-4
#   transpose (for Purgatory Creek that has to be transposed down 12 steps due to diff note/octave convention

# TODO: add name to group & master.  (Omit master?)
# TODO: support header/trailer (header, master, trailer?)
# TODO: support loop_mode=one_shot (globally or for notes in a region.)  Omit ampeg_release

import sys
import warnings
import glob

import jmidi
import jtime
import jtrans

import collections
import pprint

# index constants into LAYER list

LNAME		= 0
LVEL		= 1
LATTEN		= 2
LLEVEL		= 3
LXFIN_LO        = 4
LXFIN_HI        = 5
LXFOUT_LO       = 6
LXFOUT_HI       = 7

# initializations 

# entry structure - list of:
#  lname	name
#  lvel		velocity
#  latten	sf attenuation for layer (obsolete?)
#  llevel	amount layer was boosted by when normalized.
#           	  If zero, velocity curve adjustment not done.
#  lprevlevel	amount previous layer was boosted by.
#
# Layer entries must be ordered from softest to loudest.

LAYER = []

# release note ranges: list from high-to-low of (relnote, relval)

RELEASE_RANGES = []

############################################################################
#
# Configuration (should be read in)
#

# How to find layer name and note from file name:

# DELIMS are the characters treated as delimiters to split the
# file name.
# After splitting a line into parts separated by the delimiter,
# LOC is the location of the note or layer name, where 0 is the
# first part, 1 is the second, etc.  -1 is the last, -2 is the
# second to last, etc.

DELIMS		= " `~!@$%^&*()_+-={}|[]:\";'<>?,.\t"
DELIMS		= " `~!@$%^&*()_+={}|[]:\";'<>?,.\t"

# LAYER_LOC	= -1
# NOTE_LOC	=  2

# Not currently configurable: RR#, if any, is last part of
#   fname before .wav extension, separated by a dash.
# No rr# is used for the first sample.  -1 is used for the
# second sample, -2 for the third, and so on.

# defaults for mapping parameters

MAX_LAYER_SHIFT		= 2		# don't jump layers more than this
MAX_NOTE_SHIFT		= 7		# don't stretch pitch more than this

NOTE_SHIFT_COST		= 2		# relative cost of shifing notes (vs. layers)
LAYER_SHIFT_COST	= 1		# relative cost of shifing layers (vs. notes)

EXTEND_LAYER_UP	= True		# whether better to map higher vel  sample than lower
EXTEND_NOTE_UP	= True		# whether better to map higher note sample than lower

LOWEST_LEVEL	= 640		# attenuation for vel=1 notes (when using "level"), in cB

# default range for whole keyboard map

LO_KEY		= jmidi.notenum("C1")	# lowest C on piano, lowest key I use
HI_KEY		= jmidi.notenum("G7")	# highest key on MR76

###############################################################################

class Globals:
    def __init__(self):
        pass

gl = Globals
gl.grid = []
gl.samps = {}
gl.layernum = {}
gl.lnamelen = 0

class Samp:
    def __init__(self):
        pass

def build_grid(grid):

    for layer in range(0, len(LAYER)):
	grid.append([])
        for key in range(0, HI_KEY+MAX_NOTE_SHIFT+1):
	    grid[layer].append(collections.OrderedDict())

	gl.layernum[LAYER[layer][LNAME]] = layer

def build_sampchars():

    # omit ANSI and DOS unprintables (7f only one for DOS)
    # unprintables = [0x7f, 0x81, 0x8d, 0x8f, 0x90, 0x9d,]

    chars = ""

    # for ichar in range(ord('"'), 0xff): 
    for ichar in range(ord('"'), 0x7f): 
	# if ichar not in unprintables:
	    chars += chr(ichar)

    return chars


def load_filenames(args):
    global gl
    global CROSSFADE
    global no_xfade
    global TRANSPOSE

    warnings = []
    errors = []

    for arg in args: 
    #{
	for sampfname in glob.glob(arg):

	    if True:
		try:
		    sampf = file(sampfname, "rb")
		except IOError, msg:
		    errors.append("Can't open sample file: " + str(msg))
		    continue
		else:
		    sampf.close()

	    samp = Samp()

	    # strip directory
	    basename = sampfname.replace("\\", "/")
	    basename = basename.split("/")[-1]

	    # strip ".wav" extension
	    basename = basename.split(".")
	    basename = ".".join(basename[0:-1])
	    basename = jtrans.tr(basename, DELIMS, " ")

            # get round-robin (RR) index, if any
            # FIXME: this doesn't allow hyphens in the file name!
            rrob = ''
            parts = basename.split("-")
            if len(parts) == 2:
                rrob = parts[1]

	    # get layer name

	    parts = basename.split()
	    if len(parts) <= abs(LAYER_LOC):
	        loc = LAYER_LOC
		if loc >= 0:
		    loc += 1
	        print >>sys.stderr, (
		    "After splitting filename '%s' delimiters,"
		    % (basename))
	        print >>sys.stderr, (
		    "there aren't enough parts to find part number %d." % loc)
		sys.exit(1)
	    layername  = parts[LAYER_LOC]

            # handle RR
            layerparts = layername.split("-")
            if len(layerparts) > 1:
                layername = layerparts[0]

	    # get note: might be MIDI number or note name

	    if len(parts) <= abs(NOTE_LOC):
	        loc = NOTE_LOC
		if loc >= 0:
		    loc += 1
	        print >>sys.stderr, (
		    "After splitting filename '%s' at delimiters, "
		    % (sampfname))
	        print >>sys.stderr, (
		    "there aren't enough parts to find part number %d." % loc)
		sys.exit(1)
	    notespec   = parts[NOTE_LOC]

	    mnote = jmidi.notenum(notespec)
	    if mnote == None:
	        print >>sys.stderr, (
		    "Invalid MIDI note designation '%s' in '%s'"
		    % (notespec, basename))
		print >>sys.stderr, "Parts are:", parts
		sys.exit(1)
            # print >>sys.stderr, "MNOTE:", mnote, "XPOSE:", TRANSPOSE
            mnote = mnote + TRANSPOSE

	    # print sampfname, mnote, layername, jmidi.mnote_name(mnote)[0]
	    samp.fname = sampfname
	    samp.mnote = mnote
	    samp.notename = jmidi.mnote_name(mnote, pad=None)
	    samp.layername = layername
            samp.rrob = rrob
	    if layername not in gl.layernum:
	        warnings.append("Sample for unconfigured layer '%s': %s, parts = %s"
		    % (samp.layername, samp.fname, str(parts)))
		continue
	    samp.layer = gl.layernum[layername]

	    if samp.layer == None:
	        warnings.append("Sample for missing layer '%s': %s"
		    % (samp.layername, samp.fname))
		continue

	    x = LO_KEY - MAX_NOTE_SHIFT
	    if (samp.mnote < max(0, LO_KEY - MAX_NOTE_SHIFT)
		or samp.mnote > HI_KEY + MAX_NOTE_SHIFT):

		warnings.append("Sample outside useful note range (%s): %s" 
		    % (samp.notename, samp.fname))
		continue

	    samp.char = None
	    gl.samps[sampfname] = samp
	    # gl.grid[samp.layer][mnote] = samp
	    gl.grid[samp.layer][mnote][rrob] = samp

    #}

    if errors:
        for msg in errors:
            print >>sys.stderr, msg
        sys.exit(1)

    if warnings:
        for msg in warnings:
            print >>sys.stderr, "Warning:", msg

    # print the samples, along with a character to assigned for
    # showing the key map in showmap().

    print >>gl.ofile, "# Samples:"

    # if we're crossfading, calculate the crossfades
    if CROSSFADE:
        prev_hivel = 0
        for layer in range(len(LAYER)):
            # fade out unless last layer
            if layer != len(LAYER)-1:
                nextl = layer + 1
                this_lovel = prev_hivel + 1
                this_hivel = LAYER[layer][LVEL]
                this_midvel = this_lovel + (this_hivel - this_lovel) / 2
                next_lovel = this_hivel + 1
                next_hivel = LAYER[nextl][LVEL]
                next_midvel = next_lovel + (next_hivel - next_lovel) / 2
                # print "==", layer, this_lovel, this_hivel, next_lovel, next_midvel
                LAYER[layer][LXFOUT_LO] = this_midvel + 1
                LAYER[layer][LXFOUT_HI] = next_midvel
                next_hivel = LAYER[nextl][LVEL]
                prev_hivel = this_hivel

            # fade in: match previous layer's fade-out
            if layer != 0:
                prevl = layer - 1
                LAYER[layer][LXFIN_LO] = LAYER[prevl][LXFOUT_LO]
                LAYER[layer][LXFIN_HI] = LAYER[prevl][LXFOUT_HI]

    sampnum = 0
    sampchars = build_sampchars()

    for layer in range(len(LAYER)-1, -1, -1):
	print >>gl.ofile, (
	    "#   Layer %*s vel %3d: "
	    % (gl.lnamelen, LAYER[layer][LNAME], LAYER[layer][LVEL])),
        for mnote in range(LO_KEY, HI_KEY+1):
	    # samps = gl.grid[layer][mnote]

	    samps = gl.grid[layer][mnote]

            if len(samps):
                # print "SAMPS ",
                # pprint.pprint(samps)
                samp = samps[next(iter(samps))]
                # print "SAMP ",
                # pprint.pprint(samp)
		if samp.char == None:
		    samp.char = sampchars[sampnum]
		    sampnum += 1
		    if sampnum >= len(sampchars):
			sampnum = 0
	        print >>gl.ofile, "%3s=%c" % (samp.notename, samp.char),
	    
	print >>gl.ofile

    print >>gl.ofile

def window(row, col, bounds):
    row_min = bounds[0]
    row_max = bounds[1]
    col_min = bounds[2]
    col_max = bounds[3]

    row_lo = max(row - MAX_LAYER_SHIFT, row_min)
    row_hi = min(row + MAX_LAYER_SHIFT, row_max)
    col_lo = max(col - MAX_NOTE_SHIFT, col_min)
    col_hi = min(col + MAX_NOTE_SHIFT, col_max)

    return (row_lo, row_hi, col_lo, col_hi)


def distance(torow, tocol, fromrow, fromcol):
    row_dist = (abs(torow - fromrow) * LAYER_SHIFT_COST) * 2
    col_dist = (abs(tocol - fromcol) * NOTE_SHIFT_COST) * 2

    if torow > fromrow and EXTEND_LAYER_UP:
        row_dist += 1
    elif torow < fromrow and not EXTEND_LAYER_UP:
        row_dist += 1
   
    if tocol > fromcol and EXTEND_NOTE_UP:
        col_dist += 1
    elif tocol < fromcol and not EXTEND_NOTE_UP:
        col_dist += 1

    # print "(", fromrow, fromcol, ")",
    # print torow, fromrow, "=>", row_dist, "|", tocol, fromcol, "=>", col_dist
    return col_dist + row_dist

def sname(samp):
    return "%s-%s" % (samp.layername, samp.notename)

def assign_keys():
    global gl

    # fix bounds of search
    row_min = 0
    row_max = len(LAYER)-1
    col_min = LO_KEY
    col_max = HI_KEY

    bounds = (row_min, row_max, col_min - MAX_NOTE_SHIFT, col_max + MAX_NOTE_SHIFT)
    keymap = []
    build_grid(keymap)

    for row in range(row_min, row_max+1):
    #{
	# set initial window for this row pass
	win = window(row, col_min, bounds)

	# load initial neighbors.  Omit rightmost column (they're added below)

	neighbors = []	# (samp, row, col)

	col = 0
        # note: rr here means row, not RR (round-robin)
	for rr in range(win[0], win[1]+1):
	    for cc in range(win[2], win[3]):
                # note that nbr is a collection of RR notes
		nbr = gl.grid[rr][cc]
		if nbr:
		    # print "init:", sname(next(iter(nbr)))
		    neighbors.append((nbr, rr, cc))

        for col in range(col_min, col_max+1):
	#{
	    # set new window
	    win = window(row, col, bounds)

	    # add new neighbors at right of window
	    cc = win[3]
	    for rr in range(win[0], win[1]+1):
	        nbr = gl.grid[rr][cc]
		if nbr and len(nbr) > 0:
		    # print "new: ", rr, cc, sname(next(iter(nbr)))
		    neighbors.append((nbr, rr, cc))

	    # Visit neighbors.
	    # Discard any neighbors in old left column.
	    # Go backwards to make deletion easy
	    # Calculate distance and find closest neighbor.

	    bestdist = 9999
	    bestnbr = None

	    # print jmidi.mnote_name(col), len(neighbors), col, win
	    if len(neighbors) == 0:
	        ### print >>sys.stderr, " -- No neighbors for layer", row, "key", col
		pass
	    for nbrix in range(len(neighbors)-1, -1, -1):
	        (nbr, rr, cc) = neighbors[nbrix]
		if cc < win[2]:
		    del neighbors[nbrix]
		    continue
		
		dist = distance(rr, cc, row, col)
		# print "  ", row, col, rr, cc, ":", dist,
		if dist < bestdist:
		    bestnbr = nbr
		    bestdist = dist

	    keymap[row][col] = bestnbr
	#}
    #}

    gl.grid = keymap


def showmap(grid, layerdata):

    # Generate heading showing "piano keyboard" in three lines:
    # first line is octave number
    # second line is key name, omitting sharp or flat
    # third line is "b" for flats and " " for naturals
    #
    # Example:
    #    111111111111222222222222333333333333444444444444...
    #    CDDEEFGGAABBCDDEEFGGAABBCDDEEFGGAABBCDDEEFGGAABB...
    #     b b  b b b  b b  b b b  b b  b b b  b b  b b b ... 

    line1 = line2 = line3 = ""
    for col in range(LO_KEY, HI_KEY+1):
        notename = jmidi.mnote_name(col, pad=None)
	line2 += notename[0]
	if notename[1] == "b":
	    line3 += "b"
	    octave = notename[2]
	else:
	    line3 += " "
	    octave = notename[1]
	line1 += octave

    # print "keyboard"
    print >>gl.ofile, "#", line1
    print >>gl.ofile, "#", line2
    print >>gl.ofile, "#", line3
    print >>gl.ofile, "#"

    # print key assignments

    for row in range(len(layerdata)-1, -1, -1):
	line = ""
    	for col in range(LO_KEY, HI_KEY+1):
	    # samp = gl.grid[row][col]
	    samps = gl.grid[row][col]
	    if samps and len(samps):
                samp = samps[next(iter(samps))]
		if samp.layer == row and samp.mnote == col:
		    line += " "
                elif samp.char:
		    line += samp.char
		else:
		    line += "!"
	    else:
		line += "!"
	print >>gl.ofile, (
	    "# %s Layer %-6s v=%03d"
	    % (line, layerdata[row][LNAME], layerdata[row][LVEL]))

    print >>gl.ofile, "#"
    print >>gl.ofile, "#  Key:"
    print >>gl.ofile, "#    space = unity-mapped key"
    print >>gl.ofile, "#    !     = unmapped key"
    print >>gl.ofile, "#    anything else: see sample layer list above"


def emit_keymap(samps, keyLo, keyHi):

    if False:
        # inhibit RR ########
        sampkey = next(iter(samps))
        sampval = samps[sampkey]
        samps = {sampkey:sampval}

    rr_count = len(samps)
    rr_num = 0
    if rr_count > 1:
        rr_frac = 1.0/rr_count
    for samp in samps.values():
        print >>gl.ofile, "  SAMP:%s:%d:%d:%d:\t(%3s - %3s)" % (
            samp.fname, keyLo, keyHi, samp.mnote,
            jmidi.mnote_name(keyLo, None),
            jmidi.mnote_name(keyHi, None))

        print >>gl.sfzf, "<region>", 
        print >>gl.sfzf, "sample=%s" % samp.fname,
        if keyLo == samp.mnote and keyHi == samp.mnote:
            print >>gl.sfzf, "key=%-3s" %jmidi.mnote_name(samp.mnote, None),
        else:
            print >>gl.sfzf, "lokey=%-3s" % jmidi.mnote_name(keyLo, None),
            print >>gl.sfzf, "hikey=%-3s" % jmidi.mnote_name(keyHi, None),
            print >>gl.sfzf, "pitch_keycenter=%-3s" %jmidi.mnote_name(samp.mnote, None),

        # programmed release times based on MIDI note
        # %%% todo: interpolate!
        for (relnote, relval) in RELEASE_RANGES:
            if keyLo >= relnote:
                print >>gl.sfzf, "ampeg_release=%s" % relval,
                break

        # random round-robins
        if rr_count > 1:
            print >>gl.sfzf, "lorand=" + str(rr_frac * rr_num),
            print >>gl.sfzf, "hirand=" + str(rr_frac * (rr_num+1)),
            rr_num += 1

        print >>gl.sfzf


def cB2scalefactor(cb):
    return (pow(10.0, cb/200.0))

def emit_map(grid, layerdata):

    print >>gl.ofile
    print >>gl.ofile, "BANKNAME:%s" % BANKNAME
    print >>gl.ofile, "DESIGNER:%s" % DESIGNER
    print >>gl.ofile, "COPYRIGHT:%s" % COPYRIGHT
    print >>gl.ofile, "COMMENT:%s" % COMMENT

    print >>gl.ofile
    print >>gl.ofile, "PRESET:%s" % PRESETNAME
    print >>gl.ofile
    print >>gl.ofile, "RELEASE:%s" % RELEASE

    loVel = 1
    # LOWEST_LEVEL = 640	# centibels	%%% SHOULD BE CONFIGURED
    lprevl = LOWEST_LEVEL

    if len(SFZ_HEADERS):
        # print "HEADERS:", SFZ_HEADERS
	print >>gl.sfzf, "\n".join(SFZ_HEADERS)
        print >>gl.sfzf

    if len(SFZ_CONTROLS):
        # print "CONTROLS:", SFZ_CONTROLS
        print >>gl.sfzf, "<control>"
	print >>gl.sfzf, "\n".join(SFZ_CONTROLS)
        print >>gl.sfzf

    if len(SFZ_MASTERS):
        # print "MASTERS:", SFZ_MASTERS
        print >>gl.sfzf, "<master>"
	print >>gl.sfzf, "\n".join(SFZ_MASTERS)

    for row in range(0, len(layerdata)):
    #{
	hiVel  = layerdata[row][LVEL]
	latten = layerdata[row][LATTEN]
	llevel = layerdata[row][LLEVEL]
        xfin_lo = layerdata[row][LXFIN_LO]
        xfin_hi = layerdata[row][LXFIN_HI]
        xfout_lo = layerdata[row][LXFOUT_LO]
        xfout_hi = layerdata[row][LXFOUT_HI]

	print >>gl.ofile
        print >>gl.ofile, "VLAYER:%s:%3d:%3d:%2d" % (
	    layerdata[row][LNAME], loVel, hiVel, latten)	# %%% llevel

	print >>gl.sfzf
	print >>gl.sfzf, "<group>",
        if xfin_lo:
            print >>gl.sfzf, "xfin_lovel=%d xfin_hivel=%d" % (xfin_lo, xfin_hi),
        else:
            print >>gl.sfzf, "lovel=%d" % loVel,
        if xfout_lo:
            print >>gl.sfzf, "xfout_lovel=%d xfout_hivel=%d" % (xfout_lo, xfout_hi),
        else:
            print >>gl.sfzf, "hivel=%d" % hiVel, 

	if (latten != 0):
	    print >>gl.sfzf, "volume=%f" % (-latten/10.0)
	print >>gl.sfzf, "ampeg_release=%f" % RELEASE

	if (llevel != 0):
	    midVel = (hiVel + loVel) / 2
	    midLev = (llevel + lprevl) / 2
	    print >>gl.sfzf, "amp_velcurve_%d %f" % (loVel,  cB2scalefactor(-lprevl))
	    print >>gl.sfzf, "amp_velcurve_%d %f" % (midVel, cB2scalefactor(-midLev))
	    print >>gl.sfzf, "amp_velcurve_%d %f" % (hiVel,  cB2scalefactor(-llevel))

	    print ("row %s velocity %3d level %3d cB, scale %f"
	        % (layerdata[row][LNAME], loVel,  lprevl, cB2scalefactor(-lprevl)))
	    print ("row %s velocity %3d level %3d cB, scale %f"
	        % (layerdata[row][LNAME], midVel, midLev, cB2scalefactor(-midLev)))
	    print ("row %s velocity %3d level %3d cB, scale %f"
	        % (layerdata[row][LNAME], hiVel,  llevel, cB2scalefactor(-llevel)))
	    lprevl = llevel

	lastSamps = None

    	for col in range(LO_KEY, HI_KEY+1):
	#{
	    samps = gl.grid[row][col]
	    if samps != lastSamps:
	        if lastSamps != None:
                    emit_keymap(lastSamps, firstKey, col-1)
		lastSamps = samps
		firstKey = col
	#}

	# handle last unfinished keymap
	if lastSamps != None:
	    emit_keymap(lastSamps, firstKey, col)

        loVel = hiVel + 1
    #}

    if len(SFZ_FINALS):
        # print "FINALS:", SFZ_FINALS
        print >>gl.sfzf
	print >>gl.sfzf, "\n".join(SFZ_FINALS)
        print >>gl.sfzf



def convert_int(val, lineno):
    try:
        ival = int(val)
    except:
        print >>sys.stderr, (
	    "Line %d: expecting integer, got '%s'"
	    % (lineno, val))
	sys.exit(1)
    return (ival)

def kwval(group, lineno):

    try:
        (kw, val) = group.split("=")
    except Exception, msg:
        print >>sys.stderr, (
	    "Line %d: expecting 'keyword=value' format, got '%s'"
	    % (lineno, group))
        print >>sys.stderr, msg
	raise Exception
	sys.exit(1)
    return (kw, val)

def process_cfg(cfg_fname, sfname):
#{
    global LAYER_LOC, NOTE_LOC
    global BANKNAME, DESIGNER, COPYRIGHT, COMMENT
    global LO_KEY, HI_KEY
    global MAX_LAYER_SHIFT, LAYER_SHIFT_COST, EXTEND_LAYER_UP
    global MAX_NOTE_SHIFT, NOTE_SHIFT_COST, EXTEND_NOTE_UP
    global PRESETNAME, RELEASE, LAYER
    global LOWEST_LEVEL
    global gl
    global SFZ_HEADERS
    global SFZ_MASTERS
    global SFZ_CONTROLS
    global SFZ_FINALS
    global CROSSFADE
    global TRANSPOSE

    try:
	cfgf = file(cfg_fname, "r")
    except Exception, msg:
	print >>sys.stderr, msg
	sys.exit(1)

    # Defaults
    COMMENT = ""
    BANKNAME = sfname
    PRESETNAME = BANKNAME
    DESIGNER = ""
    CROSSFADE = False
    COPYRIGHT = ""
    RELEASE = 0.1
    SFZ_HEADERS = []
    SFZ_CONTROLS = []
    SFZ_MASTERS = []
    SFZ_FINALS = []

    # entry structure - list of:
    #  lname	name
    #  lvel	velocity
    #  lrange	velocity range
    #  latten	sf attenuation for layer (obsolete?)
    #  llevel	amount layer was boosted by when normalized.
    #          	  If zero, velocity curve adjustment not done.

    layers = []

    lvmode = None

    lineno = 0
    for iline in cfgf.readlines():
    #{
        line = jtrans.tr(iline.strip(), "\t", " ")
	lineno += 1

	# skip blank line or comment
	if len(line) == 0 or line[0] == "#":
	    continue

        # print >>sys.stderr, line 

	groups = line.split(" ")
	cmd = groups[0]
	for ix in range(len(groups)-1, -1, -1):
	    if len(groups[ix]) == 0:
	        del groups[ix]

	if cmd == "bankname":
	    BANKNAME = " ".join(groups[1:])
	    PRESETNAME = BANKNAME	# default
	    continue

	if cmd == "designer":
	    DESIGNER = " ".join(groups[1:])
	    continue

	if cmd == "copyright":
	    COPYRIGHT = " ".join(groups[1:])
	    continue

	if cmd == "comment":
	    COMMENT += " ".join(groups[1:])
	    continue

	if cmd == "preset":
	    if len(groups) >= 2:
		PRESETNAME = " ".join(groups[1:])
	    continue

        if cmd == "crossfade":
            CROSSFADE = True
            continue

        if cmd == "release":
	    if len(groups) < 2:
	        print >>sys.stderr, (
		    "Line %d: expecting release value."
		    % (lineno))
		sys.exit(1)
	    val = groups[1]
	    try:
		relval = float(val)
	    except:
	        print >>sys.stderr, (
		    "Line %d: expecting float value for release time, got '%s'."
		    % (lineno, val))
		sys.exit(1)
            if len(groups) == 3:
                # note range release level (note given is low note of range)
                val = groups[2]
                try:
                    relnote = int(val)
                except:
                    print >>sys.stderr, (
                        "Line %d: expecting int (midi note) value for release note, got '%s'."
                        % (lineno, val))
                    sys.exit(1)
                RELEASE_RANGES.append((relnote, relval))

            else:
                # global release level
		RELEASE = float(val)

	    continue

	if cmd == "transpose":
	    TRANSPOSE = int(groups[1])
            print >>sys.stderr, "TRANSPOSE by", TRANSPOSE

	if cmd == "header":
	    SFZ_HEADERS.append(" ".join(groups[1:]))

	if cmd == "control":
	    SFZ_CONTROLS.append(" ".join(groups[1:]))

	if cmd == "global" or cmd == "master":
	    SFZ_MASTERS.append(" ".join(groups[1:]))

	if cmd == "final":
	    SFZ_FINALS.append(" ".join(groups[1:]))

	if cmd == "layer-opts":
	    for group in groups[1:]:
	        if len(group) == 0:
		    continue

		(kw, val) = kwval(group, lineno)

		if kw == "max-shift":
		    MAX_LAYER_SHIFT = convert_int(val, lineno)

		elif kw == "shift-cost":
		    LAYER_SHIFT_COST = convert_int(val, lineno)

		elif kw == "extend-up":
		    if val.upper() == "Y":
			EXTEND_LAYER_UP = True
		    else:
			EXTEND_LAYER_UP = False	    continue

	if cmd == "note-opts":
	    for group in groups[1:]:
	        if len(group) == 0:
		    continue

		(kw, val) = kwval(group, lineno)

		if kw == "max-shift":
		    MAX_NOTE_SHIFT = convert_int(val, lineno)

		elif kw == "shift-cost":
		    NOTE_SHIFT_COST = convert_int(val, lineno)

		elif kw == "extend-up":
		    if val.upper() == "Y":
			EXTEND_NOTE_UP = True
		    else:
			EXTEND_NOTE_UP = False
	    continue


	if cmd == "keyboard-range":
	    for group in groups[1:]:
	        if len(group) == 0:
		    continue

		(kw, val) = kwval(group, lineno)

		if kw == "low-key":
		    key = jmidi.notenum(val)
		    if key == None:
		        print >>sys.stderr, (
			    "Line %d: expecting note name, got '%s'."
			    % (lineno, val))
			sys.exit(1)
		    LO_KEY = key
		    # print >>sys.stderr, "LO_KEY", key

		elif kw == "high-key":
		    key = jmidi.notenum(val)
		    if key == None:
		        print >>sys.stderr, (
			    "Line %d: expecting note name, got '%s'."
			    % (lineno, val))
			sys.exit(1)
		    HI_KEY = key
	    continue

	# sample filename format (the parts we need to know)

	if cmd == "format":
	    for group in groups[1:]:

		(kw, val) = kwval(group, lineno)

		if kw == "layer-loc":
		    ival = convert_int(val, lineno)
		    if ival > 0:
		        ival -= 1
		    LAYER_LOC = ival

		elif kw == "note-loc":
		    ival = convert_int(val, lineno)
		    if ival > 0:
		        ival -= 1
		    NOTE_LOC = ival
	    continue

	if cmd == "lowest-level":
	    LOWEST_LEVEL = convert_int(groups[1], lineno)
	    if (LOWEST_LEVEL < 0):
	        print >>sys.stderr, ("Line %d: lowest-level must not be negative."
		    % (lineno, groups[1:]))
	    print "LOWEST_LEVEL", LOWEST_LEVEL
	    continue

	if cmd == "layer":
	    if len(groups) < 2:
		print >>sys.stderr, (
		    "Line %d: expecting layer name."
		    % (lineno))
		sys.exit(1)

	    lname	= groups[1]
	    latten	= 0
	    llevel	= 0	# no adjustment
	    lvel	= -1
	    lrange	= -1

	    gl.lnamelen = max(gl.lnamelen, len(lname))

	    for group in groups[2:]:
	        if len(group) == 0:
		    continue

		(kw, val) = kwval(group, lineno)

		if kw == "vel":
		    if lvmode and lvmode != "vel":
			print >>sys.stderr, (
			    "Line %d: can't mix 'vel' and 'vel-range' in same preset."
			    % (lineno))
			sys.exit(1)
		    lvel = convert_int(val, lineno)
		    lvmode = "vel"

		elif kw == "vel-range":
		    if lvmode and lvmode != "range":
			print >>sys.stderr, (
			    "Line %d: can't mix 'vel' and 'vel-range' in same preset."
			    % (lineno))
			sys.exit(1)
		    lrange = convert_int(val, lineno)
		    lvmode = "range"

		elif kw == "atten":
		    latten = convert_int(val, lineno)

		elif kw == "level":
		    llevel = convert_int(val, lineno)

	    layers.append((lname, lvel, lrange, latten, llevel))

	    continue
    #}

    # Are we assigning velocities?

    if lvmode == "vel":

        # No.  Check the assignments.
	last_lvel = -1
	for (lname, lvel, lrange, latten, llevel) in layers:
	    if lvel == -1:
		print >>sys.stderr, (
		    "No velocity assigned for layer '%s'" 
		    % lname)
		sys.exit(1)
	    if lvel <= last_lvel:
		print >>sys.stderr, (
		    "Velocity for layer '%s' must be higher than previous layer" 
		    % lname)
		sys.exit(1)
	    last_lvel = lvel

	if last_lvel != 127:
	    print >>sys.stderr, (
		"Warning: velocity for top layer '%s' should be 127" 
		% lname)

    else:
    #{
	# We're assigning velocities.

	# Find how many layers need ranges assigned,
	# and how much room is left
	count = 0
	unused  = 127
	for (lname, lvel, lrange, latten, llevel) in layers:
	    if lrange == -1:
	        count += 1
	    else:
	        unused -= lrange

	if unused < 0:
	    print >>sys.stderr, "Total of velocity ranges must not exceed 127"
	    sys.exit(1)

	# allocate unused velocity range to layers without vel-range specs
	ix = 0
	for (lname, lvel, lrange, latten, llevel) in layers:
	    if lrange == -1:
	        lrange = unused / count
		count -= 1
		unused -= lrange
		layers[ix] = (lname, lvel, lrange, latten, llevel)
	    ix += 1

	# assign specific max velocities to each
	ix = 0
	last_lvel = 0
	for (lname, lvel, lrange, latten, llevel) in layers:
	    last_lvel += lrange
	    layers[ix] = (lname, last_lvel, lrange, latten, llevel)
	    print >>sys.stderr, (
	        "Layer %*s: velocity %3d, range %3d, level %3d"
		% (gl.lnamelen, lname, last_lvel, lrange, llevel))
	    ix += 1

    #}

    # build LAYER array
    for (lname, lvel, lrange, latten, llevel) in layers:
	LAYER.append([lname, lvel, latten, llevel, 0, 0, 0, 0])

#}



# Module initialization

def usage(prog):
    print >>sys.stderr
    print >>sys.stderr, "%s: create keyboard map for building a soundfont" % prog
    print >>sys.stderr
    print >>sys.stderr, "usage: %s <sfname> {sampfile}" % prog
    print >>sys.stderr
    print >>sys.stderr, "  where:"
    print >>sys.stderr, "     <sfname>   specifies input and output:"
    print >>sys.stderr, "                   <sfname>.sfc is the input (config),"
    print >>sys.stderr, "                   <sfname>.sfk is the output (keymap)."
    print >>sys.stderr, "     {sampfile} is any number of sample filenames, with UNIX wildcards"
    print >>sys.stderr, "     mapfile    is the output file name"
    print >>sys.stderr
    print >>sys.stderr, "  Output is ASCII text, and includes a char-graphic keyboard map layout"
    print >>sys.stderr
    sys.exit(1)




# Main

if __name__ == "__main__":
    global CROSSFADE
    global TRANSPOSE
    TRANSPOSE = 0

    args = sys.argv
    prog = args[0].split("\\")[-1]
    del args[0]

    if len(args) < 2:
        usage(prog)
	sys.exit(1)

    sfname = args[0]
    del args[0]

    ofname = sfname + ".sfk"
    cfname = sfname + ".sfc"
    zfname = sfname + ".sfz"

    try:
	gl.ofile = file(ofname, "w")
	gl.sfzf  = file(zfname, "w")
    except Exception, msg:
	print >>sys.stderr, msg
	sys.exit(1)

    print >>sys.stderr, "Input (control) file:", cfname
    print >>sys.stderr, "Output (keymap) file:", ofname
    print >>sys.stderr, "Output (sfz)    file:", zfname

    process_cfg(cfname, sfname)
    build_grid(gl.grid)
    load_filenames(args)
    assign_keys()

    if CROSSFADE:
        emit_map(gl.grid, LAYER)

        zfname = sfname + "-no-xfade.sfz"
        print >>sys.stderr, "Output-nx (sfz) file:", zfname
        try:
            gl.sfzf  = file(zfname, "w")
        except Exception, msg:
            print >>sys.stderr, msg
            sys.exit(1)

        gl.grid = []
        gl.samps = {}
        LAYER = []
        process_cfg(cfname, sfname)
        CROSSFADE = False
        build_grid(gl.grid)
        load_filenames(args)
        assign_keys()

    # These are no longer needed now that we don't support .sf2,
    # but the keymap might be nice to look at
    showmap(gl.grid, LAYER)
    emit_map(gl.grid, LAYER)


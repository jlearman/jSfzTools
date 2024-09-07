# equivalent of unix "tr"

import string

def tr(inp, fromstr, tostr, deletechars=""):

    if len(tostr) < len(fromstr):
        pad = tostr[-1]
        while len(tostr) < len(fromstr):
            tostr += pad
    ret = inp.translate(inp.maketrans(fromstr, tostr))
    ret = ret.translate(ret.maketrans("", "", deletechars))
    return ret

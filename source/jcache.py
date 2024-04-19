#!/usr/local/bin/python
# disk cacher
#
# Keeps "archive" folder trees identical to "active" ones.
#
# Rules:
#   If active files are newer or don't exist on archive, copy it.
#   If archive file exists but active doesn't, delete it.
#   If archive folder exists but active doesn't, do nothing.

import sys
import os
import os.path
import stat
import shutil
import string
import time
import msvcrt
import win32api

import jtrans



class Quit(Exception):
    def __init__(self, val):
        self.value = val
    def __str__(self):
        return (str(self.value))


NO   = 0
YES  = 1
A    = 3
QUIT = 4

def ynaq(question, dflt="y", aprompt=None, echo=False):
    if aprompt == None:
        aprompt = ""
    else:
        aprompt = "=" + aprompt

    answer = None
    while answer == None:
        print question, "(y,n,a%s,q) [%s]? " % (aprompt, dflt),
        answer = string.lower(msvcrt.getch())
        if answer == "\r":
            answer = dflt
        if answer == "y":
        rc = YES
        elif answer == "n":
        rc = NO
        elif answer == "a":
        rc = A
        elif answer == "q":
        if echo:
        msvcrt.putch(answer)
        print
            raise Quit("user quit")
        else:
            msvcrt.putch(answer)
            answer = None
            print

    if echo:
    msvcrt.putch(answer)
    print
    
    return rc

def yn(question, dflt="y", echo=False):
    answer = None
    while answer == None:
        print question, "(y,n) [%s]? " % dflt,
        answer = string.lower(msvcrt.getch())
        if answer == "\r":
            answer = dflt
        if answer == "y":
        rc = True
        elif answer == "n":
        rc = False
        else:
            msvcrt.putch(answer)
            answer = None
            print

    if echo:
    msvcrt.putch(answer)
    print

    return rc
    
def chr_combine(ins, ch):
    outs = ""
    match = False
    for c in ins:
        if c == ch:
            if match:
                continue
            match = True
        else:
            match = False
        outs += c
    return outs

def skippedDestDir(dstdir):
    for dir in SkippedDirs:
        if dstdir.startswith(dir):
        return True
    return False

def addSkippedDestDir(dstdir):
    SkippedDirs.append(dstdir)


Verbose = False

def backup(srcroot, dstroot, srcdir, dirs, srcfiles):
    global Copymode
    global Delmode

    check_for_deletes = True
    reldir = srcdir.replace(srcroot, "", 1)
    dstdir = dstroot + reldir
    if Verbose:
        print srcdir, "->", dstdir

    # create dstdir if necessary

    if (not os.path.exists(dstdir)):

    if skippedDestDir(dstdir):
        print "  SKIPPED:", dstdir
        return

    print "  NEW DIR:", dstdir,
        try:
            if Copymode == NO:
                print "(no)"
        addSkippedDestDir(dstdir)
                return
            if Copymode == A:
                ans = ynaq("", "y")
                if ans == NO:
                    print "no"
            addSkippedDestDir(dstdir)
                    return
                if ans == A:
                    Copymode = YES

            os.mkdir(dstdir)
        print "(ok)"
            check_for_deletes = False
        except IOError:
        print "(err)"
            print >>sys.stderr, "Can't create dir: %s:", IOError
            return(False)
    
    # copy any newer files
    for fname in srcfiles:
        srcfname = srcdir + "/" + fname
        dstfname = dstdir + "/" + fname
        copy = False
    srcstat = os.stat(srcfname)
        try:
            dststat = os.stat(dstfname)
        except OSError:
            print "  MISSING:", srcfname,
            copy = True
        else:          
            if srcstat[stat.ST_MTIME] > dststat[stat.ST_MTIME]:
                print "  NEWER:  ", srcfname,
                copy = True
        if copy:
            if Copymode == NO:
                print "(no)"
                continue
            if Copymode == A:
                ans = ynaq("", "y")
                if ans == NO:
                    print "no"
                    continue
                if ans == A:
                    Copymode = YES
            try:
                shutil.copy(srcfname, dstfname)
            except IOError, msg:
                print >>sys.stderr, "Error:", msg
        else:
        try:
            os.utime(dstfname, (srcstat[stat.ST_ATIME], srcstat[stat.ST_MTIME]))
        except OSError, msg:
            print >>sys.stderr, "\n  Warning: can't set time: ", msg
        print " (ok)"

    # delete any files on dst that aren't on src
    ii = 0
    if not check_for_deletes:
        return
    
    dstfiles = os.listdir(dstdir)
    srcfiles.sort()
    dstfiles.sort()
    
    for dfile in dstfiles:
        delete = False
        dstpath = dstdir + "/" + dfile

        if os.path.isdir(dstpath):
            continue
        if ii >= len(srcfiles):
            delete = True
        elif dfile == srcfiles[ii]:
            ii += 1
            continue
        elif dfile < srcfiles[ii]:
            delete = True

        if delete:
            print "  DELETE: ", dstpath,
            if Delmode == NO:
                print "(no)"
                continue
            if Delmode == A:
                ans = ynaq("", "y")
                if ans == NO:
                    print "no"
                    continue
                if ans == A:
                    Delmode = YES

            os.unlink(dstpath)
            print "(ok)"
    
    return(False)


def copydel():

    line = ""

    try:
        cfg_file = file(cfg_file_name, "r")
    except:
        print >>sys.stderr, "Can't open config file,", cfg_file_name
        sys.exit(1)

    for line in cfg_file:
        
        line = line.strip()
        if line.startswith("#"):
            continue

        if line == "":
            continue

        line = jtrans.tr(line, "\t", " ")
        # line = chr_combine(line, " ")
    try:
        (act, arch) = line.split("|")
    except ValueError, err:
        print "Invalid config line: no '|' or too many:"
        print line
        if not yn("Continue", "n"):
            raise Quit("User Quit")

    act  = act.strip()
    arch = arch.strip()
    if Backup:
        dest = arch
        src  = act
    else:
        dest = act
        src  = arch

        print "%s --> %s" % (src, dest)

    found_files = False
    for (root, dirs, files) in os.walk(src):
        found_files = True
        if (backup(src, dest, root, dirs, files)):
        return
    if not found_files:
        print >>sys.stderr, "Can't open source dir '%s'" % act
        if not yn("Continue with subsequent lines", "n"):
        raise Quit("User Quit")


def get_parms():
    global Copymode
    global Delmode
    global Backup

    Backup = yn("Backup? ('n' to restore)", "y", echo=True)
    Copymode = ynaq("Copy newer files to destination", "y", "ask", echo=True)
    Delmode = ynaq("Delete destination files missing in source folders", "n", "ask", echo=True)

def init():
    global cfg_file_name
    global Deleting
    global Copying
    global SkippedDirs

    cfg_file_name = "C:/jcache.cfg"
    Deleting = False
    Copying  = False
    SkippedDirs = []

def main():

    title = win32api.GetConsoleTitle()
    print

    done = False
    while not done:

    init()
        try:
            get_parms()
            print
            copydel()

        except Quit:
            pass
        
        print

        if title.endswith("python.exe"):
            print "Note: When you quit, this window will disappear."
            
        answ = yn("Start again", "n", echo=True)
        print 
        if answ == NO:
            done = True

main()


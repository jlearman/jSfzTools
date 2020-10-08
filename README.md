# jSfzTools - python tools to create sfz samplesets

Jeff's SFZ tools
Copyright 2006, Jeff Learman

No warranties.  Programs are likely to be fragile, especially
when taken outside the narrow range of test scenarios I've used!

Also, don't expect good coding.  I wrote most of this long ago
when I was new to Python.

# Overview

These tools include two programs that assist in taking a set of
samples for an instrument and building an sfz format sample set.

The first tool, jCutSamps.py, takes one or more "layer" files,
where each layer file is a recording of samples of different
notes, all at the same velocity (dynamics, e.g., all mf or all
pp), and chops them into files with one sample per file.
It detects the pitchh of each note and puts the MIDI note
number and note name in the name of each file.

(I'm considering an option to pre-specify the notes, which
would be used when converting layer files recorded using MIDI,
where you know the notes a-priori.)

The second tool, jMap.py, takes the output of the first program
(all the single-note sample files) and a small text control file,
and builds an SFZ sampleset, automatically mapping the samples
to the notes and velocity ranges.

It works best using 16-bit source (layer) files.  I have tested
it using 44.1kHz and 48kHz.  It also works best when you do any
noise reduction on each layer file, though this is optional.
This shouldn't be necessary when sampling a digital keyboard or
plugin.

I have only used this under Windows.  I don't remember if there
are any Windows dependencies; it should work under Linux or Mac.
If it does have a Windows dependency, it should be limited to
file globbing in the main sections of the two main tools.

# Getting started

Things you'll need:
* A way to capture the wave data (mike, soundcard, etc.)
* A wave editor -- optional but useful for noise reduction or bit depth conversion.
* Python, download it from www.python.org and install it.  (Python
 is a scripting language like Perl.)  You may need to add it to your PATH.
* A little ability to use the DOS command shell.
* A fair measure of patience and motivation (not just to use these tools, but to create a good sample set!)

Installation:
    Extract all the .py files into a new directory of your choice.
    Put that directory on your executable path, or else you
	can specify the path to the programs explicitly.

A note on terminology:
    I'm using the term "layer" only for the purpose of what
    more sensible folks call "velocity splits", meaning a set
    of samples that were recorded with the same key velocity
    (or force or loudness).  I'm NOT using it to refer to
    "layered instruments", where you have two sounds from
    two different instruments when you hit one key.

You may find the word "soundfont" where I haven't fixed it.
The tools originally created a .sf2 result, but that is no
longer supported.

# Instructions

To build your own sfz sampleset:

## Sample the instrument.

For each velocity layer, sample all keys you'll be sampling
into a single wave file.  The tools currently don't handle
two .wav files for the same velocity layer -- if you do end
up with more than one, use a wave editor to combine them into
one.  Ideally, sample in 24 bits.

Do not adjust the recording gain (record level) when recording
a layer.

You might want to read about layer file names below before
starting this step.

## Prepare the velocity layer files

De-noise the layer files in your favorite wave editor, such
as CoolEdit or (free) Audacity.  Then normalize, and convert
to 16 bit format if they aren't already.  Dithering optional
but probably best.

If there are any snarks (sample attempts you don't want to
keep) that are longer than the minimum sample duration
(a configurable parameter in jCutSamps.py, defaulting to
1 sec.), delete them from the layer wave file.  It's better
to delete them rather than silence them, because the "silence"
is sampled to help detect the end of a note, and a chunk of
absolute silence can throw the algorithm off.

Snarks smaller than the minimum sample duration will be
automatically ignored by the program.

Use the following format for the prepared layer file names:

    <prefix>_<layername>.wav

where \<prefix> is anything you want, usually an abbreviation
for the soundfont or instrument.  \<layername> is also anything
you want, but something that indicates to you what velocity
the layer file samples were recorded at.

Examples for different layer file naming conventions:

* using MIDI velocities:
  * sf1_v16.wav sf1_v32.wav sf1_v64.wav ...
* using music notation:
  * sf1_pp.wav sf1_p.wav sf1_mp.wave sf1_m.wave sf1_mf.wav ...
* using whatever:
  * sf1_soft.wav, sf1_medium.wav, sf1_hard.wav, sf1_nuke.wav

Use anything that's meaningful to you, but the layer names will
show up later.  The prefix will simply be preserved by the
program and doesn't mean anything specific.

## Convert the layer files to individual sample files.

Run jCutSamps.py to chop up the layer files into sample files.
It produces a set of closely cropped sample files, suitable
for building into a soundfont.  Furthermore, it names them
according to this schema:

`<prefix>_<layer>_<notenum>_<notename>.wav`

where

* \<prefix> is as described above.
* \<layer> is as described above.
* \<notenum> is the MIDI note number in the sample, or 000 if it can't tell.
* \<notename> is the note name in normal notation, using upper case for the note, lower case 'b' to indicate flat, and a one-digit octave number in normal MIDI parlance.

The program does not handle samples outside the range of an
88-key piano keyboard.  As you can imagine, it's also not
intended for percussion instruments and drums where the MIDI
note isn't related to pitch.  (It will cut these up, but
the won't be named very effectively, and the subsequent
steps won't work unless you manually rename the cut-up
sample files according to the schema above.)

The pitch detection algorithm (auto-correlation) isn't the
best algorithm, so it's touchy.  Let me know if it tends to
work or not for your instrument.  It seems to work well for
acoustic piano, Rhodes, and bass.

It's generally best to put all the samples in a single folder.
Keep different instruments in different folders.  For this
example, we'll keep the chopped samples in a "samps" directory,
and the input wave files in the current directory (along with
the soundfont and other control files).

Example:
    mkdir samps
    jCutSamps -f samps sf1_*.wav

Get a cup of coffee.  This one takes a long time, about 30
seconds per sample in my sample sets, running on a 2GHz
P4 or 2.1GHz Centrino.

When it's done, inspect the sample names.  If you have samples
with note number 000, figure out what note they really are
and name them accordingly.  It's not necessary to get the MIDI
note number correct -- it's not used by the program.

# Configure the keyboard mapping.

Create a file that's your soundfont name but with a ".sfc" extension,
for "soundfont control".  See details in the example provided.

# Build the keyboard map and .sfz file

Example:
* `jMap.py sf1 samps/*.wav`

This reads the control file (sf1.sfc) and, based on the names of
the wave files found, creates a key map file (sf1.sfk).
Take a look at the file it created to see if that's
how you want your samples mapped.  Adjust accordingly.
This completes almost immediately.  It does verify that the
specified sample files exist, but doesn't inspect their contents.
It trusts the file names to specify the note.

This step now also creates the 'sfz' format file (sf1.sfz), which
(together with the cut-up sample files) can be used by any sfz-
format-capable sample player or converter.  Note that you can
also edit the sfz file with any text editor.  Find more details
about this format at http://sfzformat.com .

Bingo, you're done.  Test your soundfont in your favorite player.
Make any necessary adjustments on the keymap config file and
run the second program again -- just takes a moment.

jMap.py also creates a .sfk file, a text file that shows the
keyboard map.  This was originally to control creating the
soundfont, but is now only a legacy.  But you might find it
interesting.

##  Resample everything and start over.

Most likely, you've learned what's not ideal about your sample
set.  Perhaps you needed more layers, or to sample more keys.
Adjust the layer definitions (if necessary) and start over.

##  Touch up the sample set in a sample set editor

I use Extreme Sample Converter (from http://www.extranslate.com).
It's archaic and fiddly but has the best loop editor I've seen.

Have fun!
Jeff


# kittenm4ster's MIDI to PICO-8 Tracker Translator
"It just works, sometimes!"

## Prequisites
* python 3.5

## How To Use
    main.py <yourfile.mid>
This will generate a PICO-8 cartridge called `midi_out.p8`

## Please Note
MIDI format stores music in a conceptually different way than PICO-8's tracker
does.  Because of this fundamental difference, conversion from MIDI to PICO-8
tracker format will never be 100% perfect in all cases.

Furthermore, in order to keep the scope of this program manageable, I have
chosen (at least for now) to concentrate only on conversion of a *certain type*
of MIDI file which has the following characterstics:

* Each "voice" should be on a different track
  * This also means that MIDI file format Type 0 (the format that puts all
    voices on only 1 track) is not currently supported
* Multiple notes should never be playing at the same time on the same track
* The tempo should not change during the song
* The song must have a maximum of 4 tracks
  * Any tracks past the first 4 will be excluded from the import
* The rhythms should be regular/quantized
  * This program will attempt to do a very basic level of quantization, but if
    the MIDI file has rhythms that are not very regular to begin with, the
    result will not be good and tracks will get out of sync
* It should be short enough (and/or use a low enough rhythm resolution) to fit
  within the 64 SFX banks of the PICO-8
  * The program will try to fit as much of the song in as it can, but it can't
    perform miracles
* It should not use any drums (channel 10)

TLDR:
If you use a MIDI with the right characteristics, this program can and does
produce a great result!  If you use anything else, don't be surprised if the
result is a grotesque monstrosity :)

## Bugs
There are probably lots of bugs!  This is a thing written for fun and it should
be considered to be in an "work in progress" state.

## Libraries/Special Thanks
* [picotool](https://github.com/dansanderson/picotool)
* [python3-midi-parser](https://github.com/akionux/python3-midi-parser)

## To Do List
These are things that are totally unimplemented now but that I probably will
try to implement in the future:
* The ability to manually specify which waveform to use for which track, via a
  command line argument
* The ability to manually override note duration via a command line argument
* Effects (especially putting a fadeout at the end of notes so they don't run
  together)
* An automatic best guess MIDI-instrument-to-PICO-8-waveform mapping table
* Automatic or manual combination of multiple tracks into one (in places where
  both are not playing notes at the same time)
* MIDI file type 0 support
* Drums (channel 10) support
* Tempo changes during the song

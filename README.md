# kittenm4ster's MIDI to PICO-8 Tracker Translator
"It just works, sometimes!"

## Prequisites
* python 3.5

## How To Use
    usage: awyeah.py [-h] [--legato] [--staccato] [--no-fix-octaves]
                     [--no-quantize] [-t MIDI_BASE_TICKS] [-d NOTE_DURATION]
                     [--start-offset START_OFFSET] [--no-compact]
                     [--waveform WAVEFORM WAVEFORM WAVEFORM WAVEFORM]
                     [--octave-shift OCTAVE_SHIFT OCTAVE_SHIFT OCTAVE_SHIFT OCTAVE_SHIFT]
                     [--volume-shift VOLUME_SHIFT VOLUME_SHIFT VOLUME_SHIFT VOLUME_SHIFT]
                     [--mute MUTE MUTE MUTE MUTE]
                     midiPath [cartPath]
    
    positional arguments:
      midiPath              The path to the MIDI file to be translated
      cartPath              The path to PICO-8 cartridge file to be generated
    
    optional arguments:
      -h, --help            show this help message and exit
      --legato              Disable fadeout effect at the end of any notes (even
                            repeated notes)
      --staccato            Add a fadeout effect at the end of every note
      --no-fix-octaves      Do not change octaves of tracks to keep them in PICO-8
                            range
      --no-quantize         Do not perform any quantization of note lengths
      -t MIDI_BASE_TICKS, --midi-base-ticks MIDI_BASE_TICKS
                            Override MIDI ticks per PICO-8 note setting (normally
                            auto-detected)
      -d NOTE_DURATION, --note-duration NOTE_DURATION
                            Override PICO-8 note duration setting (normally auto-
                            detected from MIDI tempo)
      --start-offset START_OFFSET
                            Change the start point in the MIDI file (in # of
                            PICO-8 SFX)
      --no-compact          Don't try to compact groups of repeated notes into
                            fewer notes played for longer
      --waveform WAVEFORM WAVEFORM WAVEFORM WAVEFORM
                            Specify which PICO-8 waveform (instrument) number to
                            use for each channel
      --octave-shift OCTAVE_SHIFT OCTAVE_SHIFT OCTAVE_SHIFT OCTAVE_SHIFT
                            Specify the number of octaves to shift each PICO-8
                            channel
      --volume-shift VOLUME_SHIFT VOLUME_SHIFT VOLUME_SHIFT VOLUME_SHIFT
                            Specify a number to add to the volume for all notes in
                            each PICO-8 channel (the volume for each note will be
                            limited to >= 1)
      --mute MUTE MUTE MUTE MUTE
                            Specify whether to "mute" each PICO-8 channel (1 =
                            mute, 0 = play). Notes for a muted channel will
                            excluded from the cartridge entirely

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
* An automatic best guess MIDI-instrument-to-PICO-8-waveform mapping table
* Automatic or manual combination of multiple tracks into one (in places where
  both are not playing notes at the same time)
* MIDI file type 0 support
* Drums (channel 10) support
* Tempo changes during the song
* Pitch-bend or other effects???

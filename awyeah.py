#!/usr/bin/env python3.5

import argparse
import math
import sys
from translator import translator
from midi import midi
from pico8.game import game

# Constants
PICO8_NUM_CHANNELS = 4
PICO8_NUM_SFX = 64
PICO8_NUM_MUSIC = 64
PICO8_MAX_PITCH = 63

# Song-Specific Config
pico8Config = {
    'noteDuration': 14,
    'waveforms': [1, 2, 3, 1],
}

# Parse command-line arguments
argParser = argparse.ArgumentParser()
argParser.add_argument(
        'midiPath',
        help="The path to the MIDI file to be translated")
argParser.add_argument(
        'cartPath',
        help="The path to PICO-8 cartridge file to be generated",
        nargs='?',
        default='midi_out.p8')
argParser.add_argument(
        '--legato',
        help="Disable fadeout effect at the end of any notes (even repeated " +
             "notes)",
        action="store_true")
argParser.add_argument(
        '--staccato',
        help="Add a fadeout effect at the end of every note",
        action='store_true')
argParser.add_argument(
        '--no-fix-octaves',
        help="Do not change octaves of tracks to keep them in PICO-8 range",
        action='store_true')
argParser.add_argument(
        '--no-quantize',
        help="Do not perform any quantization of note lengths",
        action='store_true')
argParser.add_argument(
        '-t',
        '--midi-base-ticks',
        help="Override MIDI ticks per PICO-8 note setting (normally auto-detected)",
        type=int)
argParser.add_argument(
        '-d',
        '--note-duration',
        help="Override PICO-8 note duration setting (normally auto-detected from MIDI tempo)",
        type=int)
argParser.add_argument(
        '--start-offset',
        help="Change the start point in the MIDI file (in # of PICO-8 SFX)",
        type=int,
        default=0)
argParser.add_argument(
        '--no-compact',
        help="Disable compacting long note runs to save space",
        action='store_true')

args = argParser.parse_args()

# Set translator settings according to command-line arugments
translatorSettings = translator.TranslatorSettings()
translatorSettings.quantization = not args.no_quantize
translatorSettings.ticksPerNoteOverride = args.midi_base_ticks
translatorSettings.staccato = args.staccato
translatorSettings.legato = args.legato
translatorSettings.fixOctaves = not args.no_fix_octaves
translatorSettings.noteDurationOverride = args.note_duration
translatorSettings.sfxCompactor = not args.no_compact

# Open the MIDI file
midiFile = midi.MidiFile()
midiFile.open(args.midiPath)
midiFile.read()

translator = translator.Translator(midiFile, translatorSettings)

translator.analyze()

# Get all the notes converted to "tracks" where a "track" is a list of
# translator.Sfx objects
tracks = translator.get_sfx_lists()

# Make an empty PICO-8 catridge
cart = game.Game.make_empty_game()
lines = [
    'music(0)\n',
    'function _update()\n',
    'end']
cart.lua.update_from_lines(lines)

# Discard tracks we don't have room for
if len(tracks) > PICO8_NUM_CHANNELS:
    print("Warning: discarding some tracks we don't have room for")
    tracks = tracks[:PICO8_NUM_CHANNELS]

if args.start_offset > 0:
    # Remove SFXes from the beginning of each track, based on the "start
    # offset" parameter
    for t, track in enumerate(tracks):
        tracks[t] = track[args.start_offset:]

# Set the note duration of all SFXes
#for sfxIndex in range(PICO8_NUM_SFX):
#    cart.sfx.set_properties(
#            sfxIndex,
#            editor_mode=1,
#            loop_start=0,
#            loop_end=0,
#            note_duration=translator.noteDuration)

trackSfxIndex = 0
musicIndex = 0
sfxIndex = 0
while sfxIndex < PICO8_NUM_SFX:
    wroteAnythingToMusic = False
    for t, track in enumerate(tracks):
        wroteAnyNotesToSfx = False

        # Get the trackSfx, which is the next group of 32 notes in this track
        if len(track) - 1 < trackSfxIndex:
            continue
        trackSfx = track[trackSfxIndex]

        # Set the properites for this SFX
        cart.sfx.set_properties(
                sfxIndex,
                editor_mode=1,
                loop_start=0,
                loop_end=0,
                note_duration=trackSfx.noteDuration)

        # Add the 32 notes in this trackSfx
        # TODO: continue from here
        for n, note in enumerate(trackSfx.notes):
            if note.volume > 0:
                wroteAnyNotesToSfx = True
                noteIsInRange = (note.pitch >= 0 and
                                 note.pitch <= PICO8_MAX_PITCH)
                if noteIsInRange:
                    # Add this note to the current PICO-8 SFX
                    cart.sfx.set_note(
                            sfxIndex,
                            n,
                            pitch = note.pitch,
                            volume = note.volume,
                            effect = note.effect,
                            waveform = pico8Config['waveforms'][t])

        if wroteAnyNotesToSfx:
            # Add the SFX to a music pattern
            cart.music.set_channel(musicIndex, t, sfxIndex)
            wroteAnythingToMusic = True

            # Move to the next SFX
            sfxIndex += 1

            if sfxIndex > PICO8_NUM_SFX - 1:
                break

    trackSfxIndex += 1
    if wroteAnythingToMusic:
        musicIndex += 1
    if musicIndex > PICO8_NUM_MUSIC - 1:
        print('reached max music patterns')
        break

    # Check if the trackSfxIndex is past the end of all tracks
    allTracksAreEnded = True
    for track in tracks:
        if trackSfxIndex < len(track):
            allTracksAreEnded = False
            break
    if allTracksAreEnded:
        break

# Write the cart
with open(args.cartPath, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

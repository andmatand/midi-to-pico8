#!/usr/bin/env python3.5

import argparse
import math
import sys
from translator import translator
from midi import midi
from pico8.game import game

# Constants
PICO8_NUM_CHANNELS = 4
PICO8_NOTES_PER_SFX = 32
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
        '--ticks-per-note',
        help="Override MIDI ticks per smallest note subdivision",
        type=int)

args = argParser.parse_args()

# Set translator settings according to command-line arugments
translatorSettings = translator.TranslatorSettings()
translatorSettings.quantization = not args.no_quantize
translatorSettings.ticksPerNoteOverride = args.ticks_per_note
translatorSettings.staccato = args.staccato
translatorSettings.legato = args.legato
translatorSettings.fixOctaves = not args.no_fix_octaves

# Open the MIDI file
midiFile = midi.MidiFile()
midiFile.open(args.midiPath)
midiFile.read()

translator = translator.Translator(midiFile, translatorSettings)

translator.analyze()

# Get all the notes converted to PICO-8-like notes
tracks = translator.get_pico_tracks()

# DEBUG
#for t, track in enumerate(tracks):
#    print('track ' + str(t))
#    for n, note in enumerate(track):
#        print(n, note.pitch, note.volume)

# Make an empty PICO-8 catridge
cart = game.Game.make_empty_game()
lines = [
    'music(0)\n',
    'function _update()\n',
    'end']
cart.lua.update_from_lines(lines)

# DEBUG: add notes from track 4 into track 3 if track 3's slot is empty
#for n, note in enumerate(tracks[3]):
#    if note == None or note['volume'] == 0:
#        if n < len(tracks[4]) and tracks[4][n] != None:
#            print(n, tracks[4][n])
#            tracks[3][n] = {
#                'pitch': tracks[4][n]['pitch'],
#                'volume': tracks[4][n]['volume']
#            }

# Discard tracks we don't have room for
if len(tracks) > PICO8_NUM_CHANNELS:
    print("Warning: discarding some tracks we don't have room for")
    tracks = tracks[:PICO8_NUM_CHANNELS]

# Set the note duration of all SFXes
for sfxIndex in range(PICO8_NUM_SFX):
    cart.sfx.set_properties(
            sfxIndex,
            editor_mode=1,
            loop_start=0,
            loop_end=0,
            note_duration=translator.noteDuration)

trackNoteIndexStart = 0
sfxIndex = 0
sfxNoteIndex = 0
musicIndex = 0
while sfxIndex < PICO8_NUM_SFX:
    for t, track in enumerate(tracks):
        wroteAnyNotesToSfx = False

        # Add the next 32 notes in this track
        trackNoteIndex = trackNoteIndexStart
        for sfxNoteIndex in range(PICO8_NOTES_PER_SFX):
            if trackNoteIndex > len(track) - 1:
                break
            note = track[trackNoteIndex]
            if note != None:
                wroteAnyNotesToSfx = True
                noteIsInRange = (note.pitch >= 0 and
                                 note.pitch <= PICO8_MAX_PITCH)
                if noteIsInRange:
                    # Add this note to the current PICO-8 SFX
                    cart.sfx.set_note(
                            sfxIndex,
                            sfxNoteIndex,
                            pitch = note.pitch,
                            volume = note.volume,
                            effect = note.effect,
                            waveform = pico8Config['waveforms'][t])
            trackNoteIndex += 1 

        if wroteAnyNotesToSfx:
            # Add the SFX to a music pattern
            cart.music.set_channel(musicIndex, t, sfxIndex)

            # Move to the next SFX
            sfxIndex += 1

            if sfxIndex > PICO8_NUM_SFX - 1:
                break

    # Increment trackNoteIndexStart
    trackNoteIndexStart += PICO8_NOTES_PER_SFX

    musicIndex += 1
    if musicIndex > PICO8_NUM_MUSIC - 1:
        print('reached max music patterns')
        break

    # Check if the trackNoteIndexStart is past the end of all tracks
    allTracksAreEnded = True
    for track in tracks:
        if trackNoteIndexStart < len(track):
            allTracksAreEnded = False
            break
    if allTracksAreEnded:
        break

# Write the cart
with open(args.cartPath, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

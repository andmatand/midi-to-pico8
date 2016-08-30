#!/usr/bin/env python3.5

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

# TODO: make this settable via CLI argument
CART_PATH = 'midi_out.p8'

# Song-Specific Config
pico8Config = {
    'noteDuration': 14,
    'waveforms': [1, 2, 3, 1],
}


def parse_command_line_args():
    global path

    if len(sys.argv) < 2:
        print('usage: main.py <MIDI FILENAME> [Ticks Per Quarter Note]')
        sys.exit(1)

    # Get the filename from the 1st command line argument
    path = sys.argv[1]


parse_command_line_args()

# Open the MIDI file
midiFile = midi.MidiFile()
midiFile.open(path)
midiFile.read()

translator = translator.Translator(midiFile)

translator.analyze()

# Get all the notes converted to PICO-8-like notes
tracks = translator.get_tracks()

# DEBUG
#for t, track in enumerate(tracks):
#    print('track ' + str(t))
#    for n, note in enumerate(track):
#        print(n, note.pitch, note.volume)

translator.adjust_octaves(tracks)

# Make an empty PICO-8 catridge
cart = game.Game.make_empty_game()
lines = [
    'music(0)\n',
    'function _update()\n',
    'end']
cart.lua.update_from_lines(lines)

# Prepend empty notes to the beginning of each track based on the track's
# startDelay
for t, track in enumerate(tracks):
    if track[0].startDelay != None:
        trackOffset = track[0].startDelay

        for i in range(trackOffset):
            track.insert(0, None)

        ## offset by whole music patterns
        musicOffset = math.floor(trackOffset / PICO8_NOTES_PER_SFX)
        musicIndex = musicOffset - 1

        ## offset the remaining individual notes
        noteOffset = trackOffset % PICO8_NOTES_PER_SFX
        noteIndex = noteOffset - 1

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
with open(CART_PATH, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

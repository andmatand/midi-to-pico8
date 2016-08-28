#!/usr/bin/env python3.5

import math
import sys
from midi import midi as midiParser
from pico8.game import game

# Constants
PICO8_MAX_CHANNELS = 4
PICO8_MAX_NOTES_PER_SFX = 32
PICO8_MAX_SFX = 64

# Song-Specific Config
CART_PATH = 'bwv578.p8'
midiConfig = {'ppq': None}


def quantize(x, ppq):
    return int(ppq * round(x / ppq))

def convert_deltatime_to_notelength(deltaTime):
    # Quantize to nearest ppq
    qdt = quantize(deltaTime, midiConfig['ppq'])

    if qdt != deltaTime:
        print('quantized deltaTime {0} to {1}'.format(deltaTime, qdt))

    length = qdt / midiConfig['ppq']

    #if length != math.floor(length):
    #    print('inaccurate TIME_SIGNATURE detected')
    #    sys.exit(1)

    return int(length)

def read_ppq(midi):
    for event in midi.tracks[0].events:
        if event.type == 'TIME_SIGNATURE':
            return event.data[2]

def get_tracks(midi):
    # DEBUG
    #i = 0
    #for event in midi.tracks[2].events:
    #    if event.type == 'NOTE_ON':
    #        i += 1
    #        print(i, event)
    #    else:
    #        print('', event)

    if midiConfig['ppq'] == None:
        ppq = read_ppq(midi)
        print('setting ticks per quarter note (ppq) to {0}'.format(ppq))
        midiConfig['ppq'] = ppq

    picoTracks = []

    for t, track in enumerate(midi.tracks):
        picoNotes = []

        for e, event in enumerate(track.events):
            if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
                note = {}
                note['pitch'] = event.pitch - 36
                note['volume'] = math.floor((event.velocity / 127) * 7)

                if event.type == 'NOTE_OFF':
                    note['volume'] = 0

                # If this is the first note in this track
                if len(picoNotes) == 0:
                    # Add information on how many PICO-8 notes to wait before
                    # starting this channel
                    prevDelta = track.events[e - 1].time
                    length = convert_deltatime_to_notelength(prevDelta)
                    note['startDelay'] = length

                # Repeat the PICO-8 note as necessary to match the
                # length of the MIDI note
                deltaTime = track.events[e + 1].time
                picoNoteCount = convert_deltatime_to_notelength(deltaTime)
                for i in range(picoNoteCount):
                    picoNotes.append(note)

        if len(picoNotes) > 0:
            picoTracks.append(picoNotes)

    return picoTracks

def parse_command_line_args():
    global path

    if len(sys.argv[0]) < 2:
        print('give a filename argument')
        sys.exit(1)

    # Get the filename from the 1st command line argument
    path = sys.argv[1]

    # Get the (optional) PPQ (pulses/ticks per quarternote) from the 2nd command
    # line argument
    if len(sys.argv) >= 3:
        midiConfig['ppq'] = int(sys.argv[2])


parse_command_line_args()

# Open the MIDI file
midi = midiParser.MidiFile()
midi.open(path)
midi.read()

# Get all the notes converted to PICO-8-like notes
tracks = get_tracks(midi)

midiConfig['numTracks'] = len(tracks)

pico8Config = {
    'noteDuration': 14,
    'maxSfxPerTrack': PICO8_MAX_SFX / midiConfig['numTracks'],
    'waveforms': [1, 2, 3, 4],
}

# Make an empty PICO-8 catridge
cart = game.Game.make_empty_game()
lines = [
    'music(0)\n',
    'function _update()\n',
    'end']
cart.lua.update_from_lines(lines)

sfxIndex = -1
for t, track in enumerate(tracks):
    if t > PICO8_MAX_CHANNELS - 1:
        print('Reached PICO-8 channel limit')
        break

    noteIndex = -1
    musicIndex = -1
    trackSfxCount = 0

    if 'startDelay' in track[0]:
        trackOffset = track[0]['startDelay']

        # offset by whole music patterns
        musicOffset = math.floor(trackOffset / PICO8_MAX_NOTES_PER_SFX)
        musicIndex = musicOffset - 1

        # offset the remaining individual notes
        noteOffset = trackOffset % PICO8_MAX_NOTES_PER_SFX
        noteIndex = noteOffset - 1

        print(trackOffset)
        print(musicOffset)
        print(noteOffset)

    print('track {0}'.format(t))

    # Write the notes to a series of PICO-8 SFXes
    firstIteration = True
    for note in track:
        if noteIndex < PICO8_MAX_NOTES_PER_SFX - 1:
            noteIndex += 1
        else:
            noteIndex = 0

        if noteIndex == 0 or firstIteration:
            firstIteration = False
            trackSfxCount += 1
            if trackSfxCount > pico8Config['maxSfxPerTrack']:
                print('Ended track {0} early'.format(t))
                break

            # Move to the next PICO-8 SFX
            sfxIndex += 1

            if sfxIndex > PICO8_MAX_SFX - 1:
                print('reached max SFX')
                break

            # Set the SFX note duration
            cart.sfx.set_properties(
                    sfxIndex,
                    editor_mode=1,
                    loop_start=0,
                    loop_end=0,
                    note_duration=pico8Config['noteDuration'])

            # Add the SFX to a music pattern
            musicIndex += 1
            cart.music.set_channel(musicIndex, t, sfxIndex)

        if note != None and note['pitch'] >= 0 and note['pitch'] <= 63:
            # Add this note to the current PICO-8 SFX
            cart.sfx.set_note(
                    sfxIndex,
                    noteIndex,
                    pitch = note['pitch'],
                    volume = note['volume'],
                    waveform = 2)
                    #waveform = pico8Config['waveforms'][t])


with open(CART_PATH, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

#print(cart.sfx.get_note(0, 0))
#print(cart.sfx.get_note(0, 8))

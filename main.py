#!/usr/bin/env python3.5

import math
import sys
from midi import midi
from pico8.game import game

# Constants
PICO8_MAX_CHANNELS = 4
PICO8_MAX_NOTES_PER_SFX = 32
PICO8_MAX_SFX = 64

# Song-Specific Config
path = 'bwv578.mid'
CART_PATH = 'bwv578.p8'
midiConfig = {
    'numTracks': 4,
    'ticksPerQuarterNote': 240
}
pico8Config = {
    'noteDuration': 14,
    'maxSfxPerTrack': PICO8_MAX_SFX / midiConfig['numTracks'],
    'waveforms': [1, 2, 3, 4],
}


# lowest midi pitch: 43
# g in pico8: 31
# g in MIDI: 67
# MIDI pitch - 36 = pico8 pitch

#ticksPerQuarterNote = m.tracks[0].events[1].data[2]
#print(ticksPerQuarterNote = m.tracks[0].events[1].data[2])

def get_tracks():
    m = midi.MidiFile()
    m.open(path)
    m.read()

    picoTracks = []

    for t, track in enumerate(m.tracks):
        picoNotes = []
        previousTime = 0
        previousPicoNote = None

        for event in track.events:
            if event.type == 'NOTE_ON' and event.velocity > 0:
                # Repeat the previous PICO-8 note as necessary to match the
                # length of the MIDI note
                timeDelta = event.time - previousTime
                previousNoteLen = timeDelta / midiConfig['ticksPerQuarterNote']
                picoNoteCount = int(previousNoteLen * 8)
                for i in range(picoNoteCount - 1):
                    picoNotes.append(previousPicoNote)

                note = {}
                note['pitch'] = event.pitch - 36
                note['volume'] = math.floor((event.velocity / 127) * 7)
                picoNotes.append(note)

                previousPicoNote = note
                previousTime = event.time

        if len(picoNotes) > 0:
            picoTracks.append(picoNotes)

    return picoTracks


# Make an empty PICO-8 catridge
cart = game.Game.make_empty_game()
lines = [
    'music(0)\n',
    'function _update()\n',
    'end']
cart.lua.update_from_lines(lines)

tracks = get_tracks()

# DEBUG
#print(tracks)
#sys.exit(0)

sfxIndex = -1
for t, track in enumerate(tracks):
    if t > PICO8_MAX_CHANNELS - 1:
        print('Reached PICO-8 channel limit')
        break

    noteIndex = -1
    musicIndex = -1
    trackSfxCount = 0

    print('new track')
    print(len(track))

    # Write the notes to a series of PICO-8 SFXes
    for n, note in enumerate(track):
        if noteIndex < PICO8_MAX_NOTES_PER_SFX:
            noteIndex += 1
        else:
            noteIndex = 0

        if noteIndex == 0:
            trackSfxCount += 1
            if trackSfxCount > pico8Config['maxSfxPerTrack']:
                print('Ended track {0} early'.format(t))
                break

            # Move to the next PICO-8 SFX
            sfxIndex += 1
            print('moving to sfx ' + str(sfxIndex))

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

        if note != None:
            # Add this note to the current PICO-8 SFX
            cart.sfx.set_note(
                    sfxIndex,
                    noteIndex,
                    pitch = note['pitch'],
                    volume = note['volume'],
                    waveform = 1)
                    #waveform = pico8Config['waveforms'][t])


with open(CART_PATH, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

#print(cart.sfx.get_note(0, 0))
#print(cart.sfx.get_note(0, 8))

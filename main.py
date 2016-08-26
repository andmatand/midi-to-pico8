#!/usr/bin/env python3.5

import math
from midi import midi
from pico8.game import game

path = 'bwv578.mid'
CART_PATH = 'bwv578.p8'

m = midi.MidiFile()
m.open(path)
m.read()
#print(m.tracks[1])

# lowest midi pitch: 43
# g in pico8: 31
# g in MIDI: 67
# MIDI pitch - 36 = pico8 pitch

#ticksPerQuarterNote = m.tracks[0].events[1].data[2]
#print(ticksPerQuarterNote = m.tracks[0].events[1].data[2])
ticksPerQuarterNote = 240

picoNotes = []
previousTime = 0
previousPicoNote = None

for event in m.tracks[1].events:
    if event.type == 'NOTE_ON' and event.velocity > 0:
        #print(event)

        # Repeat the previous PICO-8 note as necessary to match the length of the MIDI note
        previousNoteLength = (event.time - previousTime) / ticksPerQuarterNote
        picoNoteCount = int(previousNoteLength * 8)
        for i in range(picoNoteCount - 1):
            picoNotes.append(previousPicoNote)

        note = {}
        note['pitch'] = event.pitch - 36
        note['volume'] = math.floor((event.velocity / 127) * 7)
        picoNotes.append(note)

        previousPicoNote = note
        previousTime = event.time


print(picoNotes)


cart = game.Game.from_filename(CART_PATH)

i = 0
for patternIndex in range(64):
    for noteIndex in range(32):
        note = picoNotes[i]
        i += 1

        cart.sfx.set_properties(patternIndex, note_duration=14)
        cart.sfx.set_note(patternIndex, noteIndex,
                         pitch = note['pitch'],
                         volume = note['volume'],
                         waveform = 0)

sfxIndex = 0
for musicIndex in range(64):
    cart.music.set_channel(musicIndex, 0, sfxIndex)
    sfxIndex += 1

with open(CART_PATH, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

#print(cart.sfx.get_note(0, 0))
#print(cart.sfx.get_note(0, 8))

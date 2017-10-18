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
PICO8_MIN_VOLUME = 1
PICO8_MAX_VOLUME = 7
MIDI_MAX_TRACKS = 128

# Defaults for Song-Specific Config
songConfig = {
    'mute': MIDI_MAX_TRACKS * [0],
    'octaveShift': MIDI_MAX_TRACKS * [0],
    'volumeShift': MIDI_MAX_TRACKS * [0],
    'waveform': MIDI_MAX_TRACKS * [0]
}

# Assign default waveforms to the first 128 MIDI tracks
w = 0
for track in range(MIDI_MAX_TRACKS):
    songConfig['waveform'][track] = w
    w += 1
    if w == 6:
        w = 0

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
        help="Override MIDI ticks per PICO-8 note setting (normally " +
             "auto-detected)",
        type=int)
argParser.add_argument(
        '-d',
        '--note-duration',
        help="Override PICO-8 note duration setting (normally auto-detected " +
             "from MIDI tempo)",
        type=int)
argParser.add_argument(
        '--start-offset',
        help="Change the start point in the MIDI file (in # of PICO-8 SFX)",
        type=int,
        default=0)
argParser.add_argument(
        '--sfx-offset',
        help="Change the starting SFX slot in PICO-8",
        type=int,
        default=0)
argParser.add_argument(
        '--no-compact',
        help="Don't try to compact groups of repeated notes into fewer " +
             "notes played for longer (this compacting is sometimes slow, " +
             "so using this flag will speed things up at the cost of " +
             "possibly occupying more SFXes in the PICO-8 cart)",
         action='store_true')
argParser.add_argument(
        '--waveform',
        help="Specify which PICO-8 waveform (instrument) number to use for " +
             "each MIDI track",
        nargs='*',
        type=int,
        default=songConfig['waveform'])
argParser.add_argument(
        '--octave-shift',
        help="Specify the number of octaves to shift each MIDI track",
        nargs='*',
        type=int,
        default=songConfig['octaveShift'])
argParser.add_argument(
        '--volume-shift',
        help='Specify a number to add to the volume of all notes in each ' +
              'MIDI track (volume for each note will be limited to the ' +
              'range 1-7',
        nargs='*',
        type=int,
        default=songConfig['volumeShift'])
argParser.add_argument(
        '--mute',
        help='Specify whether to "mute" each MIDI track ' +
             '(1 = mute, 0 = do not mute). Notes for a muted track will be ' +
             'excluded from the PICO-8 cartridge entirely',
        nargs='*',
        type=int,
        default=songConfig['mute'])

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

# Set song-specific tracker-related settings from command-line arguments
for i, value in enumerate(args.waveform):
    songConfig['waveform'][i] = value
for i, value in enumerate(args.octave_shift):
    songConfig['octaveShift'][i] = value
for i, value in enumerate(args.volume_shift):
    songConfig['volumeShift'][i] = value
for i, value in enumerate(args.mute):
    songConfig['mute'][i] = value

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

if args.start_offset > 0:
    # Remove SFXes from the beginning of each track, based on the "start
    # offset" parameter
    for t, track in enumerate(tracks):
        tracks[t] = track[args.start_offset:]

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)

# SfxDuplicateDetector creates a map of each trackSfx (which is a group of 32
# notes in a track) and the PICO-8 SFX index to which it was written, so that
# it can check if a given trackSfx was already written to the PICO-8 catridge
# and instead return the existing SFX index so the music pattern can use that.
class SfxDuplicateDetector:
    def __init__(self):
        self.map = {}
        map = {}

    def record_tracksfx_index(self, sfxIndex, trackSfx):
        self.map[sfxIndex] = trackSfx

    @staticmethod
    def sfx_match(sfx1, sfx2):
        if len(sfx1.notes) != len(sfx2.notes) or sfx1.noteDuration != sfx2.noteDuration:
            return False

        for i in range(len(sfx1.notes)):
            note1 = sfx1.notes[i]
            note2 = sfx2.notes[i]

            if (note1.pitch != note2.pitch or
                note1.volume != note2.volume or
                note1.waveform != note2.waveform or
                note1.effect != note2.effect or
                note1.length != note2.length):
                return False

        return True

    def find_duplicate_sfx_index(self, sfx):
        for sfxIndex, existingSfx in self.map.items():
            if SfxDuplicateDetector.sfx_match(existingSfx, sfx):
                return sfxIndex

sfxDuplicateDetector = SfxDuplicateDetector()
duplicateSfxSavingsCount = 0

trackSfxIndex = 0
musicIndex = 0
sfxIndex = args.sfx_offset
while sfxIndex < PICO8_NUM_SFX:
    wroteAnythingToMusic = False
    channelIndex = 0
    for t, track in enumerate(tracks):
        wroteAnyNotesToSfx = False
        wroteAnythingToChannel = False

        # Get the trackSfx, which is the next group of 32 notes in this track
        if len(track) - 1 < trackSfxIndex:
            continue
        trackSfx = track[trackSfxIndex]

        # If there is a "mute" specified for this track
        if songConfig['mute'][t] == 1:
            continue

        # Check if this SFX is a duplicate of any that have already been
        # written
        duplicateSfxIndex = sfxDuplicateDetector.find_duplicate_sfx_index(
                trackSfx)
        if duplicateSfxIndex != None:
            # Add the SFX to a music pattern
            cart.music.set_channel(musicIndex, channelIndex, duplicateSfxIndex)
            wroteAnythingToMusic = True
            wroteAnythingToChannel = True
            duplicateSfxSavingsCount += 1
        elif sfxIndex < PICO8_NUM_SFX:
            # Set the properites for this SFX
            cart.sfx.set_properties(
                    sfxIndex,
                    editor_mode=1,
                    loop_start=0,
                    loop_end=0,
                    note_duration=trackSfx.noteDuration)

            # Add the 32 notes in this trackSfx
            for n, note in enumerate(trackSfx.notes):
                if note.volume > 0:
                    pitch = note.pitch
                    volume = note.volume

                    # If there is a manual octave shift specified for this track
                    octaveShift = songConfig['octaveShift'][t]
                    if octaveShift != 0:
                        pitch = note.pitch + (12 * octaveShift)

                    # Shift the volume as specified for this track
                    volume += songConfig['volumeShift'][t]
                    volume = clamp(volume, PICO8_MIN_VOLUME, PICO8_MAX_VOLUME)

                    wroteAnyNotesToSfx = True
                    noteIsInRange = (pitch >= 0 and pitch <= PICO8_MAX_PITCH)
                    if noteIsInRange:
                        # Add this note to the current PICO-8 SFX
                        cart.sfx.set_note(
                                sfxIndex,
                                n,
                                pitch = pitch,
                                volume = volume,
                                effect = note.effect,
                                waveform = songConfig['waveform'][t])

        if wroteAnyNotesToSfx:
            # Store the PICO-8 track number that this section of the track went in
            sfxDuplicateDetector.record_tracksfx_index(sfxIndex, trackSfx)

            # Add the SFX to a music pattern
            cart.music.set_channel(musicIndex, channelIndex, sfxIndex)
            wroteAnythingToMusic = True
            wroteAnythingToChannel = True

            # Move to the next SFX
            sfxIndex += 1

        if wroteAnythingToChannel:
            # Move to the next PICO-8 music channel
            channelIndex += 1
            if channelIndex > PICO8_NUM_CHANNELS - 1:
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

if (duplicateSfxSavingsCount > 0):
    print('optimized {0} occurences of duplicate SFX'.format(duplicateSfxSavingsCount))

# Write the cart
with open(args.cartPath, 'w', encoding='utf-8') as fh:
    cart.to_p8_file(fh)

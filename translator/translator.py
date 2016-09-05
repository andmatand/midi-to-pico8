import copy
import math
import statistics

from .note import Note
from .sfx import Sfx
from .sfxcompactor import SfxCompactor
from . import PICO8_MIN_NOTE_DURATION
from . import PICO8_MAX_PITCH
from . import PICO8_NOTES_PER_SFX

# According to https://eev.ee/blog/2016/05/30/extracting-music-from-the-pico-8/
PICO8_MS_PER_TICK = (183 / 22050) * 1000

class TranslatorSettings:
    def __init__(self):
        self.quantization = True
        self.ticksPerNoteOverride = None
        self.staccato = False
        self.legato = False
        self.fixOctaves = True
        self.noteDurationOverride = None
        self.sfxCompactor = True

class Translator:
    def __init__(self, midiFile, settings: TranslatorSettings=None): 
        self.midiFile = midiFile

        if settings != None:
            self.settings = settings
        else:
            self.settings = TranslatorSettings()

        if self.settings.ticksPerNoteOverride != None:
            print('setting ticks per note to override setting of ' +
                  str(self.settings.ticksPerNoteOverride))
        self.baseTicks = self.settings.ticksPerNoteOverride

    def find_notes(self, track, channel):
        notes = []
        activeNote = None
        deltaTime = 0
        firstNoteHasBeenAdded = False

        events = [
                event for event in track.events
                if event.channel == channel or event.type == 'DeltaTime']

        for e, event in enumerate(events):
            if event.type == 'DeltaTime':
                deltaTime += event.time
            if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
                if activeNote != None:
                    activeNote.midiDuration = deltaTime
                    activeNote = None
                elif deltaTime > 0:
                    note = Note()
                    note.midiDuration = deltaTime
                    notes.append(note)

                if event.type == 'NOTE_ON' and event.velocity > 0:
                    note = Note(event)
                    activeNote = note
                    notes.append(note)

                deltaTime = 0

        return notes

    def analyze(self):
        print('MIDI format is type ' + str(self.midiFile.format))

        # Get a list of unique note lengths and the number of occurrences of
        # each length
        uniqueLengths = {}
        noteCount = 0
        for track in self.midiFile.tracks:
            occupiedChannels = self.find_occupied_channels(track)
            for channel in occupiedChannels:
                notes = self.find_notes(track, channel)
                
                for note in notes:
                    noteCount += 1
                    length = note.midiDuration
                    if length > 0:
                        if not length in uniqueLengths:
                            uniqueLengths[length] = 0
                        uniqueLengths[length] += 1

        # DEBUG
        import operator
        #print('unique lengths:')
        #sortedUniqueLengths = sorted(
        #    uniqueLengths.items(),
        #    key=operator.itemgetter(1),
        #    reverse=True)
        #print(sortedUniqueLengths)

        mostFrequentLength = None
        highestCount = 0
        for length, count in uniqueLengths.items():
            if count > highestCount:

                highestCount = count
                mostFrequentLength = length

        print('note count: ' + str(noteCount))
        print('most frequent length: ' + str(mostFrequentLength))

        # Find the average number of occurrences for a unique length
        averageOccurences = statistics.mean(uniqueLengths.values())
        print('mean occurrences: ' + str(averageOccurences))
        print('median occurrences: ' +
              str(statistics.median(uniqueLengths.values())))

        # Remove lengths from uniqueLengths that have less than the average
        # number of occurrences
        newUniqueLengths = {}
        for length, occurrences in uniqueLengths.items():
            if occurrences >= averageOccurences:
                newUniqueLengths[length] = occurrences
        uniqueLengths = newUniqueLengths

        # Take each length and divide the other lengths by it, counting how
        # many other lengths it divides evenly into
        candidateBaseLengths = {}
        for length, occurrences in uniqueLengths.items():
            for otherLength in uniqueLengths.keys():
                if otherLength % length == 0:
                    if not length in candidateBaseLengths:
                        candidateBaseLengths[length] = 0
                    candidateBaseLengths[length] += 1

        # DEBUG
        print('candidate base lengths:')
        sortedCandidateBaseLengths = sorted(
            candidateBaseLengths.items(),
            key=operator.itemgetter(1),
            reverse=True)
        for length, score in sortedCandidateBaseLengths:
            print(length, score)


        # Find the best of the candidate base-lengths, where "best" is the one
        # with the most even divisions into other lengths. If there is a tie,
        # prefer the shortest candidate base-length.
        bestBaseLength = None
        highestNumberOfEvenDivisions = 0
        for length, evenDivisionCount in candidateBaseLengths.items():
            if evenDivisionCount > highestNumberOfEvenDivisions:
                highestNumberOfEvenDivisions = evenDivisionCount
                bestBaseLength = length
            elif evenDivisionCount == highestNumberOfEvenDivisions:
                if length < bestBaseLength:
                    bestBaseLength = length

        if self.baseTicks == None:
            print('setting MIDI base ticks per note to ' + str(bestBaseLength))
            self.baseTicks = bestBaseLength

        self.noteDuration = self.find_note_duration()
        print('PICO-8 note duration: ' + str(self.noteDuration))


    def quantize_length(self, ticks):
        return int(self.baseTicks * round(ticks / self.baseTicks))

    # Find the first SET_TEMPO event and take that to be the tempo of the whole
    # song.  Then, use math along with the BPM to convert that to the
    # equivalent PICO-8 note duration
    def find_note_duration(self):
        if self.settings.noteDurationOverride != None:
            return self.settings.noteDurationOverride

        ppq = self.midiFile.ticksPerQuarterNote
        ## Find the PPQ from the first TIME_SIGNATURE event
        #for track in self.midiFile.tracks:
        #    for e, event in enumerate(track.events):
        #        if event.type == 'TIME_SIGNATURE':
        #            print(event)
        #            ppq = event.data[2]
        #            #break

        # Find the microseconds per MIDI quarter note from the first SET_TEMPO
        # event
        mpqn = None
        for track in self.midiFile.tracks:
            for e, event in enumerate(track.events):
                if event.type == 'SET_TEMPO':
                    mpqn = int.from_bytes(
                            event.data,
                            byteorder='big',
                            signed=False)
                    break


        if mpqn != None:
            bpm = 60000000 / mpqn
        else:
            bpm = MIDI_DEFAULT_BPM

        midiMsPerTick = 60000 / (bpm * ppq)

        # DEBUG
        #print('ppq: ' + str(ppq))
        #print('mpqn: ' + str(mpqn))
        #print('bpm: ' + str(bpm))
        #print('MIDI msPerTick: ' + str(midiMsPerTick))
        #print('PICO-8 msPerTick: ' + str(PICO8_MS_PER_TICK))

        d = round(self.baseTicks * (midiMsPerTick / PICO8_MS_PER_TICK))
        if d < PICO8_MIN_NOTE_DURATION:
            d = PICO8_MIN_NOTE_DURATION
        return d

    def convert_ticks_to_notelength(self, deltaTime):
        if self.settings.quantization:
            originalDeltaTime = deltaTime
            deltaTime = self.quantize_length(deltaTime)

            if deltaTime != originalDeltaTime:
                print('quantized deltaTime {0} to {1}'.format(
                    originalDeltaTime, deltaTime))

        return int(deltaTime / self.baseTicks)

    def get_pico_notes(self, track, channel):
        picoTrack = []

        notes = self.find_notes(track, channel)
        for n, note in enumerate(notes):
            note.length = self.convert_ticks_to_notelength(note.midiDuration)
            for i in range(note.length):
                # Create a copy of the note
                noteCopy = copy.copy(note)

                if not self.settings.legato:
                    # If this is the last copy of this note
                    if i == note.length - 1:
                        # Find the next note
                        if n < len(notes) - 1:
                            nextNote = notes[n + 1]
                        else:
                            nextNote = None

                        # If the next note is the same pitch
                        if nextNote and nextNote.pitch == noteCopy.pitch:
                            nextNoteIsSamePitch = True
                        else:
                            nextNoteIsSamePitch = False
                        if nextNoteIsSamePitch or self.settings.staccato:
                            # Give the note a fadeout effect
                            noteCopy.effect = 5

                picoTrack.append(noteCopy)

        return picoTrack

    def find_occupied_channels(self, track):
        occupiedChannels = []

        for event in track.events:
            if not event.channel in occupiedChannels:
                occupiedChannels.append(event.channel)

        return occupiedChannels

    @staticmethod
    def trim_empty_notes_from_end_of_sfx_list(sfxes):
        if len(sfxes) > 0:
            # Trim empty notes off the end of the last Sfx
            lastNoteIndex = None
            for i in range(len(sfxes[-1].notes) - 1, -1, -1):
                if sfxes[-1].notes[i].volume > 0:
                    lastNoteIndex = i
                    break
            if lastNoteIndex != None:
                sfxes[-1].notes = sfxes[-1].notes[:lastNoteIndex + 1]


    def split_into_sfxes(self, notes):
        sfxes = []

        for i in range(0, len(notes), PICO8_NOTES_PER_SFX):
            sfx = Sfx(notes[i:i + PICO8_NOTES_PER_SFX])
            sfx.noteDuration = self.find_note_duration()
            sfxes.append(sfx)

        return sfxes

    def get_sfx_lists(self):
        picoNoteLists = []

        for t, midiTrack in enumerate(self.midiFile.tracks):
            # Find the channels in use in this track
            usedChannels = self.find_occupied_channels(midiTrack)

            # Separate each channel into a "track"
            for channel in usedChannels:
                picoNotes = self.get_pico_notes(midiTrack, channel)

                hasAudibleNotes = False
                for note in picoNotes:
                    if note.volume > 0:
                        hasAudibleNotes = True
                        break

                # If this track has any notes
                if len(picoNotes) > 0 and hasAudibleNotes:
                    picoNoteLists.append(picoNotes)

        if self.settings.fixOctaves:
            picoNoteLists = self.adjust_octaves(picoNoteLists)

        print('got a total of {0} translated tracks'.format(len(picoNoteLists)))

        # OPTIMIZATION TODO: Try to combine tracks if they have no overlapping
        # notes

        # Split each noteList into "SFX"es (i.e. 32-note chunks)
        sfxLists = []
        for t, noteList in enumerate(picoNoteLists):
            sfxes = self.split_into_sfxes(noteList)
            Translator.trim_empty_notes_from_end_of_sfx_list(sfxes)
            sfxLists.append(sfxes)

        if self.settings.sfxCompactor:
            print('Compacting long notes...')
            sfxCompactor = SfxCompactor(sfxLists)
            sfxLists = sfxCompactor.run()

        return sfxLists

    def adjust_octaves(self, tracks):
        for t, track in enumerate(tracks):
            raised = False
            lowered = False
            while True:
                trackGoesTooLow = False
                trackGoesTooHigh = False

                # Check if any notes are out of range
                for note in track:
                    if note.volume > 0 and note.pitch != None:
                        if note.pitch < 0:
                            trackGoesTooLow = True
                        elif note.pitch > PICO8_MAX_PITCH:
                            trackGoesTooHigh = True

                if trackGoesTooLow and trackGoesTooHigh:
                    print('track {0} goes out of range in both directions; ' +
                          'octave will not be adjusted'.format(t))
                    break
                elif trackGoesTooLow:
                    print('pitching out-of-range track {0} up an octave'.
                          format(t))
                    # Add an octave to every note in this track
                    raised = True
                    for note in track:
                        if note.pitch != None:
                            note.pitch += 12

                elif trackGoesTooHigh:
                    print('pitching out-of-range track {0} down an octave'.
                          format(t))
                    # Subtract an octave from every note in this track
                    lowered = True
                    for note in track:
                        if note.pitch != None:
                            note.pitch -= 12
                else:
                    break

                # Prevent ping-ponging back and forth infinitely
                if raised and lowered:
                    break

        return tracks




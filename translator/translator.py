import copy
import math

PICO8_MAX_PITCH = 63
PICO8_MIN_NOTE_DURATION = 1
MIDI_DEFAULT_BPM = 120

# According to https://eev.ee/blog/2016/05/30/extracting-music-from-the-pico-8/
PICO8_MS_PER_TICK = (183 / 22050) * 1000

class Note:
    def __init__(self):
        self.pitch = None
        self.volume = None
        self.effect = None

class TranslatorSettings:
    def __init__(self):
        self.quantization = True
        self.legato = False

class Translator:
    def __init__(self, midiFile, settings: TranslatorSettings=None): 
        self.midiFile = midiFile

        if settings != None:
            self.settings = settings
        else:
            self.settings = TranslatorSettings()

        self.ticksPerNote = None # MIDI ticks per PICO-8 note


    def analyze(self):
        # Get a list of unique note lengths and the number of occurences of
        # each length
        uniqueLengths = {}
        for track in self.midiFile.tracks:
            for e, event in enumerate(track.events):
                if event.type == 'NOTE_ON': #or event.type == 'NOTE_OFF':
                    length = track.events[e + 1].time
                    if length > 0:
                        if not length in uniqueLengths:
                            uniqueLengths[length] = 0

                        uniqueLengths[length] += 1

        mostFrequentLength = None
        highestCount = 0
        for length, count in uniqueLengths.items():
            if count > highestCount:

                highestCount = count
                mostFrequentLength = length

        print('most frequent length: ' + str(mostFrequentLength))

        # DEBUG
        #shortestLength = 32767
        #for length, count in uniqueLengths.items():
        #    if length < shortestLength:
        #        shortestLength = length
        #print('shortest length: ' + str(shortestLength))

        # DEBUG
        #print('events with shortest length:')
        #for track in self.midiFile.tracks:
        #    for e, event in enumerate(track.events):
        #        if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
        #            length = track.events[e + 1].time
        #            if length == shortestLength:
        #                print(event)

        # Find the shortest occuring length that divides evenly into
        # mostFrequentLength
        smallestEvenSubdivision = 32767
        for length, count in uniqueLengths.items():
            if (mostFrequentLength % length == 0 and
                length < smallestEvenSubdivision):
                smallestEvenSubdivision = length

        print('smallest even subdivision: ' + str(smallestEvenSubdivision))
        print('setting ticks per note to ' + str(smallestEvenSubdivision))
        self.ticksPerNote = smallestEvenSubdivision

        # DEBUG
        #self.ticksPerNote = 48
        #self.noteDuration = ticksPerNote

        self.noteDuration = self.find_note_duration()
        print('PICO-8 note duration: ' + str(self.noteDuration))


    def quantize_length(self, ticks):
        return int(self.ticksPerNote * round(ticks / self.ticksPerNote))

    # Find the first SET_TEMPO event and take that to be the tempo of the whole
    # song.  Then, use math along with the BPM to convert that to the
    # equivalent PICO-8 note duration
    def find_note_duration(self):
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

        d = round(self.ticksPerNote * (midiMsPerTick / PICO8_MS_PER_TICK))
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

        return int(deltaTime / self.ticksPerNote)

    #def read_ppq(self):
    #    for event in self.midiFile.tracks[0].events:
    #        if event.type == 'TIME_SIGNATURE':
    #            return event.data[2]

    def get_tracks(self):
        # DEBUG
        #i = 0
        #for event in self.midiFile.tracks[1].events:
        #    if event.type == 'NOTE_ON':
        #        i += 1
        #        print(i, event)
        #    else:
        #        print('', event)

        picoTracks = []

        for t, track in enumerate(self.midiFile.tracks):
            picoNotes = []
            deltaTime = 0
            activeNote = None
            firstNoteHasBeenAdded = False

            for e, event in enumerate(track.events):
                if event.type == 'DeltaTime':
                    deltaTime += event.time
                if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
                    activeLength = self.convert_ticks_to_notelength(deltaTime)
                    deltaTime = 0

                    if not firstNoteHasBeenAdded:
                        firstNoteHasBeenAdded = True
                        # If this is the first note in this track, add empty
                        # notes before this to delay the start until the
                        # correct time
                        for i in range(activeLength):
                            picoNotes.append(None)

                    if activeNote != None:
                        # If we are adding a note right after a different note
                        # finished
                        if len(picoNotes) > 0:
                            prevNote = picoNotes[-1]
                        else:
                            prevNote = None
                        if activeLength > 0 and prevNote != None:
                            if activeNote.volume > 0 and prevNote.volume > 0:
                                # Give a fade-out effect to the last PICO-8
                                # note in the previous series
                                picoNotes[-1].effect = 5

                        # Repeat the active PICO-8 note as necessary to match
                        # the length of the MIDI note
                        for i in range(activeLength):
                            picoNotes.append(copy.copy(activeNote))

                        #if activeLength > 0:
                        #    # Give a fade-out effect to the last PICO-8 note in
                        #    # the series
                        #    picoNotes[-1].effect = 5

                    activeNote = Note()
                    activeNote.pitch = event.pitch - 36
                    activeNote.volume = math.floor((event.velocity / 127) * 7)

                    if event.type == 'NOTE_OFF':
                        activeNote.volume = 0

            if len(picoNotes) > 0:
                picoTracks.append(picoNotes)

        return picoTracks

    def adjust_octaves(self, tracks):
        for t, track in enumerate(tracks):
            # Count how many actual notes are in this track, where "actual
            # notes" are those who have the following characteristics:
            # * volume greater than 0
            # * will actually fit in PICO-8 tracker space limits
            actualNoteCount = 0
            for note in track:
                if note != None: 
                    if note.volume > 0:
                        actualNoteCount += 1
            
            # Count how many notes' pitches in this track are below PICO-8 range
            tooLowCount = 0
            for note in track:
                if note != None:
                    if note.volume > 0 and note.pitch < 0:
                        tooLowCount += 1

            # Count how many notes' pitches in this track are above PICO-8
            # range
            tooHighCount = 0
            for note in track:
                if note != None:
                    if note.volume > 0 and note.pitch > PICO8_MAX_PITCH:
                        tooHighCount += 1

            # If the majority are too low
            if tooLowCount >= (actualNoteCount / 2):
                print('pitching out-of-range track {0} up an octave'.format(t))
                # Add an octave to every note in this track
                for note in track:
                    if note != None:
                        note.pitch += 12
            # If the majority are too high
            elif tooHighCount >= (actualNoteCount / 2):
                print('pitching out-of-range track {0} down an octave'.format(t))
                # Subtract an octave from every note in this track
                for note in track:
                    if note != None:
                        note.pitch -= 12



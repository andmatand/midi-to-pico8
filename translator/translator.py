import copy
import math

MIDI_DEFAULT_BPM = 120
MIDI_MAX_CHANNELS = 16

MIDI_TO_PICO8_PITCH_SUBTRAHEND = 36

PICO8_MAX_PITCH = 63
PICO8_MIN_NOTE_DURATION = 1

# According to https://eev.ee/blog/2016/05/30/extracting-music-from-the-pico-8/
PICO8_MS_PER_TICK = (183 / 22050) * 1000

class Note:
    def __init__(self, event=None):
        # MIDI properties
        self.midiDuration = 0
        self.midiPitch = None
        self.midiChannel = None
        self.midiVelocity = None

        # PICO-8 tracker properties
        self.pitch = None
        self.volume = 0
        self.effect = None

        if event != None:
            self.midiPitch = event.pitch
            self.midiChannel = event.channel
            self.midiVelocity = event.velocity
            self.pitch = event.pitch - MIDI_TO_PICO8_PITCH_SUBTRAHEND
            self.volume = math.floor((event.velocity / 127) * 7)

class TranslatorSettings:
    def __init__(self):
        self.quantization = True
        self.ticksPerNoteOverride = None
        self.staccato = False
        self.legato = False
        self.fixOctaves = True
        self.noteDurationOverride = None

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

    #def find_notes_any_channel(self, track):
    #    notes = []
    #    activeNote = None
    #    deltaTime = 0

    #    for e, event in enumerate(track.events):
    #        if event.type == 'DeltaTime':
    #            deltaTime += event.time
    #        if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
    #            if activeNote != None:
    #                activeNote.midiDuration = deltaTime
    #                if deltaTime == 40:
    #                    print(event)
    #            deltaTime = 0

    #            activeNote = Note(event)
    #            notes.append(activeNote)

    #            if event.type == 'NOTE_OFF':
    #                activeNote.volume = 0

    #    return notes

    def find_notes(self, track, channel):
        notes = []
        activeNotes = []
        deltaTime = 0
        firstNoteHasBeenAdded = False

        events = [
                event for event in track.events
                if event.channel == channel or event.type == 'DeltaTime']

        for e, event in enumerate(events):
            if event.type == 'DeltaTime':
                deltaTime += event.time
            if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
                existingNote = next(
                    (note for note in activeNotes
                     if note.midiPitch == event.pitch and
                     note.midiChannel == event.channel),
                    None)

                if existingNote != None:
                    existingNote.midiDuration = deltaTime
                    activeNotes.remove(existingNote)
                elif deltaTime > 0:
                    note = Note()
                    note.midiDuration = deltaTime
                    notes.append(note)

                if event.type == 'NOTE_ON' and event.velocity > 0:
                    note = Note(event)
                    activeNotes.append(note)
                    notes.append(note)

                deltaTime = 0

        return notes

    def analyze(self):
        # Get a list of unique note lengths and the number of occurences of
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
        print('unique lengths:')
        sortedUniqueLengths = sorted(
            uniqueLengths.items(),
            key=operator.itemgetter(1),
            reverse=True)
        print(sortedUniqueLengths)

        mostFrequentLength = None
        highestCount = 0
        for length, count in uniqueLengths.items():
            if count > highestCount:

                highestCount = count
                mostFrequentLength = length

        print('note count: ' + str(noteCount))
        print('most frequent length: ' + str(mostFrequentLength))

        # Take each length and divide the other lengths by it, counting how
        # many other lengths it divides evenly into
        candidateBaseLengths = {}
        for length, occurences in uniqueLengths.items():
            for otherLength in uniqueLengths.keys():
                if otherLength != length:
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
            # If this length is an "outlier", i.e the length occurs on less
            # than 5% of all notes
            if (evenDivisionCount / noteCount) < 0.05:
                continue

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

    def get_pico_track(self, track, channel):
        picoTrack = []

        notes = self.find_notes(track, channel)
        for n, note in enumerate(notes):
            length = self.convert_ticks_to_notelength(note.midiDuration)
            for i in range(length):
                # Create a copy of the note
                noteCopy = copy.copy(note)

                if not self.settings.legato:
                    # If this is the last copy of this note
                    if i == length - 1:
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
        
    #def get_pico_track_old(self, track, channel):
    #    picoNotes = []
    #    deltaTime = 0
    #    activeNote = None
    #    firstNoteHasBeenAdded = False

    #    # Filter to only events on the specified channel
    #    #print(channel)
    #    events = [
    #            event for event in track.events
    #            if event.channel == channel or event.type == 'DeltaTime']

    #    for e, event in enumerate(events):
    #        if event.type == 'DeltaTime':
    #            deltaTime += event.time
    #        if event.type == 'NOTE_ON' or event.type == 'NOTE_OFF':
    #            activeLength = self.convert_ticks_to_notelength(deltaTime)
    #            deltaTime = 0

    #            if not firstNoteHasBeenAdded:
    #                firstNoteHasBeenAdded = True
    #                # If this is the first note in this track, add empty notes
    #                # before this to delay the start until the correct time
    #                for i in range(activeLength):
    #                    picoNotes.append(None)

    #            if activeNote != None:
    #                if not self.settings.legato:
    #                    # If we are adding a note right after a different note
    #                    # finished
    #                    if len(picoNotes) > 0:
    #                        prevNote = picoNotes[-1]
    #                    else:
    #                        prevNote = None
    #                    if activeLength > 0 and prevNote != None:
    #                        if activeNote.volume > 0 and prevNote.volume > 0:
    #                            needFadeOut = activeNote.pitch == prevNote.pitch
    #                            if needFadeOut or self.settings.staccato:
    #                                # Give a fade-out effect to the last PICO-8
    #                                # note in the previous series
    #                                picoNotes[-1].effect = 5

    #                # Repeat the active PICO-8 note as necessary to match the
    #                # length of the MIDI note
    #                for i in range(activeLength):
    #                    picoNotes.append(copy.copy(activeNote))

    #            activeNote = Note(event)

    #            if event.type == 'NOTE_OFF':
    #                activeNote.volume = 0

    #    return picoNotes

    def find_occupied_channels(self, track):
        occupiedChannels = []

        for event in track.events:
            if not event.channel in occupiedChannels:
                occupiedChannels.append(event.channel)

        return occupiedChannels

    def get_pico_tracks(self):
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
            # Find the channels in use in this track
            usedChannels = self.find_occupied_channels(track)
            for channel in usedChannels:
                picoTrack = self.get_pico_track(track, channel)

                # If this track has any notes
                if len(picoTrack) > 0:
                    picoTracks.append(picoTrack)

        print('got a total of {0} translated tracks'.format(len(picoTracks)))

        if self.settings.fixOctaves:
            picoTracks = self.adjust_octaves(picoTracks)

        return picoTracks

    def adjust_octaves(self, tracks):
        for t, track in enumerate(tracks):
            while True:
                trackGoesTooLow = False
                trackGoesTooHigh = False

                # Check if any notes are out of range
                for note in track:
                    if note != None and note.volume > 0 and note.pitch != None:
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
                    for note in track:
                        if note != None and note.pitch != None:
                            note.pitch += 12

                elif trackGoesTooHigh:
                    print('pitching out-of-range track {0} down an octave'.
                          format(t))
                    # Subtract an octave from every note in this track
                    for note in track:
                        if note != None and note.pitch != None:
                            note.pitch -= 12
                else:
                    break

        return tracks




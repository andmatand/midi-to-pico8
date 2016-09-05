from .note import Note
from .sfx import Sfx

# SfxCompactor does the following:
# Look for spots across all tracks at the same time with N consecutive SFXes
# that can be combined into one with each note-run's length reduced (i.e.
# divided by N) and the note duration increased (i.e. multiplied by N) to
# compensate
class SfxCompactor:
    # "tracks" is a list of SFX lists
    def __init__(self, tracks):
        self.tracks = tracks

    def get_longest_track_sfx_count(self):
        longestTrackSfxCount = 0
        for track in self.tracks:
            length = len(track)
            if length > longestTrackSfxCount:
                longestTrackSfxCount = length

        return longestTrackSfxCount

    def run(self):
        # TODO: figure out optimal highest N to try first
        n = 8
        while n > 1:
            self.optimize_sfx_speeds(n)
            n -= 1

        return self.tracks

    def get_track_section(self, track, sfxIndexStart, n):
        trackSection = TrackSection()
        trackSection.sfxList = track[sfxIndexStart:sfxIndexStart + n]

        for s, sfx in enumerate(trackSection.sfxList):
            noteRuns = self.find_note_runs(sfx.notes)
            trackSection.sfxNoteRunLists.append(noteRuns)

        return trackSection

    def get_track_sections(self, sfxIndexStart, n):
        trackSections = []
        for track in self.tracks:
            trackSection = self.get_track_section(track, sfxIndexStart, n)
            trackSections.append(trackSection)

        return trackSections

    def optimize_sfx_speeds(self, n):
        sfxIndexStart = 0
        while sfxIndexStart < self.get_longest_track_sfx_count():
            trackSections = self.get_track_sections(sfxIndexStart, n)

            # Check if all note runs have lengths divisible by N
            allRunsDivideEvenly = True
            for trackSection in trackSections:
                for runList in trackSection.sfxNoteRunLists:
                    for run in runList:
                        if len(run) % n != 0:
                            allRunsDivideEvenly = False

            if allRunsDivideEvenly:
                print('Compacting SFX group by a factor of ' + str(n))

                for t, trackSection in enumerate(trackSections):
                    # Remove notes from each run
                    for runList in trackSection.sfxNoteRunLists:
                        for r, run in enumerate(runList):
                            newLength = int(len(run) / n)
                            runList[r] = run[:-newLength]

                    # Collect all the notes from this TrackSection into a
                    # contiguous list
                    allNotes = []
                    for runList in trackSection.sfxNoteRunLists:
                        for run in runList:
                            allNotes.extend(run)

                    # Replace the first SFX's notes with the concatenation of
                    # all the now-shortened notes in the group of SFX
                    trackSection.sfxList[0].notes = allNotes
                    trackSection.sfxList[0].noteDuration *= n

                    # Delete the now-empty SFXes in this track
                    del self.tracks[t][sfxIndexStart + 1 : sfxIndexStart + n]
                sfxIndexStart += 1
            else:
                sfxIndexStart += n

    # Find all the note runs (where a "run" is a list of consecutive PICO-8
    # notes that are all representing the same MIDI note) in a given list of
    # notes
    def find_note_runs(self, notes):
        runs = []

        run = []
        for n, note in enumerate(notes):
            currentRunShouldEnd = False

            noteBelongsToCurrentRun = False
            if len(run) > 0:
                prevNote = run[-1]
            else:
                prevNote = None

            if prevNote != None:
                if (note.pitch == prevNote.pitch and
                    note.volume == prevNote.volume and
                    note.waveform == prevNote.waveform):
                    noteBelongsToCurrentRun = True
                elif note.volume == 0 and prevNote.volume == 0:
                    noteBelongsToCurrentRun = True

            # If this note should be added to the current run
            if noteBelongsToCurrentRun or len(run) == 0:
                run.append(note)

                # If this note has an effect, it must be the last in the run
                if note.effect != None:
                    currentRunShouldEnd = True
            else:
                currentRunShouldEnd = True

            if n == len(notes) - 1:
                currentRunShouldEnd = True

            if currentRunShouldEnd:
                # End the current run
                runs.append(run)

                # Add the current note to a new run
                run = [note]

        return runs


class TrackSection:
    def __init__(self):
        self.sfxList = []
        self.sfxNoteRunLists = []

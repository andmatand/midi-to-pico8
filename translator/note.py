import math
from . import MIDI_TO_PICO8_PITCH_SUBTRAHEND

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
        self.waveform = None
        self.effect = None
        self.length = 0

        if event != None:
            self.midiPitch = event.pitch
            self.midiChannel = event.channel
            self.midiVelocity = event.velocity
            self.pitch = event.pitch - MIDI_TO_PICO8_PITCH_SUBTRAHEND
            self.volume = math.floor((event.velocity / 127) * 7)


#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" 
midi.py -- MIDI classes and parser in Python 
Convered Python 2 code to Python 3 code in December 2012 by Akio Nishimura
Placed into the public domain in December 2001 by Will Ware 
Python MIDI classes: meaningful data structures that represent MIDI 
events 
and other objects. You can read MIDI files to create such objects, or 
generate a collection of objects and use them to write a MIDI file. 
Helpful MIDI info: 
http://crystal.apana.org.au/ghansper/midi_introduction/midi_file_form... 
http://www.argonet.co.uk/users/lenny/midi/mfile.html 
""" 
import sys, string, types, io
debugflag = 0 
#import io
#sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
def showstr(tmpstr, n=16): 
    for x in tmpstr[:n]: 
        print(('%02x' % x), end=' ') 
    print() 
def getNumber(tmpstr, length): 
    # MIDI uses big-endian for everything 
    sum = 0 
    for i in range(length): 
        sum = (sum << 8) + tmpstr[i] 
    return sum, tmpstr[length:] 
def getVariableLengthNumber(tmpstr): 
    sum = 0 
    i = 0 
    while 1: 
        x = tmpstr[i] 
        i = i + 1 
        sum = (sum << 7) + (x & 0x7F) 
        if not (x & 0x80): 
            return sum, tmpstr[i:] 
def putNumber(num, length): 
    # MIDI uses big-endian for everything 
    lst = [ ] 
    for i in range(length): 
        n = 8 * (length - 1 - i) 
        lst.append(chr((num >> n) & 0xFF)) 
    return str([lst, ""]) 
def putVariableLengthNumber(x): 
    lst = [ ] 
    while 1: 
        y, x = x & 0x7F, x >> 7 
        lst.append(chr(y + 0x80)) 
        if x == 0: 
            break 
    lst.reverse() 
    lst[-1] = chr(ord(lst[-1]) & 0x7f) 
    return str([lst, ""]) 
class EnumException(Exception): 
    pass 
class Enumeration: 
    def __init__(self, enumList): 
        lookup = { } 
        reverseLookup = { } 
        i = 0 
        uniqueNames = [ ] 
        uniqueValues = [ ] 
        for x in enumList: 
            if type(x) == tuple: 
                x, i = x 
            if type(x) != str: 
                raise EnumException("enum name is not a string: " + x) 
            if type(i) != int: 
                raise EnumException("enum value is not an integer: " + i) 
            if x in uniqueNames: 
                raise EnumException("enum name is not unique: " + x) 
            if i in uniqueValues: 
                raise EnumException("enum value is not unique for " + x) 
            uniqueNames.append(x) 
            uniqueValues.append(i) 
            lookup[x] = i 
            reverseLookup[i] = x 
            i = i + 1 
        self.lookup = lookup 
        self.reverseLookup = reverseLookup 
    def __add__(self, other): 
        lst = [ ] 
        for k in list(self.lookup.keys()): 
            lst.append((k, self.lookup[k])) 
        for k in list(other.lookup.keys()): 
            lst.append((k, other.lookup[k])) 
        return Enumeration(lst) 
    def hasattr(self, attr): 
        return attr in self.lookup 
    def has_value(self, attr): 
        return attr in self.reverseLookup 
    def __getattr__(self, attr): 
        if attr not in self.lookup: 
            raise AttributeError 
        return self.lookup[attr] 
    def whatis(self, value): 
        return self.reverseLookup[value] 
channelVoiceMessages = Enumeration([("NOTE_OFF", 0x80), 
                                    ("NOTE_ON", 0x90), 
                                    ("POLYPHONIC_KEY_PRESSURE", 0xA0), 
                                    ("CONTROLLER_CHANGE", 0xB0), 
                                    ("PROGRAM_CHANGE", 0xC0), 
                                    ("CHANNEL_KEY_PRESSURE", 0xD0), 
                                    ("PITCH_BEND", 0xE0)]) 
channelModeMessages = Enumeration([("ALL_SOUND_OFF", 0x78), 
                                   ("RESET_ALL_CONTROLLERS", 0x79), 
                                   ("LOCAL_CONTROL", 0x7A), 
                                   ("ALL_NOTES_OFF", 0x7B), 
                                   ("OMNI_MODE_OFF", 0x7C), 
                                   ("OMNI_MODE_ON", 0x7D), 
                                   ("MONO_MODE_ON", 0x7E), 
                                   ("POLY_MODE_ON", 0x7F)]) 
metaEvents = Enumeration([("SEQUENCE_NUMBER", 0x00), 
                          ("TEXT_EVENT", 0x01), 
                          ("COPYRIGHT_NOTICE", 0x02), 
                          ("SEQUENCE_TRACK_NAME", 0x03), 
                          ("INSTRUMENT_NAME", 0x04), 
                          ("LYRIC", 0x05), 
                          ("MARKER", 0x06), 
                          ("CUE_POINT", 0x07), 
                          ("MIDI_CHANNEL_PREFIX", 0x20), 
                          ("MIDI_PORT", 0x21), 
                          ("END_OF_TRACK", 0x2F), 
                          ("SET_TEMPO", 0x51), 
                          ("SMTPE_OFFSET", 0x54), 
                          ("TIME_SIGNATURE", 0x58), 
                          ("KEY_SIGNATURE", 0x59), 
                          ("SEQUENCER_SPECIFIC_META_EVENT", 0x7F)]) 
# runningStatus appears to want to be an attribute of a MidiTrack. But 
# it doesn't seem to do any harm to implement it as a global. 
runningStatus = None 
class MidiEvent: 
    def __init__(self, track): 
        self.track = track 
        self.time = None 
        self.channel = self.pitch = self.velocity = self.data = None 
    def __cmp__(self, other): 
        # assert self.time != None and other.time != None 
        return cmp(self.time, other.time) 
    def __repr__(self): 
        r = ("<MidiEvent %s, t=%s, track=%s, channel=%s" % 
             (self.type, 
              repr(self.time), 
              self.track.index, 
              repr(self.channel))) 
        for attrib in ["pitch", "data", "velocity"]: 
            if getattr(self, attrib) != None: 
                r = r + ", " + attrib + "=" + repr(getattr(self, attrib)) 
        return r + ">" 
    def read(self, time, tmpstr): 
        global runningStatus
        self.time = time 
        #print('%02x' % tmpstr[0])
        # do we need to use running status? 
        if not (tmpstr[0] & 0x80): 
            tmpstr = bytes([runningStatus]) + tmpstr
        runningStatus = x = tmpstr[0]
        y = x & 0xF0 
        z = tmpstr[1] 
        if channelVoiceMessages.has_value(y): 
            self.channel = (x & 0x0F) + 1 
            self.type = channelVoiceMessages.whatis(y) 
            if (self.type == "PROGRAM_CHANGE" or 
                self.type == "CHANNEL_KEY_PRESSURE"): 
                self.data = z 
                return tmpstr[2:] 
            else: 
                self.pitch = z 
                self.velocity = tmpstr[2] 
                channel = self.track.channels[self.channel - 1] 
                if (self.type == "NOTE_OFF" or 
                    (self.velocity == 0 and self.type == "NOTE_ON")): 
                    channel.noteOff(self.pitch, self.time) 
                elif self.type == "NOTE_ON": 
                    channel.noteOn(self.pitch, self.time, self.velocity) 
                return tmpstr[3:] 
        elif y == 0xB0 and channelModeMessages.has_value(z): 
            self.channel = (x & 0x0F) + 1 
            self.type = channelModeMessages.whatis(z) 
            if self.type == "LOCAL_CONTROL": 
                self.data = (tmpstr[2] == 0x7F) 
            elif self.type == "MONO_MODE_ON": 
                self.data = tmpstr[2] 
            return tmpstr[3:] 
        elif x == 0xF0 or x == 0xF7: 
            self.type = {0xF0: "F0_SYSEX_EVENT", 
                         0xF7: "F7_SYSEX_EVENT"}[x] 
            length, tmpstr = getVariableLengthNumber(tmpstr[1:]) 
            self.data = tmpstr[:length] 
            return tmpstr[length:] 
        elif x == 0xFF: 
            if not metaEvents.has_value(z): 
                print("Unknown meta event: FF %02X" % z) 
                sys.stdout.flush() 
                raise Exception("Unknown midi event type") 
            self.type = metaEvents.whatis(z) 
            length, tmpstr = getVariableLengthNumber(tmpstr[2:]) 
            self.data = tmpstr[:length] 
            return tmpstr[length:] 
        raise Exception("Unknown midi event type") 
    def write(self): 
        sysex_event_dict = {"F0_SYSEX_EVENT": 0xF0, 
                            "F7_SYSEX_EVENT": 0xF7} 
        if channelVoiceMessages.hasattr(self.type): 
            x = chr((self.channel - 1) + 
                    getattr(channelVoiceMessages, self.type)) 
            if (self.type != "PROGRAM_CHANGE" and 
                self.type != "CHANNEL_KEY_PRESSURE"): 
                data = chr(self.pitch) + chr(self.velocity) 
            else: 
                data = chr(self.data) 
            return x + data 
        elif channelModeMessages.hasattr(self.type): 
            x = getattr(channelModeMessages, self.type) 
            x = (chr(0xB0 + (self.channel - 1)) + 
                 chr(x) + 
                 chr(self.data)) 
            return x 
        elif self.type in sysex_event_dict: 
            tmpstr = chr(sysex_event_dict[self.type]) 
            tmpstr = tmpstr + putVariableLengthNumber(len(self.data)) 
            return tmpstr + str(self.data) 
        elif metaEvents.hasattr(self.type): 
            tmpstr = chr(0xFF) + chr(getattr(metaEvents, self.type)) 
            tmpstr = tmpstr + putVariableLengthNumber(len(self.data)) 
            return tmpstr + str(self.data) 
        else: 
            raise Exception("unknown midi event type: " + self.type) 
""" 
register_note() is a hook that can be overloaded from a script that 
imports this module. Here is how you might do that, if you wanted to 
store the notes as tuples in a list. Including the distinction 
between track and channel offers more flexibility in assigning voices. 
import midi 
notelist = [ ] 
def register_note(t, c, p, v, t1, t2): 
    notelist.append((t, c, p, v, t1, t2)) 
midi.register_note = register_note 
""" 
def register_note(track_index, channel_index, pitch, velocity, 
                  keyDownTime, keyUpTime): 
    pass 
class MidiChannel: 
    """A channel (together with a track) provides the continuity 
connecting 
    a NOTE_ON event with its corresponding NOTE_OFF event. Together, 
those 
    define the beginning and ending times for a Note.""" 
    def __init__(self, track, index): 
        self.index = index 
        self.track = track 
        self.pitches = { } 
    def __repr__(self): 
        return "<MIDI channel %d>" % self.index 
    def noteOn(self, pitch, time, velocity): 
        self.pitches[pitch] = (time, velocity) 
    def noteOff(self, pitch, time): 
        if pitch in self.pitches: 
            keyDownTime, velocity = self.pitches[pitch] 
            register_note(self.track.index, self.index, pitch, velocity, 
                          keyDownTime, time) 
            del self.pitches[pitch] 
        # The case where the pitch isn't in the dictionary is illegal, 
        # I think, but we probably better just ignore it. 
class DeltaTime(MidiEvent): 
    type = "DeltaTime" 
    def read(self, oldtmpstr): 
        self.time, newtmpstr = getVariableLengthNumber(oldtmpstr) 
        return self.time, newtmpstr 
    def write(self): 
        tmpstr = putVariableLengthNumber(self.time) 
        return tmpstr 
class MidiTrack: 
    def __init__(self, index): 
        self.index = index 
        self.events = [ ] 
        self.channels = [ ] 
        self.length = 0 
        for i in range(16): 
            self.channels.append(MidiChannel(self, i+1)) 
    def read(self, tmpstr): 
        time = 0 
        assert tmpstr[:4] == b"MTrk" 
        length, tmpstr = getNumber(tmpstr[4:], 4) 
        self.length = length 
        mytmpstr = tmpstr[:length] 
        remainder = tmpstr[length:] 
        while mytmpstr: 
            delta_t = DeltaTime(self) 
            dt, mytmpstr = delta_t.read(mytmpstr) 
            time = time + dt 
            self.events.append(delta_t) 
            e = MidiEvent(self) 
            mytmpstr = e.read(time, mytmpstr) 
            self.events.append(e) 
        return remainder 
    def write(self): 
        time = self.events[0].time 
        # build tmpstr using MidiEvents 
        tmpstr = "" 
        for e in self.events: 
            tmpstr = tmpstr + e.write() 
        return "MTrk" + putNumber(len(tmpstr), 4) + tmpstr 
    def __repr__(self): 
        r = "<MidiTrack %d -- %d events\n" % (self.index, 
len(self.events)) 
        for e in self.events: 
            r = r + "    " + repr(e) + "\n" 
        return r + "  >" 
class MidiFile: 
    def __init__(self): 
        self.file = None 
        self.format = 1 
        self.tracks = [ ] 
        self.ticksPerQuarterNote = None 
        self.ticksPerSecond = None 
    def open(self, filename, attrib="rb"): 
        if filename == None: 
            if attrib in ["r", "rb"]: 
                self.file = sys.stdin 
            else: 
                self.file = sys.stdout 
        else: 
            self.file = open(filename, attrib) 
    def __repr__(self): 
        r = "<MidiFile %d tracks\n" % len(self.tracks) 
        for t in self.tracks: 
            r = r + "  " + repr(t) + "\n" 
        return r + ">" 
    def close(self): 
        #self.file.close()
        pass
    def read(self): 
        self.readstr(self.file.read()) 
    def readstr(self, tmpstr): 
        assert tmpstr[:4] == b"MThd" 
        length, tmpstr = getNumber(tmpstr[4:], 4) 
        assert length == 6 
        format, tmpstr = getNumber(tmpstr, 2) 
        self.format = format 
        assert format == 0 or format == 1   # dunno how to handle 2 
        numTracks, tmpstr = getNumber(tmpstr, 2) 
        division, tmpstr = getNumber(tmpstr, 2) 
        if division & 0x8000: 
            framesPerSecond = -((division >> 8) | -128) 
            ticksPerFrame = division & 0xFF 
            assert ticksPerFrame == 24 or ticksPerFrame == 25 or \
                   ticksPerFrame == 29 or ticksPerFrame == 30 
            if ticksPerFrame == 29: ticksPerFrame = 30  # drop frame 
            self.ticksPerSecond = ticksPerFrame * framesPerSecond 
        else: 
            self.ticksPerQuarterNote = division & 0x7FFF 
        for i in range(numTracks): 
            trk = MidiTrack(i)
            #print('Track#%d' % i);
            tmpstr = trk.read(tmpstr) 
            self.tracks.append(trk) 
    def write(self): 
        self.file.write(self.writestr()) 
    def writestr(self): 
        division = self.ticksPerQuarterNote 
        # Don't handle ticksPerSecond yet, too confusing 
        assert (division & 0x8000) == 0 
        tmpstr = "MThd" + putNumber(6, 4) + putNumber(self.format, 2) 
        tmpstr = tmpstr + putNumber(len(self.tracks), 2) 
        tmpstr = tmpstr + putNumber(division, 2) 
        for trk in self.tracks: 
            tmpstr = tmpstr + trk.write() 
        return tmpstr 
def main(argv): 
    global debugflag 
    import getopt 
    infile = None 
    outfile = None 
    printflag = 0 
    optlist, args = getopt.getopt(argv[1:], "i:o:pd") 
    for (option, value) in optlist: 
        if option == '-i': 
            infile = value 
        elif option == '-o': 
            outfile = value 
        elif option == '-p': 
            printflag = 1 
        elif option == '-d': 
            debugflag = 1
    m = MidiFile() 
    m.open(infile) 
    m.read() 
    m.close() 
    if printflag: 
        print(m) 
    else: 
        m.open(outfile, "wb") 
        m.write() 
        m.close() 
if __name__ == "__main__":
    main(sys.argv) 
    

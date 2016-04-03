#!/usr/bin/env python
# coding: utf-8
import rtmidi
import time

send = rtmidi.MidiOut()
recv = rtmidi.MidiIn()
recv.ignore_types(False)  # Don't ignore sysex!

print repr(send.get_ports())
print repr(recv.get_ports())
remotePort = 4

send.open_port(remotePort)


def sender(msg):
    send.send_message((ord(c) for c in msg.replace(' ', '').decode('hex')))


class MPK2Sysex:
    akaiHeader = [0xf0, 0x47, 0x00]
    mpkID = {
        0x24: 'MPK249',
        0x25: 'MPK261',
        }
    padColors = {
        0x00: 'Off',
        0x01: 'Red',
        0x02: 'Orange',
        0x03: 'Amber',
        0x04: 'Yellow',
        0x05: 'Green',
        0x06: 'Green_Blue',
        0x07: 'Aqua',
        0x08: 'Light_Blue',
        0x09: 'Blue',
        0x0A: 'Purple',
        0x0B: 'Pink',
        0x0C: 'Hot_Pink',
        0x0D: 'Pastel_Purple',
        0x0E: 'Pastel_Green',
        0x0F: 'Pastel_Pink',
        0x10: 'Grey',
        }

    def pretty(self, data):
        return ' '.join('{:02x}'.format(i) for i in data)

    def bankName(self, bank):
        # A B C D
        return chr(65+bank)

    def msbPack(self, value):
        # In sysex, no byte can have MSB set, since 0xf7
        # marks end of sysex message. So we pack large numbers.
        loWord = value & 0x7f
        hiWord = (value >> 7)
        return [hiWord, loWord]

    def msbUnpack(self, data):
        (hiWord, loWord) = data
        return (hiWord << 7) | loWord

    def __init__(self, data):
        self._data = data

        header = self._data[:3]
        if header != MPK2Sysex.akaiHeader:
            raise Exception('Sysex message does not start with AKAI header, instead ' + self.pretty(header))

        mpkName = MPK2Sysex.mpkID[self._data[3]]
        print 'Received sysex message from AKAI ' + mpkName
        if mpkName is not 'MPK261':
            raise Exception('Sysex message not from MPK261, not going to try to parse it for now')

        msgSize = self.msbUnpack(self._data[5:7])
        expectedSize = 4+3+msgSize+1 # header + command + size bytes + message + 0xf7
        if len(self._data) != expectedSize:
            raise Exception('Sysex message appears to have wrong size! Expected %d, got %d' % (expectedSize, msgSize))

        command = self._data[4]
        if command is 0x10 :
            self.readPresetDump()

    def readPresetDump(self):
        presetId = self._data[7]
        if presetId == 0 or presetId > 30:
            raise Exception('Malformed preset dump? presetId = %d!' % presetId)
        presetName = ''.join((chr(i) for i in self._data[8:16]))
        print 'Preset:% 3u %8s' % (presetId, presetName)

        self.readKeyboardSpec()
        for bank in range(4):
            for pad in range(16):
                self.readPadSpec(bank, pad)
        for i in range(24):
            self.readSwitchSpec(i)
        for i in range(24):
            self.readFaderSpec(i)
        for i in range(24):
            self.readKnobSpec(i)
        self.readMiscSpec()

    def readKeyboardSpec(self):
        '''
            @ 0x01d:
            keyboard spec (21? bytes)
            [midi ch] [octave (0=4)] [01] [01] [00] [transpose (0=24)]

            @ 0x032:
            2x pedal spec (6 bytes)
            [cc / tap / play / rec / stop / playstop / arp / sustain] [midi ch] [midi cc] 00 00 00
        '''
        offset = 0x1d
        keyboardSpec = self._data[offset:offset+21]
        offset = 0x32
        foot1Spec = self._data[offset:offset+6]
        offset = 0x32 + 6
        foot2Spec = self._data[offset:offset+6]
        print 'Keyboard spec: ' + self.pretty(keyboardSpec)
        print 'Footswitch 1 spec: ' + self.pretty(foot1Spec)
        print 'Footswitch 2 spec: ' + self.pretty(foot2Spec)

    def readPadSpec(self, bank, pad):
        '''
            @ 0x03d:
            64x pad spec (11 bytes)
            [Note/Prgm] [Midi Ch] [Note#] [00] [00] [01] [pgm #] [00] [00] [Off color] [On color]
        '''
        offset = 0x3d + (bank*16 + pad)*11
        padSpec = self._data[offset:offset+11]
        print 'Bank %s Pad% 3u spec: ' % (self.bankName(bank+1), pad+1) + self.pretty(padSpec)

    def readSwitchSpec(self, switch):
        '''
            @ 0x465:
            24x switch spec (13 bytes)
            [cc / note / program change / ? ] [midi ch] [midi cc] [toggle/momentary] [program #] 00 00 00 [note val?] [note vel] 00 00 00
        '''
        offset = 0x465 + switch*13
        switchSpec = self._data[offset:offset+13]
        print 'Bank %s Switch %u spec: ' % (self.bankName(switch/8), switch%8+1) + self.pretty(switchSpec)

    def readKnobSpec(self, knob):
        '''
            @ 0x2fd:
            24x knob spec (9 bytes)
            [cc / aft / inc1 / inc2] [midi ch] [midi cc] 00 7f 00 7f 7f 01
        '''
        offset = 0x2fd + knob*9
        knobSpec = self._data[offset:offset+9]
        print 'Bank %s Knob %u spec: ' % (self.bankName(knob/8), knob%8+1) + self.pretty(knobSpec)

    def readFaderSpec(self, fader):
        '''
            @ 0x3d5:
            24x fader spec (6 bytes)
            [cc / aft] [midi ch] [midi cc] [min] [max] 00
        '''
        offset = 0x3df + fader*6
        faderSpec = self._data[offset:offset+6]
        print 'Bank %s Fader %u spec: ' % (self.bankName(fader/8), fader%8+1) + self.pretty(faderSpec)

    def readMiscSpec(self):
        '''
            @ 0x59d
            Not sure
            # 0x5e4:
            [foot1 type] [foot1 cc]
            @ 0x5f7:
            [split on] [split key] [B channel]
            < 117 values
        '''
        offset = 0x59d
        miscSpec = self._data[offset:offset+117]
        print 'Unknown spec: ' + self.pretty(miscSpec)

def callback(tup, extra):
    data, deltaT = tup
    message = MPK2Sysex(data)

recv.open_port(remotePort)
done = False
while not done:
    msg = recv.get_message()
    if msg:
        MPK2Sysex(msg[0])
        exit(0)
    time.sleep(0.1)


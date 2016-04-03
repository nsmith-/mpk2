# Use python -i (or ipython)
# coding: utf-8
import rtmidi

send = rtmidi.MidiOut()
recv = rtmidi.MidiIn()
recv.ignore_types(False) # Don't ignore sysex!

print repr(send.get_ports())
remotePort = 4

send.open_port(remotePort)

def sender(msg) :
    send.send_message((ord(c) for c in msg.replace(' ','').decode('hex')))

def callback(tup, data) :
    data, deltaT = tup
    dataNice = ' '.join('{:02x}'.format(i) for i in data)
    print
    print 'Received ' + dataNice

recv.open_port(remotePort)
recv.set_callback(callback)



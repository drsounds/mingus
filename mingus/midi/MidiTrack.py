"""

================================================================================

	mingus - Music theory Python package, MIDI Track
	Copyright (C) 2008, Bart Spaans

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

================================================================================

	The [refMingusMidiMiditrack MidiTrack] class is kept in this module 
	and provides methods for working with MIDI data as bytes.

	The MIDI file format specification I used can be found here:
	http://www.sonicspot.com/guide/midifiles.html

================================================================================

"""

from binascii import a2b_hex
from struct import pack, unpack
from math import log
from MidiEvents import *

class MidiTrack():
	"""This class is used to generate MIDI events from the
	objects in mingus.containers."""

	track_data = ''
	delta_time = '\x00'
	delay = 0
	bpm = 120

	def __init__(self, start_bpm = 120):
		self.track_data =''
		self.set_tempo(start_bpm)


	def end_of_track(self):
		"""Returns the bytes for an end of track meta event."""
		return "\x00\xff\x2f\x00"

	def play_Note(self, channel, note):
		"""Converts a Note object to a midi event and adds it \
to the track_data. You can set Note.parameters["velocity"] to adjust the \
speed with which the note should be hit [0-128]."""
		velocity = 64
		if hasattr(note, "dynamics"):
			if 'velocity' in note.dynamics:
				velocity = note.dynamics["velocity"]

		self.track_data += self.note_on(channel, int(note) + 12, velocity)

	def play_NoteContainer(self, channel, notecontainer):
		"""Converts a mingus.containers.NoteContainer to the \
equivalent midi events and adds it to the track_data."""
		if len(notecontainer) <= 1:
			[self.play_Note(channel, x) for x in notecontainer]
		else:
			self.play_Note(channel, notecontainer[0])
			self.set_deltatime(0)
			[self.play_Note(channel, x) for x in notecontainer[1:]]



	def play_Bar(self, channel, bar):
		"""Converts a Bar object to MIDI events and writes them \
to the track_data."""
		for x in bar:
			tick = int(round((1.0 / x[1] * 288)))
			if x[2] is None or len(x[2]) == 0:
				self.delay += tick
			else:
				self.set_deltatime(self.delay)
				self.delay = 0
				self.play_NoteContainer(channel, x[2])

				self.set_deltatime(self.int_to_varbyte(tick))
				self.stop_NoteContainer(channel, x[2])

	def play_Track(self, channel, track):
		"""Converts a Track object to MIDI events and writes \
them to the track_data."""
		self.delay = 0
		instr = track.instrument
		if hasattr(instr, "instrument_nr"):
			self.set_instrument(channel, instr.instrument_nr)
		for bar in track:
			self.play_Bar(channel, bar)


	def stop_Note(self, channel, note):
		"""Adds a note_off event for note to event_track"""
		velocity = 64
		if hasattr(note, "dynamics"):
			if 'velocity' in note.dynamics:
				velocity = note.dynamics["velocity"]

		self.track_data += self.note_off(channel, int(note) + 12,
					velocity)


	def stop_NoteContainer(self, channel, notecontainer):
		"""Adds note_off events for each note in the \
NoteContainer to the track_data."""

		# if there is more than one note in the container, 
		# the deltatime should be set back to zero after the 
		# first one has been stopped
		if len(notecontainer) <= 1:
			[self.stop_Note(channel, x) for x in notecontainer]
		else:
			self.stop_Note(channel, notecontainer[0])
			self.set_deltatime(0)
			[self.stop_Note(channel, x) for x in notecontainer[1:]]


	def set_instrument(self, channel, instr, bank = 1):
		"""Adds an program change and bank select event \
to the track_data"""
		self.track_data += self.select_bank(channel, bank)
		self.track_data += self.program_change_event(channel, instr)

	def header(self):
		"""Returns the bytes for the header of track. NB. \
The header contains the length of the track_data, so \
you'll have to call this function when you're done \
adding data (when you're not using get_midi_data)."""
		chunk_size = a2b_hex("%08x" % (len(self.track_data) +\
				len(self.end_of_track())))
		return TRACK_HEADER + chunk_size

	def get_midi_data(self):
		"""Returns the MIDI data in bytes for this track. \
Includes header, track_data and the end of track \
meta event."""
		return self.header() + self.track_data + self.end_of_track()

	def midi_event(self, event_type, channel, param1, param2 = None):
		"""Converts and returns the paraters as a MIDI event in bytes."""
		"""Parameters should be given as integers."""
		"""event_type and channel: 4 bits."""
		"""param1 and param2: 1 byte."""
		assert event_type < 128 and event_type >= 0
		assert channel < 16 and channel >= 0
		tc = a2b_hex("%x%x" % (event_type, channel))

		if param2 is None:
			params = a2b_hex("%02x" % (param1))
		else:
			params = a2b_hex("%02x%02x" % (param1, param2))
		return self.delta_time + tc + params


	def note_off(self, channel, note, velocity):
		"""Returns bytes for a `note off` event."""
		return self.midi_event(NOTE_OFF, channel, note, velocity)

	def note_on(self, channel, note, velocity):
		"""Returns bytes for a `note_on` event."""
		return self.midi_event(NOTE_ON, channel, note, velocity)

	def controller_event(self, channel, contr_nr, contr_val):
		"""Returns the bytes for a MIDI controller event."""
		return self.midi_event(CONTROLLER, channel, contr_nr, contr_val)

	def reset(self):
		"""Resets track_data and delta_time."""
		self.track_data = ''
		self.delta_time = '\x00'

	def set_deltatime(self, delta_time):
		"""Sets the delta_time. Can be an integer or a \
variable length byte."""
		if type(delta_time) == int:
			delta_time = self.int_to_varbyte(delta_time)

		self.delta_time = delta_time

	def select_bank(self, channel, bank):
		"""Returns the MIDI event for a select bank \
controller event."""
		return self.controller_event(BANK_SELECT, channel, bank)


	def program_change_event(self, channel, instr):
		"""Returns the bytes for a program change \
controller event."""
		return self.midi_event(PROGRAM_CHANGE, channel, instr)

	def set_tempo(self, bpm):
		"""Converts the bpm to a midi event and writes it to the track_data"""
		self.bpm = bpm
		self.track_data += self.set_tempo_event(self.bpm)


	def set_tempo_event(self, bpm):
		"""Calculates the microseconds per quarter note """
		"""and returns tempo event."""
		ms_per_min = 60000000
		mpqn = a2b_hex("%06x" % (ms_per_min / bpm))
		return self.delta_time + "\xff\x51\x03" + mpqn
		
	def int_to_varbyte(self, value):
		"""A lot of MIDI variables can be of variable length. \
This method converts an integer into a variable length byte. \
How it works: the bytes are stored in big-endian (significant bit first), \
the highest bit of the byte (mask 0x80) is set when there are more \
bytes following. The remaining 7 bits (mask 0x7F) are used to store the \
value."""
		# Warning: bit kung-fu ahead.
		# The length of the integer in bytes
		length = int(log(max(value, 1), 128)) + 1
	
		# Remove the highest bit and move the bits to the right
		# if length > 1
		bytes = [(value >> (i*7)) & 0x7F for i in range(length)]
		bytes.reverse()

		# Set the first bit on every one but the last bit.
		for i in range(len(bytes)-1):
			bytes[i] = bytes[i] | 0x80

		return pack('%sB' % len(bytes), *bytes)



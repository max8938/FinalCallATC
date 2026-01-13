import threading
import time
from dataclasses import dataclass, field

from typing import Callable, List
import sys

import mmap
import struct
import time
import json


POLLING_INTERVAL = 0.2	# seconds

MAC_PLATFORM = sys.platform == "darwin"



@dataclass
class RadioPanel:
	# fields
	COM1VolumeOutput: float = 1.0
	COM2VolumeOutput: float = 1.0
	NAV1VolumeOutput: float = 1.0
	NAV2VolumeOutput: float = 1.0
	#TransponderReply: float = 0.0
	TransponderIdentButton: float = 0.0
	TransponderCode: float = 0.0
	MicrophoneSelect: float = 0.0
	COM1AudioSelectButton: float = 1.0
	COM2AudioSelectButton: float = 0.0
	COM3AudioSelectButton: float = 0.0
	NAV1AudioSelectButton: float = 0.0
	NAV2AudioSelectButton: float = 0.0
	AUXAudioSelectButton: float = -1.0
	COM1Frequency: float = 0.0
	COM2Frequency: float = 0.0
	TransponderMode: float = 0.0
	PushSpeaker: float = 0.0
	AircraftName = None
	AircraftOnGround: float = -1.0
	AircraftOnRunway: float = -1.0
	AircraftLongitude: float = 0.0
	AircraftLatitude: float = 0.0
	AircraftTrueHeading: float = 0.0
	AircraftGroundSpeed: float = 0.0
	AircraftAltitude: float = 0.0
	
	# Mapping of variable names to shared memory keys/AF4 messages
	VARIABLE_MAP = {
			"COM1VolumeOutput": "Communication.COM1Volume",
			"COM2VolumeOutput": "Communication.COM2Volume",
			"MicrophoneSelect": "Communication.MicrophoneSelect",
			"COM1Frequency": "Communication.COM1Frequency",
			"COM2Frequency": "Communication.COM2Frequency",
			"COM1AudioSelectButton": "Communication.COM1AudioSelect",
			"COM2AudioSelectButton": "Communication.COM2AudioSelect",
			"AUXAudioSelectButton": "Communication.AUXAudioSelect",
			"TransponderCode": "Communication.TransponderCode",
			"TransponderIdentButton": "Communication.TransponderIdent",
			"TransponderMode":	"Communication.TransponderMode",  
			"AircraftOnGround": "Aircraft.OnGround",
			"AircraftOnRunway": "Aircraft.OnRunway",
			"AircraftLongitude": "Aircraft.Longitude",
			"AircraftLatitude": "Aircraft.Latitude",
			"AircraftTrueHeading": "Aircraft.TrueHeading",
			"AircraftGroundSpeed": "Aircraft.GroundSpeed",
			"AircraftAltitude": "Aircraft.Altitude",
			"AircraftName": "Aircraft.Name",
		}

	

	# Transmitting radio switch
	MICROPHONE_OUTPUT = {
		"c172": {
			"EMG": 0.0,
			"COM1": 1.0,
			"COM2": 2.0,
			"COM3": 3.0,
			"PA": 4.0,
		},
		"b58": {
			"COM1": 0.0,
			"COM2": 1.0,
			"AUX": 2.0,
			"EXT": 3.0,
		},
		"q400": {
			"COM1": 0.0,
			"COM2": 1.0,
			"AUX": 3.0,
			
		},
		"dr400": {
			"COM1": 0.0,
			
			
		},
		"c90gtx": {
			"COM1": 0.0,
			"COM2": 1.0,
			
		},
	}

	# Transponder modes
	TRANSPONDER_MODE = {
		"c172": {
			"OFF": 0.0,
			"SBY": 1.0,
			"TST": 2.0,
			"ON": 3.0,
			"ALT": 4.0,
		},
		"b58": {
			"OFF": 0.0,
			"SBY": 1.0,
			"ON": 2.0,
			"ALT": 3.0,
			"TST": 4.0,
		},
		"q400": {
			"OFF": 1.0,
			"ALT": 0.0,
			
		},
		"dr400": {
			"OFF": 0.0,
			"ON": 2.0,
			"ALT": 3.0,
			
		},
		"c90gtx": {
			"SBY": 1.0,
			"ALT": 4.0,
			
		},
	}

	_stop_flag: bool = field(default=False, init=False, repr=False)
	_thread: threading.Thread = field(default=None, init=False, repr=False)
	_callbacks: List[Callable[[str, float, float], None]] = field(default_factory=list, init=False, repr=False)
	
	def __new__(cls, enablePanel):
		if MAC_PLATFORM:
			print("RadioPanel: Mac platform is not supported.")
			return None
		elif not enablePanel:
			print("RadioPanel: Panel disabled in settings.")
			return None
			
		return super().__new__(cls)

	def __init__(self, enablePanel):
		
		
		
		self._stop_flag = False
		self._thread = None
		self._callbacks = []
	

	def add_callback(self, func: Callable[[str, float, float], None]):
		"""Register a function to be called on value change.
		Callback signature: (name, old_value, new_value)."""
		self._callbacks.append(func)

	shm = None
	
	def start_polling(self, interval: float = 0.2):
		"""Start background thread to refresh values every `interval` seconds."""
		self._stop_flag = False
		
		global shm
		
		# Open shared memory (matches the name in C++)
		try:
			shm = mmap.mmap(-1, 65536, "Local\\AeroflyFS4Data", access=mmap.ACCESS_READ)
		except FileNotFoundError:
			print("Shared memory not found. Is the game running with the DLL loaded?")
		except KeyboardInterrupt:
			print("\nStopped")
			if 'shm' in locals():
				shm.close()
		
			

		def _poll_loop():
			while not self._stop_flag:
				try:
					# Read from shared memory
					shm.seek(0)
					data = shm.read(65536)
					
					# Find the null terminator
					null_pos = data.find(b'\x00')
					if null_pos > 0:
						json_str = data[:null_pos].decode('utf-8')
						
						# Parse JSON
						game_data = json.loads(json_str)
					
						# Print all available keys (optional)
						#print(f"\nAvailable data keys: {list(game_data.keys())}")
						
						for name, message in self.VARIABLE_MAP.items():
							new_val = game_data.get(message, -9999) 
							if new_val == -9999: # key not found, do not update this value
								continue
							
							old_val = getattr(self, name)

							if new_val != old_val:  # only trigger if value changed
								# Ignore jumps to 0.0 for volume, that happens when volume control is grabbed in VR
								if "VolumeOutput" in name and new_val == 0.0:
									continue

								setattr(self, name, new_val)

								# Do not send callback for heading, speed, location and altitude changes
								if name in ["AircraftTrueHeading", "AircraftLongitude", "AircraftLatitude", "AircraftAltitude", "AircraftGroundSpeed"]:
									continue

								for cb in self._callbacks:
									cb(name, old_val, new_val)
				except json.JSONDecodeError as e:
					print(f"JSON decode error: {e}")
				except KeyboardInterrupt:
					print("\nStopped")
				
				
				time.sleep(interval)

		self._thread = threading.Thread(target=_poll_loop, daemon=True)
		self._thread.start()

	def stop_polling(self):
		"""Stop the background polling thread."""
		self._stop_flag = True
		
		if 'shm' in locals():
				shm.close()
				
		if self._thread:
			self._thread.join(timeout=1.0)
			self._thread = None



def on_change(name, old, new):
	print(f"{name} changed: {old} to {new}")

# for testing
def main():
	panel = RadioPanel(True)
	panel.add_callback(on_change)
	panel.start_polling(POLLING_INTERVAL)

	
	# now values are auto-updated
	while True:
		time.sleep(1)
		#print("COM1:", panel.COM1VolumeOutput, "COM2:", panel.COM2VolumeOutput)
		#for name in panel.OFFSETS["b58"].keys():
			#value = getattr(panel, name)
			#print(f"{name}: {value}")
	panel.stop_polling()


if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		print("The program crashed with an error:")
		print(e)
		input("Press Enter to close the window...")

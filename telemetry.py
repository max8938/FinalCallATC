import socket
import struct
import datetime
from datetime import datetime
from typing import Optional, Dict, List, Any
import threading

#Aerofly UDP packet examples:
# XATT<simulator_name>,<true_heading>,<pitch_degrees>,<roll_degrees>
# XATTAerofly FS 4,341.5,5.91,0.52
# XGPS<simulator_name>,<longitude>,<latitude>,<altitude_msl>,<track_true_north>,<groundspeed_m/s>
# XGPSAerofly FS 4,13.0042,47.7931,429.1,341.5,0.0

# Multicast configuration
MULTICAST_GROUP = '239.255.50.10'  # Common MSFS/X-Plane multicast group
PORT = 49002
BUFFER_SIZE = 4096

TELEMETRY_SEND_INTERVAL=60.0 #in seconds


class Attitude:
    def __init__(
        self,
        true_heading: float,
        pitch_degrees: float,
        roll_degrees: float,
        timestamp: datetime
    ):
        """
        Represents an aircraft's attitude in 3D space.
        
        Args:
            true_heading (float): Direction the aircraft is pointing (0� to 360�).
            pitch_degrees (float): Nose-up/nose-down angle (-90� to +90�).
            roll_degrees (float): Left/right wing tilt (-180� to +180�).
        """
        self.true_heading = true_heading
        self.pitch_degrees = pitch_degrees
        self.roll_degrees = roll_degrees
        self.timestamp = datetime.now()

    @property
    def true_heading(self) -> float:
        return self._true_heading

    @true_heading.setter
    def true_heading(self, value: float):
        if not (0 <= value <= 360):
            raise ValueError("True heading must be between 0� and 360�.")
        self._true_heading = value

    @property
    def pitch_degrees(self) -> float:
        return self._pitch_degrees

    @pitch_degrees.setter
    def pitch_degrees(self, value: float):
        if not (-90 <= value <= 90):
            raise ValueError("Pitch must be between -90� and +90�.")
        self._pitch_degrees = value

    @property
    def roll_degrees(self) -> float:
        return self._roll_degrees

    @roll_degrees.setter
    def roll_degrees(self, value: float):
        if not (-180 <= value <= 180):
            raise ValueError("Roll must be between -180� and +180�.")
        self._roll_degrees = value
        
    @property
    def timestamp(self) -> datetime:
        return self._timestamp
        
    def timestamp(self, value: datetime):
        self._timestamp = value

    def __repr__(self) -> str:
        return (
            f"Attitude("
            f"true_heading={self.true_heading}�, "
            f"pitch={self.pitch_degrees}�, "
            f"roll={self.roll_degrees}�)"
        )

    def to_dict(self) -> dict:
        """Convert the Attitude object to a dictionary."""
        return {
            "true_heading": self.true_heading,
            "pitch_degrees": self.pitch_degrees,
            "roll_degrees": self.roll_degrees,
        }
        
        
class Location:
    def __init__(
        self,
        longitude: float,
        latitude: float,
        altitude_msl: float,
        track_true_north: float,
        groundspeed_m_s: float,
        timestamp: datetime
    ):
        """
        Represents a geographic location with motion attributes.
        
        Args:
            longitude (float): Decimal degrees (-180 to +180).
            latitude (float): Decimal degrees (-90 to +90).
            altitude_msl (float): Meters above mean sea level (>= 0).
            track_true_north (float): True track angle (0� to 360�).
            groundspeed_m_s (float): Ground speed in meters/second (>= 0).
        """
        self.longitude = longitude
        self.latitude = latitude
        self.altitude_msl = altitude_msl
        self.track_true_north = track_true_north
        self.groundspeed_m_s = groundspeed_m_s
        self.timestamp = datetime.now()

    # --- Properties with Validation ---
    @property
    def longitude(self) -> float:
        return self._longitude

    @longitude.setter
    def longitude(self, value: float):
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180� and +180�.")
        self._longitude = value

    @property
    def latitude(self) -> float:
        return self._latitude

    @latitude.setter
    def latitude(self, value: float):
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90� and +90�.")
        self._latitude = value

    @property
    def altitude_msl(self) -> float:
        return self._altitude_msl

    @altitude_msl.setter
    def altitude_msl(self, value: float):
        if value < 0:
            raise ValueError("Altitude (MSL) must be >= 0 meters.")
        self._altitude_msl = value

    @property
    def track_true_north(self) -> float:
        return self._track_true_north

    @track_true_north.setter
    def track_true_north(self, value: float):
        if not 0 <= value <= 360:
            raise ValueError("Track angle must be between 0� and 360�.")
        self._track_true_north = value

    @property
    def groundspeed_m_s(self) -> float:
        return self._groundspeed_m_s

    @groundspeed_m_s.setter
    def groundspeed_m_s(self, value: float):
        if value < 0:
            raise ValueError("Ground speed must be >= 0 m/s.")
        self._groundspeed_m_s = value
        
    @property
    def timestamp(self) -> datetime:
        return self._timestamp
        
    
    def timestamp(self, value: datetime):
        self._timestamp = value
        
    # --- Utility Methods ---
    
    def __repr__(self) -> str:
        return (
            f"Location("
            f"lon={self.longitude:.6f}�, "
            f"lat={self.latitude:.6f}�, "
            f"alt={self.altitude_msl:.1f}m MSL, "
            f"track={self.track_true_north:.1f}�, "
            f"speed={self.groundspeed_m_s:.1f} m/s)"
        )
    
    def to_dict(self) -> dict:
        """Convert to a dictionary (e.g., for JSON serialization)."""
        return {
            "longitude": self.longitude,
            "latitude": self.latitude,
            "altitude_msl": self.altitude_msl,
            "track_true_north": self.track_true_north,
            "groundspeed_m_s": self.groundspeed_m_s
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create a Location object from a dictionary."""
        return cls(
            longitude=data["longitude"],
            latitude=data["latitude"],
            altitude_msl=data["altitude_msl"],
            track_true_north=data["track_true_north"],
            groundspeed_m_s=data["groundspeed_m_s"]
        )


class Telemetry:
	current_attitude: Optional[Attitude] = None
	current_location: Optional[Location] = None
	
	def __init__(self):
		threading.Thread(target=self.receiveTelemetry).start()

	def parse_telemetry_string(self,telemetry_str: str):
		"""
		Parses a telemetry string and returns either an Attitude or Location object.

		https://support.foreflight.com/hc/en-us/articles/204115005-Flight-Simulator-GPS-Integration-UDP-Protocol

		Supported formats:
		- Attitude: "XATT<simulator_name>,<true_heading>,<pitch_degrees>,<roll_degrees>"
		- Location: "XGPS<simulator_name>,<longitude>,<latitude>,<altitude_msl>,<track_true_north>,<groundspeed_m/s>"

		Args:
			telemetry_str: The input telemetry string

		Returns:
			Attitude or Location object if parsing succeeds

		Raises:
			ValueError: If the string is malformed or values are invalid
		"""
		#if not (telemetry_str.startswith("XATT") or telemetry_str.startswith("XGPS")):
		#    raise ValueError("String must start with either 'XATT' or 'XGPS'")
		global current_attitude
		global current_location

		if telemetry_str.startswith("XTRAFFIC"):
			print("!!!!!!!!!!!!!!! telemetry TRAFFIC info received: " + telemetry_str) # not implemented yet in Aerofly

		parts = telemetry_str.split(',')

		try:
			if telemetry_str.startswith("XATT"):
				if len(parts) != 4:
					raise ValueError(f"XATT string requires 4 values, got {len(parts)}")
			
				# Extract values (ignore simulator name)
				self.current_attitude = Attitude(
					true_heading=float(parts[1]),
					pitch_degrees=float(parts[2]),
					roll_degrees=float(parts[3]),
					timestamp=datetime.now()
				)
			 
				#print("Got attitude: ", current_attitude)
				#print(f"Parsed Attitude: {self.current_attitude}")
										
			elif telemetry_str.startswith("XGPS"):
				if len(parts) != 6:
					raise ValueError(f"XGPS string requires 6 values, got {len(parts)}")
			
				self.current_location = Location(
					longitude=float(parts[1]),
					latitude=float(parts[2]),
					altitude_msl=float(parts[3]),
					track_true_north=float(parts[4]),
					groundspeed_m_s=float(parts[5]),
					timestamp=datetime.now()
				)
				#print("Got location: ", current_location)
				#print(f"Parsed Location: {self.current_location}")
			
		except (IndexError, ValueError) as e:
			raise ValueError(f"Failed to parse values: {e}")

	def receiveTelemetry(self):
		# Create a UDP socket
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	
		# Bind to the port
		sock.bind(('', PORT))
	
		# Join the multicast group
		mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
		sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
	
		print(f"Listening for telemetry data on {MULTICAST_GROUP}:{PORT}...")
	
		# Enable this to send telemetry to AI periodically, separate from the spoken info
		#send_telemetry_update()
	
		try:
			while True:
				# Receive data
				data, addr = sock.recvfrom(BUFFER_SIZE)
			
				#print("data: ", data.decode('utf-8'))
				self.parse_telemetry_string(data.decode('utf-8'))
				'''
				try:
					# Parse JSON and print formatted output
					telemetry = json.loads(data.decode('utf-8'))
					print(json.dumps(telemetry, indent=2))
				except json.JSONDecodeError:
					print("Received non-JSON data:", data)
				  '''
		except KeyboardInterrupt:
			print("\nStopping telemetry capture...")
		finally:
			sock.close()
        


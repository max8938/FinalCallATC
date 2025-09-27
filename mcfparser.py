import re
from typing import List, Optional, Callable, Dict, Any
from enum import Enum
from dataclasses import dataclass
import math

class MissionCheckpointType(Enum):
	ORIGIN = "origin"
	DEPARTURE_RUNWAY = "departure_runway"
	DEPARTURE = "departure"
	WAYPOINT = "waypoint"
	ARRIVAL = "arrival"
	APPROACH = "approach"
	DESTINATION_RUNWAY = "destination_runway"
	DESTINATION = "destination"

@dataclass
class MainMcfWaypoint:
	type: MissionCheckpointType
	Identifier: str
	Position: List[float]
	Direction: List[float]
	NavaidFrequency: float
	Elevation: float
	Altitude: List[float]
	Length: float
	FlyOver: bool

@dataclass
class MainMcf:
	aircraft: Dict[str, Any]
	flight_setting: Dict[str, Any]
	time_utc: Dict[str, Any]
	visibility: float
	wind: Dict[str, Any]
	clouds: Dict[str, Any]
	navigation: Dict[str, Any]

class FileParser:
	def get_number(self, subject: str, key: str, default_value: float = 0) -> float:
		try:
			return float(self.get_value(subject, key, str(default_value)))
		except (ValueError, TypeError):
			return default_value
	
	def set_number(self, subject: str, key: str, value: float) -> str:
		return self.set_value(subject, key, str(value))
	
	def get_number_array(self, subject: str, key: str) -> List[float]:
		value = self.get_value(subject, key)
		if not value:
			return []
		try:
			return [float(i.strip()) for i in value.split() if i.strip()]
		except (ValueError, TypeError):
			return []
	
	def get_value(self, subject: str, key: str, default_value: str = "") -> str:
		if not subject:
			return default_value
			
		pattern = rf"(?:\]\s*\[{re.escape(key)}\]\s*\[)([^\]]*)(?:\])"
		match = re.search(pattern, subject)
		return match.group(1).strip() if match else default_value
	
	def get_values(self, subject: str, key: str) -> List[str]:
		if not subject:
			return []
			
		pattern = rf"(?:\]\s*\[{re.escape(key)}\]\s*\[)([^\]]*)(?:\])"
		matches = re.findall(pattern, subject)
		return [match.strip() for match in matches] if matches else []
	
	def set_value(self, subject: str, key: str, value: str) -> str:
		if value is None:
			return subject
		pattern = rf"(\]\[{re.escape(key)}\]\[)[^\]]*(\])"
		replacement = rf"\1{value}\2"
		return re.sub(pattern, replacement, subject)
	
	def get_group(self, subject: str, group: str, indent: int = 2) -> str:
		if not subject:
			return ""
			
		indent_string = "    " * indent
		pattern = rf"\n{re.escape(indent_string)}<\[{re.escape(group)}\][\s\S]+?\n{re.escape(indent_string)}>"
		match = re.search(pattern, subject)
		return match.group(0) if match else ""
	
	def get_groups(self, subject: str, group: str, indent: int = 2) -> List[str]:
		if not subject:
			return []
			
		indent_string = "    " * indent
		pattern = rf"\n{re.escape(indent_string)}<\[{re.escape(group)}\][\s\S]+?\n{re.escape(indent_string)}>"
		matches = re.findall(pattern, subject)
		return list(matches) if matches else []
	
	def set_group(self, subject: str, group: str, indent: int, callback: Callable[[str], str]) -> str:
		indent_string = "    " * indent
		
		def replacer(match: re.Match) -> str:
			return callback(match.group(0))
		
		pattern = rf"(\n{re.escape(indent_string)}<\[{re.escape(group)}\]\S*)([\s\S]+?)(\n{re.escape(indent_string)}>)"
		return re.sub(pattern, replacer, subject)

class MainMcfFactory(FileParser):
	def create(self, config_file_content: str) -> MainMcf:
		m = MainMcf(
			aircraft={"name": ""},
			flight_setting={
				"position": [0, 0, 0],
				"orientation": [0, 0, 0],
				"configuration": "",
				"on_ground": True
			},
			time_utc={
				"time_year": 0,
				"time_month": 0,
				"time_day": 0,
				"time_hours": 0
			},
			visibility=0,
			wind={
				"strength": 0,
				"direction_in_degree": 0,
				"turbulence": 0,
				"thermal_activity": 0
			},
			clouds={
				"cumulus_density": 0,
				"cumulus_height": 0,
				"cumulus_mediocris_density": 0,
				"cumulus_mediocris_height": 0,
				"cirrus_height": 0,
				"cirrus_density": 0
			},
			navigation={
				"Route": {
					"CruiseAltitude": -1,
					"Ways": []
				}
			}
		)
		
		tmsettings_aircraft = self.get_group(config_file_content, "tmsettings_aircraft")
		tmsettings_flight = self.get_group(config_file_content, "tmsettings_flight")
		tm_time_utc = self.get_group(config_file_content, "tm_time_utc")
		tmsettings_wind = self.get_group(config_file_content, "tmsettings_wind")
		tmsettings_clouds = self.get_group(config_file_content, "tmsettings_clouds")
		tmnav_route = self.get_group(config_file_content, "tmnav_route", 3)
		list_tmmission_checkpoint = self.get_group(config_file_content, "pointer_list_tmnav_route_way", 4)
		
		waypoints = []
		if list_tmmission_checkpoint:
			waypoint_sections = list_tmmission_checkpoint.split("<[tmnav_route_")[1:]
			
			for wp in waypoint_sections:
				type_match = None
				if wp:
					bracket_pos = wp.find(']')
					if bracket_pos != -1:
						type_match = wp[:bracket_pos]
				
				try:
					checkpoint_type = MissionCheckpointType(type_match) if type_match else MissionCheckpointType.WAYPOINT
				except ValueError:
					checkpoint_type = MissionCheckpointType.WAYPOINT
				
				waypoint = MainMcfWaypoint(
					type=checkpoint_type,
					Identifier=self.get_value(wp, "Identifier", ""),
					Position=self.get_number_array(wp, "Position"),
					Direction=self.get_number_array(wp, "Direction"),
					NavaidFrequency=self.get_number(wp, "NavaidFrequency", 0),
					Elevation=self.get_number(wp, "Elevation", 0),
					Altitude=self.get_number_array(wp, "Altitude"),
					Length=self.get_number(wp, "RunwayLength", 0),
					FlyOver=self.get_value(wp, "FlyOver", "false").lower() != "false"
				)
				waypoints.append(waypoint)
		
		# Set all the parsed values
		m.aircraft["name"] = self.get_value(tmsettings_aircraft, "name", "c172")
		
		m.flight_setting["position"] = self.get_number_array(tmsettings_flight, "position") or [0, 0, 0]
		m.flight_setting["orientation"] = self.get_number_array(tmsettings_flight, "orientation") or [0, 0, 0]
		m.flight_setting["configuration"] = self.get_value(tmsettings_flight, "configuration", "")
		m.flight_setting["on_ground"] = self.get_value(tmsettings_flight, "on_ground", "true").lower() == "true"
		
		m.time_utc["time_year"] = self.get_number(tm_time_utc, "time_year", 0)
		m.time_utc["time_month"] = self.get_number(tm_time_utc, "time_month", 0)
		m.time_utc["time_day"] = self.get_number(tm_time_utc, "time_day", 0)
		m.time_utc["time_hours"] = self.get_number(tm_time_utc, "time_hours", 0)
		
		m.visibility = self.get_number(config_file_content, "visibility", 0)
		
		m.wind["strength"] = self.get_number(tmsettings_wind, "strength", 0)
		m.wind["direction_in_degree"] = self.get_number(tmsettings_wind, "direction_in_degree", 0)
		m.wind["turbulence"] = self.get_number(tmsettings_wind, "turbulence", 0)
		m.wind["thermal_activity"] = self.get_number(tmsettings_wind, "thermal_activity", 0)
		
		m.clouds["cumulus_density"] = self.get_number(tmsettings_clouds, "cumulus_density", 0)
		m.clouds["cumulus_height"] = self.get_number(tmsettings_clouds, "cumulus_height", 0)
		m.clouds["cumulus_mediocris_density"] = self.get_number(tmsettings_clouds, "cumulus_mediocris_density", 0)
		m.clouds["cumulus_mediocris_height"] = self.get_number(tmsettings_clouds, "cumulus_mediocris_height", 0)
		m.clouds["cirrus_height"] = self.get_number(tmsettings_clouds, "cirrus_height", 0)
		m.clouds["cirrus_density"] = self.get_number(tmsettings_clouds, "cirrus_density", 0)
		
		m.navigation["Route"]["CruiseAltitude"] = self.get_number(tmnav_route, "CruiseAltitude", -1)
		m.navigation["Route"]["Ways"] = waypoints
		
		return m

# Convert cartasian coordinates to lat and long
def ecef_to_lla(x, y, z):
	# WGS84 constants
	a = 6378137.0             # semi-major axis (m)
	f = 1 / 298.257223563     # flattening
	e2 = f * (2 - f)          # eccentricity squared
	b = a * (1 - f)           # semi-minor axis
	ep2 = (a**2 - b**2) / b**2  # second eccentricity squared

	# Longitude
	lon = math.atan2(y, x)

	# Distance from Z axis
	p = math.sqrt(x**2 + y**2)

	# Initial parametric latitude
	theta = math.atan2(z * a, p * b)

	# Latitude
	sin_theta = math.sin(theta)
	cos_theta = math.cos(theta)
	lat = math.atan2(
		z + ep2 * b * sin_theta**3,
		p - e2 * a * cos_theta**3
	)

	# Radius of curvature in the prime vertical
	N = a / math.sqrt(1 - e2 * math.sin(lat)**2)

	# Altitude
	alt = p / math.cos(lat) - N

	# Convert to degrees
	lat_deg = math.degrees(lat)
	lon_deg = math.degrees(lon)

	return lat_deg, lon_deg, alt
	



	
def offset_position(dest, vec, dist_km):
	"""
	Compute a new position dist_km in the opposite direction of vec from dest.

	Parameters:
		dest (tuple): (x, y, z) ECEF coords of destination [meters]
		vec (tuple): (dx, dy, dz) direction vector (will be normalized)
		dist_km (float): distance in kilometers to move

	Returns:
		dict with:
		  - 'ecef': (x_new, y_new, z_new)
		  - 'lla': (lat_deg, lon_deg, alt_m)
	"""
	x, y, z = dest
	dx, dy, dz = vec

	# Normalize vector
	norm = math.sqrt(dx*dx + dy*dy + dz*dz)
	dx /= norm
	dy /= norm
	dz /= norm

	# Opposite direction
	dx, dy, dz = -dx, -dy, -dz

	# Distance in meters
	d = dist_km * 1000.0

	# New ECEF position
	x_new = x + dx * d
	y_new = y + dy * d
	z_new = z + dz * d

	# Convert to LLA
	lat_deg, lon_deg, alt_m = ecef_to_lla(x_new, y_new, z_new)

	return {
		"ecef": (x_new, y_new, z_new),
		"lla": (lat_deg, lon_deg, alt_m)
	}


# Example usage
#dest = (4271018.623391, 641046.897351407, 4677673.13707566)  # Runway threshold
#vec  = (0.597571566448455, 0.517542039305527, -0.61242016665343)  # Approach direction
#dist_km = 5  # 5 km back on approach

#result = offset_position(dest, vec, dist_km)

#print("New ECEF:", result["ecef"])
#print("New LLA:", result["lla"])	
		
def main():
	# Create the parser factory
	parser = MainMcfFactory()
	
	try:
		# Read the main.mcf file
		with open('main.mcf', 'r', encoding='utf-8') as file:
			mcf_content = file.read()
		
		# Parse the content
		parsed_data = parser.create(mcf_content)
		
		# Access the parsed data
		print(f"Aircraft: {parsed_data.aircraft['name']}")
		print(f"Position: {parsed_data.flight_setting['position']}")
		print(f"Visibility: {parsed_data.visibility}")
		print(f"Wind Strength: {parsed_data.wind['strength']}")
		print(f"Wind direction_in_degree: {parsed_data.wind['direction_in_degree']}")
		
		# Access waypoints
		print(f"\nNumber of waypoints: {len(parsed_data.navigation['Route']['Ways'])}")
		for i, waypoint in enumerate(parsed_data.navigation['Route']['Ways']):
			print(f"Waypoint {i+1}: {waypoint.Identifier} at {waypoint.Position}. Type:{waypoint.type} ")
			
	except FileNotFoundError:
		print("Error: main.mcf file not found")
	except Exception as e:
		print(f"Error parsing file: {e}")

if __name__ == "__main__":
	main()
# activate environment in ATC folder on Mac: source <environment name>/bin/activate


# SETTINGS
# NOT ACTIVE AT THE MOMENT How often should telemetry be sent to AI (besides sending with user messages), in seconds
TELEMETRY_SEND_INTERVAL=60.0 

RADIO_CHATTER_TIMER = 15.0 # How often will system attempt to create radio chatter between other stations, in seconds
RADIO_CHATTER_PROBABILITY = 100.0 # 0.0-100.0 (in %), chance of radio chatter being generated each RADIO_CHATTER_TIMER interval. Set to 0.0 to disable.
# For smaller airports (less frequencies), the chatter will be generated a bit less often. Chatter on GUARD (121.5) is rare and frequent on CENTER (134.0).

# Set to true to use DeepSeek AI, or False to use OpenAI. At the moment, DeepSeek creates a bit better conversation but takes 2-3 seconds more to respond.
USE_DEEPSEEK = True

# AI models to use
DEEPSEEK_MODEL = "deepseek-chat"
OPENAI_MODEL = "gpt-4.1-mini"

# Enable interaction with the radio panel (COM1/COM2 frequencies, audio routing, transponder)
# Currently suported only on Windows, for Cessna 172 and Baron 58 in Aerofly FS4
ENABLE_RADIO_PANEL = True

# VR controller mapping for Push to Talk. Assume controller 1 is at device index 1.
VR_CONTROLLER_INDEX = 1
VR_CONTROLLER_BUTTON_ID = 1 

# END OF SETTINGS

from telemetry import Telemetry, Attitude, Location
import RadioPanel
import mcfparser
import glob

import pygame

import json
import threading
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
import random
import math
from dotenv import load_dotenv


import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont
import sys
import os
import io
import atexit
from pydub import AudioSegment, effects


from pydub.generators import WhiteNoise

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

import threading

import azure.cognitiveservices.speech as speechsdk

from openai import OpenAI

MAC_PLATFORM = sys.platform == "darwin"

if sys.platform == "win32":
    from pycaw.pycaw import AudioUtilities
    import openvr
elif sys.platform == "darwin":
    pass

PHONETIC_ALPHABET = [
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf",
        "Hotel", "India", "Juliett", "Kilo", "Lima", "Mike", "November",
        "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform",
        "Victor", "Whiskey", "X-ray", "Yankee", "Zulu"
    ]


GAME_VARIABLES_POLLING_INTERVAL = 0.2 # Reading interval for state of radio panel controls, in seconds

#Aerofly config file 
mcf_path = None
if sys.platform == "win32":
    mcf_path = os.path.join(os.environ["USERPROFILE"], "Documents\\Aerofly FS 4\\main.mcf")
elif sys.platform == "darwin":
    mcf_path = os.path.expanduser("~/Library/Application Support/Aerofly FS 4/main.mcf")


WIND_SPEED_100_PERCENT_IN_KNOTS = 16.0

DEEPSEEK_API_KEY = None
MSSPEECH_API_KEY=None
MSSPEECH_API_REGION=None
OPENAI_API_KEY = None


ATC_INIT_INSTRUCTIONS="""I want you to roleplay ATC in my flight sim. I will send you plane attitude and location updates, and you should use that info to communicate with me in the same way a real ATC would. 
- Do not make up any telemetry like altitude, heading and airspeed; use only data received from me. 
- If you see me make an error or not follow instructions, you will warn me as an atc would do. 
- If I do not communicate as expected, you should warn me about that as well. 
- Format your response as JSON, except when calling a tool/function. The response should contain what ATC says to me (without any other comments) in ATC_VOICE variable. You can send blank ATC_VOICE variable if there is nothing new that needs to be communicated to the pilot. Output only pure JSON-compliant text, do not use any markdown code.
- Put any comments or notes in COMMENTS variable.  
- If readback from pilot is required for the instructions sent by ATC, write 15 in READBACK_TIMEOUT variable, this is the timeout in seconds. Do not say that readback is required. If you do not receive a correct readback after READBACK_TIMEOUT elapses, ask for a radio check or if I copy. 
- Put the name of the entity you are representing, like Paris Tower, in variable ENTITY. 
- Put the frequency of the sender in FREQUENCY variable, or 0 if unknown. 
- If I deviate from ATC instructions behave as real ATC would. 
- If any numbers are typically read digit by digit, write them using letters, not digits.  
- Ignore small mispronunciations on my side. 
- Do not give takeoff clearance until I confirm that I am holding at runway. 
- When I request vector or a heading, keep in mind what is my current location and heading in order to calculate the correct vector. If I read back another heading, assume that yours was incorrect and that mine is correct. 
- Ignore minor deviations from the agreed heading, speed, altitude, etc. 
- Warn me if I am entering protected airspace without authorization. 
- If I do not respond to urgent messages, try sending them on guard frequency 121.5 MHz. 
- Always respond on the same frequency that I sent the message on, including guard frequency. 
- Always respond as the entity on that frequency, not another one. 
- Use function get_heading_to_approach_point to get the heading and the distance to the destination approach point. 
- AFIS service does not issue clearances, only advisories. 
- React to my transponder code appropriately."""
ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN = ""

RADIO_CHATTER_GENERATION_PROMPT = "When I ask, you will generate a single exchange between a pilot and ATC. It should be relevant considering the description of the ATC frequency. It can be initiated either by the pilot or the ATC.  Output as JSON dictionary with keys MESSAGE1_ENTITY, MESSAGE2_ENTITY (names of the entities sending the messages, like: pilot, berlin ground, paris tower), MESSAGE1_TEXT and MESSAGE2_TEXT (contents of the radio messages). Do not put anything else in JSON. Use any worldwide airline if on big airport and random callsigns/flight numbers. For medium airports, use regional companies. For small airfields, use just GA callsigns.Do not repeat same requests from same entities. AFIS service does not issue clearances, only advisories."

FEET_IN_METER = 3.28084

VOICES = ['en-US-EmmaMultilingualNeural', 'en-US-GuyNeural', 'en-US-AndrewMultilingualNeural', 'en-US-SteffanMultilingualNeural', 'en-US-DerekMultilingualNeural', 'en-US-ChristopherNeural', 'en-US-RyanMultilingualNeural', 'en-US-DavisNeural', 'en-US-KaiNeural', 'en-US-TonyNeural', 'en-US-CoraMultilingualNeural']

# Distance in nautical miles that each type of radio can be heard from the airport
RADIO_REACH = {
        "TWR": 10.0,
		"GND": 5.0,
		"ATIS": 70.0,
		"AFIS": 20.0,
		"A/D": 50.0,
		"ARR": 60.0,
		"APP/DEP": 50.0,
		"ARR/DEP": 50.0,
		"APP": 50.0,
		"DEP": 50.0,
		"GUARD": 99999.0,
		"CENTER": 99999.0,
		"OTHER": 15.0
    }



ATC_AI_TOOLS = [
			{
				"type": "function",
				"function": {
					"name": "get_heading_to_approach_point",
					"description": "Get flight heading and destination from user's current location to the location of the runway approach start waypoint.",
					"parameters": {
						"type": "object",
						"properties": {
							"current_latitude": {
								"type": "number",
								"description": "User's current latitude",
							},
							"current_longitude": {
								"type": "number",
								"description": "User's current_longitude",
							}
						},
						"required": []
					},
				}
			},
		]

communicationWithAIInProgress = False
radioOn = True
atc_text_box = None
entityVoices = {}
speech_config = None
parsedAIResponse = None
radioPanel = None
gameTelemetry: Optional[Telemetry] = None
atcSessionStarted = False
atisPlaying = False
atisPlayingOnRadio = ""
atisThread = None
atcSoundCOM1 = None
atcSoundCOM2 = None
atcChannelCOM1 = None
atcChannelCOM2 = None
current_attitude: Optional[Attitude] = None
current_location: Optional[Location] = None
ttsengine = None
synthesizer = None
recognizer = None
root = None
button_held = False
radioButtonHeld = False
auxButtonOn = False
chatterTimer = None

recognizer_thread = None
recognizer_controller = None

class ChatSession:
	def __init__(self, system_prompt=ATC_INIT_INSTRUCTIONS, aiTools=None):
		# Start with a system prompt to set the assistant's behavior
		if USE_DEEPSEEK == True:
			self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
		else:
			self.client = OpenAI(api_key=OPENAI_API_KEY)
		self.messages = [{"role": "system", "content": system_prompt}]
				
		self.tools = aiTools
    
	def add_user_message(self, message):
		self.messages.append({"role": "user", "content": message})
    
	def add_assistant_message(self, message):
		self.messages.append({"role": "assistant", "content": message})
		
	def add_assistant_tool_call(self, tool_calls):
		self.messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
		
	def reset_session(self, system_prompt=ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN):
		self.messages = [{"role": "system", "content": system_prompt}]
		
    
	def get_response(self): #model="deepseek-chat"):
		if USE_DEEPSEEK == True:
			model=DEEPSEEK_MODEL
		else:
			model=OPENAI_MODEL
		response = self.client.chat.completions.create(
			model=model,
			messages=self.messages,
			tools=self.tools
		)
		#print(response)
		global parsedAIResponse
		finish_reason = response.choices[0].finish_reason
		#print("finish reason: ", finish_reason)
		
		if (finish_reason == "tool_calls"):
			assistant_message = response.choices[0].message.tool_calls
			self.add_assistant_tool_call(assistant_message)
			return handle_tool_calls(response)
		else:
			assistant_message = response.choices[0].message.content
			self.add_assistant_message(assistant_message)
		return assistant_message 

chatSession: Optional[ChatSession] = None	
trafficChatSession: Optional[ChatSession] = None

def handle_tool_calls(parsed_response):
	"""
	Handle tool/function calls from DeepSeek response
	"""
	if not parsed_response.choices:
		return None

	choice = parsed_response.choices[0]
	message = choice.message
	tool_calls = message.tool_calls

	if not tool_calls:
		return None

	tool_responses = []

	for tool_call in tool_calls:
		function_name = tool_call.function.name
		function_args = json.loads(tool_call.function.arguments)
		
		# Call the appropriate function
		result = call_function(function_name, function_args)
		
		tool_responses.append({
			'role': "tool",
			'tool_call_id': tool_call.id,
			'name': function_name,
			'content': result
		})

	print("tool responses: ", tool_responses[0])
	global chatSession
	chatSession.messages.append(tool_responses[0])
	print("all messages: ", chatSession.messages)
	return chatSession.get_response()
    

def call_function(name, args):
	"""Execute the requested function"""
	function_map = {
		'get_heading_to_approach_point': get_heading_to_approach_point
	}

	if name in function_map:
		return function_map[name](**args)
	else:
		return f"Function {name} not found"

# AI tool
def get_heading_to_approach_point(current_latitude, current_longitude):
	print("calculate_heading called")
	"""
	Calculate the initial bearing (heading) from current position to target position.

	Args:
		current_latitude (float): Current latitude in degrees
		current_lon (float): Current longitude in degrees
		target_lat (float): Target latitude in degrees
		target_lon (float): Target longitude in degrees

	Returns:
		float: Heading in degrees from North (0° to 360°)

	Example:
		>>> calculate_heading(37.7749, -122.4194, 34.0522, -118.2437)
		135.23  # Heading from San Francisco to Los Angeles
	"""
	if current_latitude is None or current_longitude is None:
		return "Unable to calculate heading."

	global aeroflySettings
	# Convert degrees to radians
	lat1 = math.radians(float(current_latitude))
	lon1 = math.radians(float(current_longitude))
	lat2 = math.radians(aeroflySettings.approach_start_latitude)
	lon2 = math.radians(aeroflySettings.approach_start_longitude)

	# Calculate the differences
	dlon = lon2 - lon1

	# Calculate the bearing using the formula
	y = math.sin(dlon) * math.cos(lat2)
	x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

	# Calculate the initial bearing in radians
	bearing_rad = math.atan2(y, x)

	# Convert to degrees and normalize to 0-360
	bearing_deg = math.degrees(bearing_rad)
	heading = (bearing_deg + 360) % 360

	distanceToDestination = getDistanceToLocation(aeroflySettings.approach_start_latitude, aeroflySettings.approach_start_longitude)

	return "Heading to destination: " + str(int(heading)) + " degrees, distance to destination: " + str(int(distanceToDestination)) + " nautical miles."


def getDistanceToLocation(destLatitude, destLongitude):
	# Calculate distance in nautical miles between two lat/lon points using Haversine formula
	if not gameTelemetry or not gameTelemetry.current_location or not gameTelemetry.current_location:
		return 0.0
		
	R = 6371.0  # Earth radius in kilometers
	lat1 = math.radians(gameTelemetry.current_location.latitude)
	lon1 = math.radians(gameTelemetry.current_location.longitude)
	lat2 = math.radians(destLatitude)
	lon2 = math.radians(destLongitude)
	dlon = lon2 - lon1
	dlat = lat2 - lat1
	a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	distance_km = R * c
	distance_nm = distance_km * 0.539957  # Convert km to nautical miles
	return distance_nm




# Load phrases from file
def load_phrases(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip()]
        
def cleanRecognizedSpeech(text):
	# Remove slashes
	cleaned = text.replace("/", "")
	
	return cleaned

def log_message(text_box, message):
    text_box.insert(tk.END, message + "\n")
    text_box.see(tk.END)


def getReachableFrequencies():
	# Create list of reachable frequencies considering the plane location, airport size and radio range

	# Get list of frequencies at origin and destination airports
	
	allFrequencies = []
	origFreqs = get_airport_frequencies(aeroflySettings.origin_name)
	origAirportType = get_airport_size(aeroflySettings.origin_name)
	origAirportSizeModifier = 1.0
	if origAirportType == "large_airport":
		origAirportSizeModifier = 1.0 
	elif origAirportType == "medium_airport":
		origAirportSizeModifier = 0.6 
	else:
		origAirportSizeModifier = 0.3 

	destFreqs = get_airport_frequencies(aeroflySettings.destination_name)
	destAirportType = get_airport_size(aeroflySettings.destination_name)
	destAirportSizeModifier = 1.0
	if destAirportType == "large_airport":
		destAirportSizeModifier = 1.0 
	elif destAirportType == "medium_airport":
		destAirportSizeModifier = 0.6
	else:
		destAirportSizeModifier = 0.3
	
	# Add reachable frequencies from origin
	distanceFromOrigin = getDistanceToLocation(aeroflySettings.origin_airport_latitude, aeroflySettings.origin_airport_longitude)
	for freq in origFreqs:
		freq["airport"] = get_airport_name(aeroflySettings.origin_name)
		freq["airportType"] = origAirportType
		freq["airportSizeModifier"] = origAirportSizeModifier
		freq["receivingRadio"] = radioTunedToFrequency(round(float(freq["frequency_mhz"]),2))
		if len(freq["receivingRadio"]) > 0:
			reach = RADIO_REACH.get(freq["description"], 0.0)
			if reach and reach >= distanceFromOrigin:
				allFrequencies.append(freq)
			elif RADIO_REACH["OTHER"] >= distanceFromOrigin:
				allFrequencies.append(freq)
	
	# Add reachable frequencies from destination
	distanceFromDestination = getDistanceToLocation(aeroflySettings.destination_airport_latitude, aeroflySettings.destination_airport_longitude)
	for freq in destFreqs:
		freq["airport"] = get_airport_name(aeroflySettings.destination_name)
		freq["airportType"] = destAirportType
		freq["airportSizeModifier"] = destAirportSizeModifier
		freq["receivingRadio"] = radioTunedToFrequency(round(float(freq["frequency_mhz"]),2))
		if len(freq["receivingRadio"]) > 0:
			reach = RADIO_REACH.get(freq["description"], 0.0)
			if reach and reach >= distanceFromDestination:
				allFrequencies.append(freq)
			elif RADIO_REACH["OTHER"] >= distanceFromDestination:
				allFrequencies.append(freq)
	
	
	guardFreq = {
        "airport": "",
		"description": "GUARD",
        "frequency_mhz": 121.50,
		"airportType": "large_airport",
        "airportSizeModifier": "0.01"
      }
	guardFreq["receivingRadio"] = canMessageBeHeard(round(float(guardFreq["frequency_mhz"]),2))
	if len(guardFreq["receivingRadio"]) > 0:
		allFrequencies.append(guardFreq)

	centerFreq = {
        "airport": "",
		"description": "CENTER",
        "frequency_mhz": 134.00,
		"airportType": "large_airport",
        "airportSizeModifier": "1.0"
      }
	centerFreq["receivingRadio"] = canMessageBeHeard(round(float(centerFreq["frequency_mhz"]),2))
	if len(centerFreq["receivingRadio"]) > 0:
		allFrequencies.append(centerFreq)
	
	return allFrequencies
	

def canMessageBeHeard(senderFrequency):
	# Check if we can hear this entity, is the correct frequency selected and audio routed?
	if not radioPanel:
		#print("Radio panel state unknown, allowing playing the message.")
		return "COM1"


	com1FrequencyMHz = round(radioPanel.COM1Frequency/1000000, 2)
	com2FrequencyMHz = round(radioPanel.COM2Frequency/1000000, 2)
	#print("senderFrequency: ", senderFrequency, " com1FrequencyMHz: ", com1FrequencyMHz, " com2FrequencyMHz: ", com2FrequencyMHz, " COM1AudioSelectButton: ", radioPanel.COM1AudioSelectButton, " COM2AudioSelectButton: ", radioPanel.COM2AudioSelectButton)
	if senderFrequency == com1FrequencyMHz and radioPanel.COM1AudioSelectButton: 
		print("can hear " + str(senderFrequency) +" on COM1")
		return "COM1"
	elif senderFrequency == com2FrequencyMHz and radioPanel.COM2AudioSelectButton:
		print("can hear " + str(senderFrequency) +" on COM2")
		return "COM2"
	elif (senderFrequency == 0):
		print("Sender frequency is unknown, playing the message anyway.")
		return "COM1"
	else:
		print("cannot hear " + str(senderFrequency))
		return ""

def radioTunedToFrequency(senderFrequency):
	# Return radio tuned to this frequency
	if not radioPanel:
		return "COM1"

	com1FrequencyMHz = round(radioPanel.COM1Frequency/1000000, 2)
	com2FrequencyMHz = round(radioPanel.COM2Frequency/1000000, 2)
	#print("senderFrequency: ", senderFrequency, " com1FrequencyMHz: ", com1FrequencyMHz, " com2FrequencyMHz: ", com2FrequencyMHz, " COM1AudioSelectButton: ", radioPanel.COM1AudioSelectButton, " COM2AudioSelectButton: ", radioPanel.COM2AudioSelectButton)
	if senderFrequency == com1FrequencyMHz: 
		print("Returning COM1 as tuned to " + str(senderFrequency))
		return "COM1"
	elif senderFrequency == com2FrequencyMHz:
		print("Returning COM2 as tuned to " + str(senderFrequency))
		return "COM2"
	elif (senderFrequency == 0):
		print("Sender frequency is unknown, returning COM1 as tuned radio.")
		return "COM1"
	else:
		print("Cannot hear " + str(senderFrequency))
		return ""


def canPilotBeHeard():
	# Can anyone hear the pilot on the transmitting frequency?
	global aeroflySettings

	transmittingFrequency = pilotTransmittingFrequency()

	if transmittingFrequency == 0.0:
		pygame.mixer.Sound('error.mp3').play()
		return False

	"""
	validFrequencies = []
	origFreqs = get_airport_frequencies(aeroflySettings.origin_name)
	originAirportFrequencies = [round(float(item["frequency_mhz"]),2) for item in origFreqs]
	destFreqs = get_airport_frequencies(aeroflySettings.destination_name)
	destinationAirportFrequencies = [round(float(item["frequency_mhz"]),2) for item in destFreqs]
	validFrequencies += originAirportFrequencies + destinationAirportFrequencies + [float(121.50)]
	"""
	reachableFrequencies = getReachableFrequencies()
	validFrequencies = [round(float(item["frequency_mhz"]),2) for item in reachableFrequencies]
	print("Reachable frequencies: ", reachableFrequencies)

	# Allow sending pilot's message if the freq is valid or in case we do not have radio panel info (-1.0)
	if transmittingFrequency in validFrequencies or transmittingFrequency == -1.0:
		return True
	else:		
		print("Pilot transmitting frequency ", transmittingFrequency, " is not among the listening/in range stations.")
		pygame.mixer.Sound('radio-static-1s.mp3').play()
		return False

def pilotTransmittingFrequency():
	global radioPanel
	global aeroflySettings

	if not radioPanel:
		print("Radio panel state unknown!")
		return -1.0

	# Get status of microphone switch
	mapping = radioPanel.MICROPHONE_OUTPUT[aeroflySettings.aircraft_model]
	micSwitchValue =  getattr(radioPanel,"MicrophoneSelect")

	# Match against options
	pilotTransmittingRadio = next(
		(name for name, value in mapping.items()
		 if value == micSwitchValue),
		None
	)

	pilotTransmittingFrequency = None
	if pilotTransmittingRadio == "COM1":
		pilotTransmittingFrequency = round(radioPanel.COM1Frequency/1000000, 2)
	elif pilotTransmittingRadio == "COM2":	
		pilotTransmittingFrequency = round(radioPanel.COM2Frequency/1000000, 2)
	else:
		print("Pilot is not transmitting on COM1 or COM2, no one can hear the pilot.")
		pilotTransmittingFrequency = 0

	print("Pilot transmitting on: ", pilotTransmittingRadio, " frequency: ", pilotTransmittingFrequency)

	return pilotTransmittingFrequency


def sendMessageToAI(cleanedtext):
	timestamp = datetime.now().strftime("%H:%M:%S")
	chatSession.add_user_message(timestamp + " " + cleanedtext)
	currentHeading = ""
	currentLocation = ""
	currentAltitude = 0.0
	currentGroundspeed = ""
	if gameTelemetry and gameTelemetry.current_attitude and gameTelemetry.current_location:
		currentHeading = "Heading " + str(int(gameTelemetry.current_attitude.true_heading))
		currentLocation = ", location Latitude: " + str(gameTelemetry.current_location.latitude) + ", location Longitude: " + str(gameTelemetry.current_location.longitude)
		currentGroundspeed = ", Groundspeed " + str(int(gameTelemetry.current_location.groundspeed_m_s * 1.94384)) + " kn" # convert m/s to knots
		currentAltitude = gameTelemetry.current_location.altitude_msl * FEET_IN_METER

	# Send squawk code if transponder is ON or squawk + altitude if on ALT
	transponderCode = "0000"
	transponderInfo = ", squawk: not sending"
	# Get status of transponde mode switch
	if radioPanel:
		mapping = radioPanel.TRANSPONDER_MODE[aeroflySettings.aircraft_model]
	
		# Match against options
		transponderMode = next(
			(name for name, value in mapping.items()
			 if value == radioPanel.TransponderMode),
			None
		)

		if transponderMode == "ON" or transponderMode == "ALT":
			transponderCode = str(int(radioPanel.TransponderCode))
			transponderInfo = ", squawk: " + transponderCode
		if  transponderMode == "ALT" and currentAltitude > 0:
			transponderInfo += ", altitude " + str(int(currentAltitude)) + " feet"

	transmittingFrequency = pilotTransmittingFrequency()
	telemetryMessage = "Airplane telemetry: "
	telemetryMessage += currentHeading + currentLocation + currentGroundspeed + transponderInfo
	
	if transmittingFrequency > 0:
		telemetryMessage += ", transmitting on " + str(transmittingFrequency) + "MHz"
	else:
		telemetryMessage += ", transmitting on the right frequency. "
	
	
	chatSession.add_user_message(timestamp + " " + telemetryMessage) # this sends telemetry together with voice
	
	
	response = chatSession.get_response()
	
	timestamp = datetime.now().strftime("%H:%M:%S")
	print(timestamp+" sendMessageToAI response from received speech: ", response)

	atcResponse = ATCResponse(response)

	senderFrequency = round(float(atcResponse.FREQUENCY),2) # in MHz, rounded to 2 decimals
	receivingRadio = canMessageBeHeard(senderFrequency)
	if (len(receivingRadio) > 0):	
		printATCInstructions(atcResponse.ATC_VOICE, atcResponse.COMMENTS, True)	
		#printATCInstructions(getATCInstructions(response), getAIComment(response), True)
		#say_response_distorted(response, receivingRadio)
		if len(atcResponse.ATC_VOICE) > 0:
			sayWithRadioEffect(atcResponse.ENTITY, atcResponse.ATC_VOICE, receivingRadio, True, "atc_to_user")
	else:
		print("Message ", atcResponse.ATC_VOICE, " cannot be heard because of radio configuration.")
		pygame.mixer.Sound('error.mp3').play()
		printATCInstructions("THIS CANNOT BE HEARD: " + atcResponse.ATC_VOICE, atcResponse.COMMENTS, True)

	global communicationWithAIInProgress
	communicationWithAIInProgress = False



def startATCSession():
	global chatSession
	global radioPanel
	global entityVoices
	global atcSessionStarted

	loadAeroflySettings() # reload Aerofly settings
	chatSession = ChatSession(ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN, ATC_AI_TOOLS)
	deleteRadioLogFiles()
	entityVoices = {}
	print("AI ATC SESSION START command")
	say("ATC session started")
	writeRadioLogToFile()
	radioPanel = None
	radioPanel = RadioPanel.RadioPanel(ENABLE_RADIO_PANEL, aeroflySettings.aircraft_model) # start reading radio panel
	print(radioPanel)
	if radioPanel:
		radioPanel.add_callback(onGameVariableChange)
		radioPanel.start_polling(GAME_VARIABLES_POLLING_INTERVAL)
	
	atcSessionStarted = True
	global chatterTimer
	if chatterTimer:
		chatterTimer.cancel()
	chatterTimer = threading.Timer(10, createRadioExchange).start() # Generate radio chatter

def resetATCSession():
	global chatSession
	global entityVoices
	loadAeroflySettings() # reload Aerofly settings
	#chatSession.reset_session()
	chatSession = ChatSession(ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN, ATC_AI_TOOLS)
	deleteRadioLogFiles()
	entityVoices = {}
	print("AI ATC SESSION RESET command")
	say("ATC session reset")
	writeRadioLogToFile()
	global chatterTimer
	if chatterTimer:
		chatterTimer.cancel()
	chatterTimer = threading.Timer(10, createRadioExchange).start() # Generate radio chatter

def stopATCSession():
	say("ATC session stopped.")
	global chatterTimer
	if chatterTimer:
		chatterTimer.cancel()
	
def recognized_handler(evt):
	trySendingMessage(evt.result.text)		
			
def trySendingMessage(message):
	timestamp = datetime.now().strftime("%H:%M:%S")
	cleanedtext = cleanRecognizedSpeech(message)
	print("\033[32m" + timestamp + " Recognized: " + cleanedtext + "\033[0m")
			
	global chatSession
	global entityVoices
				
	if cleanedtext.lower().startswith("reset session"):
		resetATCSession()
		return
	elif cleanedtext.lower().startswith("start session"):
		startATCSession()
		return
	elif cleanedtext.lower().startswith("stop session"):
		stopATCSession()
		return
			
	if len(cleanedtext) < 7:
		print("recognized speech too short, not sending")
		return
			
	
	if not atcSessionStarted:
		startATCSession()
		time.sleep(0.5) # give it a moment to start properly

	if not canPilotBeHeard():
		return

	global communicationWithAIInProgress
	communicationWithAIInProgress = True
	#print(timestamp + " sending speech to AI")
	ai_thread = threading.Thread(target=sendMessageToAI, args=(cleanedtext,), daemon=True)
	ai_thread.start()
			

def create_speech_recognizer():
	#print("enter create_speech_recognizer")
	done = threading.Event()
	speech_config = speechsdk.SpeechConfig(subscription=MSSPEECH_API_KEY, region=MSSPEECH_API_REGION)
	speech_config.speech_recognition_language = "en-US"
	recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
	#print("enter create_speech_recognizer 2")
	speech_config.set_property(speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs,"4000")  # default is 500
	
	#self.speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_StablePartialResultThreshold, "100") # this should improve recognition speed
	
	# Add word list for better recognition - MUST be less than 1kB for free Azure tier
	phrase_list_grammar = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
	for phrase in load_phrases("aviation_phrases.txt"):
		phrase_list_grammar.addPhrase(phrase)

	# Events
	#recognizer.recognizing.connect(lambda evt: text_box.after(0, lambda: log_message(text_box, f"[Partial] {evt.result.text}")))
	recognizer.recognized.connect(recognized_handler)
	recognizer.session_started.connect(lambda evt: print("[Recognizer session started]"))
	recognizer.session_stopped.connect(lambda evt: done.set())
	recognizer.canceled.connect(lambda evt: (print(evt.cancellation_details), done.set()))

	return recognizer, done



def safe_log(self, text):
        # Ensure logs from background thread are passed to main thread
        #self.root.after(0, lambda: self.log(text))
		print(text)

	
def get_entity_voice(entityName):
	# If the entity already has a voice assigned, return it
	if entityName in entityVoices:
		return entityVoices[entityName]

	# Find the first available voice that hasn't been assigned yet
	used_voices = set(entityVoices.values())
	available_voices = [voice for voice in VOICES if voice not in used_voices]

	# Assign a new or random voice
	if available_voices:
		chosen_voice = random.choice(available_voices)
	else:
		chosen_voice = random.choice(VOICES)

	# Store and return the chosen voice
	entityVoices[entityName] = chosen_voice
	#print("Chosen voice for " + entityName + ": " + chosen_voice)
	return chosen_voice
	
			

class ATCResponse:
	ATC_VOICE: str = ""
	COMMENTS: str = ""
	ENTITY: str = ""
	FREQUENCY: float = 0.0
	READBACK_TIMEOUT: int = 0
	
	def __init__(self, aiResponse):
		data = None
		try:
			if aiResponse.startswith("```json"):
				aiResponse = aiResponse[len("```json"):]
			if aiResponse.endswith("```"):
				aiResponse = aiResponse[:-3]
			data = json.loads(aiResponse)
						
		except json.JSONDecodeError:
			print("Received non-JSON data:", aiResponse)
			return None
		
		self.ATC_VOICE=data.get("ATC_VOICE", "")
		self.COMMENTS=data.get("COMMENTS", "")
		self.ENTITY=data.get("ENTITY", "")
		self.FREQUENCY=data.get("FREQUENCY", 0)
		self.READBACK_TIMEOUT=data.get("READBACK_TIMEOUT", 0)

class AITrafficGenerationResponse:
	message1Entity: str = ""
	message1Text: str = ""
	message2Entity: str = ""
	message2Text: str = ""
	
	def __init__(self, aiResponse):
		data = None
		try:
			if aiResponse.startswith("```json"):
				aiResponse = aiResponse[len("```json"):]
			if aiResponse.endswith("```"):
				aiResponse = aiResponse[:-3]
			data = json.loads(aiResponse)
						
		except json.JSONDecodeError:
			print("Received non-JSON data:", aiResponse)
			return None
		
		self.message1Entity=data.get("MESSAGE1_ENTITY", "")
		self.message1Text=data.get("MESSAGE1_TEXT", "")
		self.message2Entity=data.get("MESSAGE2_ENTITY", "")
		self.message2Text=data.get("MESSAGE2_TEXT", "")

def printATCInstructions(instructions, aiComment, withTimestamp):
	
	
	if withTimestamp:
		timestamp = datetime.now().strftime("%H:%M:%S")
	else:
		timestamp = ""
		
	print("\033[91m" + timestamp + " " + instructions + "\033[0m")

	global atc_text_box
	atc_text_box.delete("1.0", tk.END)
	atc_text_box.insert(tk.END, instructions + "\n")
	atc_text_box.see("end")
	
	# write messages to log files
	writeRadioLogToFile()
   


def say(text):
	speech_config.speech_synthesis_voice_name = 'en-US-GuyNeural'
	synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
	result = synthesizer.speak_text_async(text).get()


"""
def say_response_distorted(response, receivingRadio):
	#global ttsengine
	#global synthesizer
	global speech_config
	
	try:
		if response.startswith("```json"):
			response = response[len("```json"):]
		if response.endswith("```"):
			response = response[:-3]
		data = json.loads(response)
	except json.JSONDecodeError:
		print("Received non-JSON data:", response)
		return
                
	atc_speech = data["ATC_VOICE"]
	entityName = data["ENTITY"]
	if atc_speech is None or len(atc_speech) == 0:
		return

	sayWithRadioEffect(entityName, atc_speech, receivingRadio)
"""

def sayWithRadioEffect(entityName, message, receivingRadio, blocking, filePrefix):
	# set voice for entity
	voice = get_entity_voice(entityName)
	print("Assigned voice " + voice + " to entity " + entityName)
	speech_config.speech_synthesis_voice_name = voice
	
	soundID = random.randint(10000, 99999)
	
	cleanRecordingFileName = os.path.join("Temp", filePrefix + "_clean_tts_" + str(soundID) + ".wav")
	audio_config = speechsdk.audio.AudioOutputConfig(filename=cleanRecordingFileName)
	synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config,audio_config=audio_config)
	result = synthesizer.speak_text_async(message).get()
	
	try:
		if (result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted):
			print(result)
			print("speech result.reason: ", result.reason, " cancellation_details: ", result.cancellation_details)
	except e:
		print("exception: ", e)
	
	
	radioEffectRecordingFileName = file_path = os.path.join("Temp", filePrefix + "_radio_tts_" + str(soundID) + ".wav")
	audio = addRadioEffectToRecording(cleanRecordingFileName, radioEffectRecordingFileName)
	
	global atcSoundCOM1
	global atcSoundCOM2
	COM1VolumeOutput = 0.7
	COM2VolumeOutput = 0.7
	if radioPanel:
		COM1VolumeOutput = radioPanel.COM1VolumeOutput
		COM2VolumeOutput = radioPanel.COM2VolumeOutput

	if receivingRadio == "COM1":
		if atcSoundCOM1 is not None:
			atcSoundCOM1.stop()
		atcSoundCOM1 = pygame.mixer.Sound(radioEffectRecordingFileName)
		atcSoundCOM1.set_volume(COM1VolumeOutput)
		channel = atcSoundCOM1.play()
	elif receivingRadio == "COM2":
		if atcSoundCOM2 is not None:
			atcSoundCOM2.stop()
		atcSoundCOM2 = pygame.mixer.Sound(radioEffectRecordingFileName)
		atcSoundCOM2.set_volume(COM2VolumeOutput)
		channel = atcSoundCOM2.play()
	else:
		print("Unknown receiving radio, not playing atc sound: ", receivingRadio)
		return

	if blocking:
		while channel.get_busy():
			time.sleep(0.1) 

def addRadioEffectToRecording(fileName, newFileName):
	# Load the clean TTS
	audio = AudioSegment.from_wav(fileName)

	# --- Radio Effect ---
	# Convert to mono, 8kHz
	audio = audio.set_channels(1).set_frame_rate(8000)

	# Bandpass filter (300–3400 Hz)
	audio = audio.low_pass_filter(3400)
	audio = audio.high_pass_filter(300)

	# Add compression (normalize)
	audio = effects.compress_dynamic_range(audio)

	# Add light static noise
	#noise = AudioSegment.white_noise(duration=len(audio)).apply_gain(-35)  # subtle

	noise = WhiteNoise().to_audio_segment(duration=len(audio)).apply_gain(-50)
	audio = audio.overlay(noise)

	# Optional squelch click at start/end
	#click = AudioSegment.white_noise(duration=30).apply_gain(-10)
	click = WhiteNoise().to_audio_segment(duration=30).apply_gain(-30)
	audio = click + audio + click

	# Save processed audio
	audio.export(newFileName, format="wav")

	return audio

""" not used at the moment, automatically send telemetry updates to atc
def send_telemetry_update():
	global current_attitude
	global current_location
	#global client
	global chatSession
	
	if communicationWithAIInProgress == True:
		print("telemetry paused, not sending")
		threading.Timer(TELEMETRY_SEND_INTERVAL, send_telemetry_update).start()
		return

	if current_location is None or current_attitude is None:
		# Reschedule the next execution (recursive)
		print("Full telemetry missing")
		threading.Timer(TELEMETRY_SEND_INTERVAL, send_telemetry_update).start()
		return

	timestamp = time.strftime('%H:%M:%S')
	print(f"Sending telemetry update at {timestamp}")  

	#todo - send same telemetry as when sending speech to ai
	telemetry = current_attitude.timestamp.strftime("%H:%M:%S") + " " + str(current_attitude) + " " + str(current_location)
	print(telemetry)


	chatSession.add_user_message(telemetry)
	response = chatSession.get_response()
	print("response for telemetry sent at " + timestamp + ": ", response)
	atcResponse = parseATCResponse(response)
	printATCInstructions(atcResponse.ATC_VOICE, atcResponse.COMMENTS, True)	
	#printATCInstructions(getATCInstructions(response), getAIComment(response), True)
	say_response(response)


	# Reschedule the next execution (recursive)
	threading.Timer(TELEMETRY_SEND_INTERVAL, send_telemetry_update).start()
"""





def controllerInputListen():
	# Initialize OpenVR
	try:
		openvr.init(openvr.VRApplication_Background )
	except Exception as e:
		print("Error while initializing OpenVR")
		print(e)
		return

	vr_system = openvr.VRSystem()
	global radioButtonHeld
	
	# Mask for button
	button_mask = 1 << VR_CONTROLLER_BUTTON_ID

	try:
		while True:
			# Get the device class to make sure it’s a controller
			device_class = vr_system.getTrackedDeviceClass(VR_CONTROLLER_INDEX)
			
			was_pressed = radioButtonHeld
			
			global recognizer

			if device_class == openvr.TrackedDeviceClass_Controller:
				result, state = vr_system.getControllerState(VR_CONTROLLER_INDEX)
				curr_pressed = state.ulButtonPressed

				# Check if button 1 is pressed now
				is_pressed_now = curr_pressed & button_mask
				
				if is_pressed_now:
					radioButtonHeld = True
				else:
					radioButtonHeld = False
					
				if was_pressed and not radioButtonHeld:
					#print("radio button not held any more, stopping speech recognition")
					pygame.mixer.Sound('radio-off.mp3').play()
					recognizer.stop_continuous_recognition()
					
				elif not was_pressed and radioButtonHeld:
					print("radio button is held")
					pygame.mixer.Sound('radio-on.mp3').play()
					recognizer.start_continuous_recognition()
					 

			time.sleep(0.1)

	finally:
		openvr.shutdown()


def runSpeechRecognizer():
		global recognizer, recognizer_controller
		print("starting recognizer thread")
		recognizer, done = create_speech_recognizer()
		recognizer_controller = (recognizer, done)
		#recognizer.start_continuous_recognition()
		done.wait()

controllerMonitorThread = None
parsed_data = None

class AeroflySettings:
	
	def __init__(
		self,
		destination_runway_longitude: float = 0.0,
		destination_runway_latitude: float = 0.0,
		destination_runway_altitude_msl: float = 0.0,
		approach_start_longitude: float = 0.0,
		approach_start_latitude: float = 0.0,
		wind_strength: float = 0.0,
		wind_direction_in_degree: int = 0,
		origin_name: str = "",
		departure_runway: str = "",
		destination_name: str = "",
		destination_runway: str = "",
		aircraft_model: str = "",
		cruise_altitude: float = 0.0,
		visibility: float = 0.0,
		destination_airport_atis_frequency: float = 0.0,
		origin_airport_atis_frequency: float = 0.0,
		origin_airport_latitude: float = 0.0,
		origin_airport_longitude: float = 0.0,
		destination_airport_latitude: float = 0.0,
		destination_airport_longitude: float = 0.0
	):
		
		self.destination_runway_longitude = destination_runway_longitude
		self.destination_runway_latitude = destination_runway_latitude
		self.destination_runway_altitude_msl = destination_runway_altitude_msl
		self.approach_start_longitude = approach_start_longitude
		self.approach_start_latitude = approach_start_latitude
		self.wind_strength = wind_strength
		self.wind_direction_in_degree = wind_direction_in_degree
		self.origin_name = origin_name
		self.departure_runway = departure_runway
		self.destination_name = destination_name
		self.destination_runway = destination_runway
		self.aircraft_model = aircraft_model
		self.cruise_altitude = cruise_altitude
		self.visibility = visibility
		self.destination_airport_atis_frequency = destination_airport_atis_frequency
		self.origin_airport_atis_frequency = origin_airport_atis_frequency
		self.origin_airport_latitude = origin_airport_latitude
		self.origin_airport_longitude = origin_airport_longitude
		self.destination_airport_latitude = destination_airport_latitude
		self.destination_airport_longitude = destination_airport_longitude
		
	

aeroflySettings = None
airports = None

def loadAeroflySettings():
	global aeroflySettings
	global mcf_path
	aeroflySettings = AeroflySettings()
	
	# Create the parser factory
	parser = mcfparser.MainMcfFactory()
	
	try:
		# Read the main.mcf file
		with open(mcf_path, 'r', encoding='utf-8') as file:
			mcf_content = file.read()
		
		# Parse the content
		parsed_data = parser.create(mcf_content)
		
		aeroflySettings.wind_strength = parsed_data.wind['strength'] * WIND_SPEED_100_PERCENT_IN_KNOTS
		aeroflySettings.wind_direction_in_degree = parsed_data.wind['direction_in_degree']
		aeroflySettings.aircraft_model = parsed_data.aircraft['name']
		aeroflySettings.cruise_altitude = parsed_data.navigation['Route']['CruiseAltitude'] * FEET_IN_METER
		aeroflySettings.visibility = parsed_data.visibility
		
		# Access the parsed data
		#print(f"Aircraft: {parsed_data.aircraft['name']}")
		#print(f"Position: {parsed_data.flight_setting['position']}")
		#print(f"Visibility: {parsed_data.visibility}")
		#print(f"Wind Strength: {parsed_data.wind['strength']}")
		#print(f"Wind direction_in_degree: {parsed_data.wind['direction_in_degree']}")
		
		# Access waypoints
		#print(f"\nNumber of waypoints: {len(parsed_data.navigation['Route']['Ways'])}")
		for i, waypoint in enumerate(parsed_data.navigation['Route']['Ways']):
			#print(f"Waypoint {i+1}: {waypoint.Identifier} at {waypoint.Position}. Type:{waypoint.type}. Direction:{waypoint.Direction}")
			if (waypoint.type == mcfparser.MissionCheckpointType.DESTINATION_RUNWAY):
				# Get location of the destination runway and approach start point
				lat_deg, lon_deg, alt_m = mcfparser.ecef_to_lla(waypoint.Position[0], waypoint.Position[1], waypoint.Position[2])
				aeroflySettings.destination_runway_longitude = lon_deg
				aeroflySettings.destination_runway_latitude = lat_deg
				aeroflySettings.destination_runway = waypoint.Identifier
				approach_distance_km = 7
				approach_lat_deg, approach_lon_deg, approach_alt_m = mcfparser.offset_position((waypoint.Position[0], waypoint.Position[1], waypoint.Position[2]), (waypoint.Direction[0], waypoint.Direction[1], waypoint.Direction[2]), approach_distance_km)["lla"]
				aeroflySettings.approach_start_longitude = approach_lon_deg
				aeroflySettings.approach_start_latitude = approach_lat_deg
				
			elif (waypoint.type == mcfparser.MissionCheckpointType.DESTINATION):
				aeroflySettings.destination_name = waypoint.Identifier
				aeroflySettings.destination_runway_altitude_msl = waypoint.Elevation * FEET_IN_METER
				lat_deg, lon_deg, alt_m = mcfparser.ecef_to_lla(waypoint.Position[0], waypoint.Position[1], waypoint.Position[2])
				aeroflySettings.destination_airport_latitude = lat_deg
				aeroflySettings.destination_airport_longitude = lon_deg
			elif (waypoint.type == mcfparser.MissionCheckpointType.ORIGIN):
				aeroflySettings.origin_name = waypoint.Identifier
				lat_deg, lon_deg, alt_m = mcfparser.ecef_to_lla(waypoint.Position[0], waypoint.Position[1], waypoint.Position[2])
				aeroflySettings.origin_airport_latitude = lat_deg
				aeroflySettings.origin_airport_longitude = lon_deg
			elif (waypoint.type == mcfparser.MissionCheckpointType.DEPARTURE_RUNWAY):
				aeroflySettings.departure_runway = waypoint.Identifier
		
		#print("Aerofly settings loaded: ", aeroflySettings.__dict__)

		originAirportName = get_airport_name(aeroflySettings.origin_name)
		destinationAirportName = get_airport_name(aeroflySettings.destination_name)
		origFreqs = get_airport_frequencies(aeroflySettings.origin_name)
		aeroflySettings.origin_airport_atis_frequency = getATISFrequency(origFreqs)
		originAirportFrequencies = ", ".join(f"{f['description']}:{f['frequency_mhz']}" for f in origFreqs)
		destFreqs = get_airport_frequencies(aeroflySettings.destination_name)
		aeroflySettings.destination_airport_atis_frequency = getATISFrequency(destFreqs)
		destinationAirportFrequencies = ", ".join(f"{f['description']}:{f['frequency_mhz']}" for f in destFreqs)
		
		# add flight plan to AI ATC instructions
		global ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN
		ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN = (ATC_INIT_INSTRUCTIONS + 
			" Wind direction in degrees is " + str(aeroflySettings.wind_direction_in_degree) +
			". Wind strength in knots is " + str(aeroflySettings.wind_strength) +
			". My aircraft model is " + aeroflySettings.aircraft_model +
			". My flight plan is: cruise altitude " + str(int(aeroflySettings.cruise_altitude)) + " feet. " + 
			". Origin airport: " + aeroflySettings.origin_name + " (" + originAirportName + ", frequencies:" + originAirportFrequencies + ")" +
			". Departure runway: "  + aeroflySettings.departure_runway + 
			". Destination airport: " + aeroflySettings.destination_name + " (" + destinationAirportName + ", frequencies:" + destinationAirportFrequencies + ")" +
			". Destination runway latitude: "  + str(aeroflySettings.destination_runway_latitude) +
			". Destination runway longitude: "  + str(aeroflySettings.destination_runway_longitude) +
			". Destination runway: "  + aeroflySettings.destination_runway +
			". Destination elevation: " + str(int(aeroflySettings.destination_runway_altitude_msl)) + " feet " +
			". Approach start waypoint latitude: " + str(aeroflySettings.approach_start_latitude) + 
			". Approach start waypoint longitude: " + str(aeroflySettings.approach_start_longitude) + 
			". When I ask for vector for runway, calculate it using my current position towards the approach start waypoint.")
			
		
		generateATISRecording(aeroflySettings.origin_name, originAirportName, None, aeroflySettings.departure_runway, aeroflySettings.wind_strength, aeroflySettings.wind_direction_in_degree, aeroflySettings.visibility)
		generateATISRecording(aeroflySettings.destination_name, destinationAirportName, None, aeroflySettings.destination_runway, aeroflySettings.wind_strength, aeroflySettings.wind_direction_in_degree, aeroflySettings.visibility)

	except FileNotFoundError:
		print("Error: main.mcf file not found")
	except Exception as e:
		print(f"Error parsing file: {e}")

def getATISFrequency(frequencies):
    """Searches a list of frequency dicts and returns the ATIS frequency."""
    for freq_item in frequencies:
        if freq_item.get("description") == "ATIS":
            return freq_item.get("frequency_mhz")
    return None  # Return None if ATIS is not found

def generateATISRecording(airportCode, airportName, time, runway, wind_strength, wind_direction_in_degree, visibility):
	
	visibilityDescription = None
	if visibility >= 0.7:
		visibilityDescription = "ten miles or more"
	elif visibility >= 0.6:
		visibilityDescription = "eight miles"
	elif visibility >= 0.5:
		visibilityDescription = "six miles"
	elif visibility >= 0.3:
		visibilityDescription = "three miles"
	elif visibility >= 0.2:
		visibilityDescription = "two miles"
	elif visibility >= 0.1:
		visibilityDescription = "less than one mile"
	else:
		visibilityDescription = "less than one quarter mile"

	informationVersion = random.choice(PHONETIC_ALPHABET)
	
	message = airportName + " Information " + informationVersion + ", time 0900 Zulu. Runway in use " + runway + ". Wind " + str(int(wind_direction_in_degree)) + " degrees at " + str(int(wind_strength)) + " knots. Visibility " + visibilityDescription + ". No significant weather. Temperature one eight, dewpoint one zero. QNH one zero one three. On first radio contact, advise you have Information " + informationVersion + "."
	
	atisTempFilename = os.path.join("Temp", airportCode + "_atis_temp.wav")
	atisFilename = os.path.join("Temp", airportCode + "_atis.wav")
	global speech_config
	audio_config = speechsdk.audio.AudioOutputConfig(filename=atisTempFilename)
	speech_config.speech_synthesis_voice_name = 'en-US-ChristopherNeural'
	synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config,audio_config=audio_config)
	
	
	ssml_string = f"""
    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
        
		<voice name='en-US-ChristopherNeural' style="calm">
            <prosody rate='{"+10%"}'>
                {message}
            </prosody>
        </voice>
    </speak>
    """

	result = synthesizer.speak_ssml_async(ssml_string).get()

	if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
		print("Speech synthesized successfully.")
	elif result.reason == speechsdk.ResultReason.Canceled:
		cancellation_details = result.cancellation_details
		print(f"Speech synthesis canceled: {cancellation_details.reason}")
		if cancellation_details.reason == speechsdk.CancellationReason.Error:
			print(f"Error details: {cancellation_details.error_details}")

	audio = addRadioEffectToRecording(atisTempFilename, atisFilename)


def onGameVariableChange(name, old, new):
	global atcSoundCOM1
	global atcSoundCOM2
	
	if (name in {"SenderTransponderIdent",}):
		return

	if name == "AUXAudioSelectButton" and float(old) != -1.0:   # to avoid triggering on initial value
		global auxButtonOn
		global recognizer
		was_pressed = auxButtonOn
		is_pressed_now = new
		if is_pressed_now:
			auxButtonOn = True
		else:
			auxButtonOn = False
					
		if was_pressed and not auxButtonOn:
			print("radio button not held any more, stopping speech recognition")
			pygame.mixer.Sound('radio-off.mp3').play()
			recognizer.stop_continuous_recognition()
					
		elif not was_pressed and auxButtonOn:
			print("radio button is held")
			pygame.mixer.Sound('radio-on.mp3').play()
			recognizer.start_continuous_recognition()

	
	# todo set initial volume
	if name == "COM1VolumeOutput":
		if atcSoundCOM1 is not None:
			atcSoundCOM1.set_volume(new)
	elif name == "COM2VolumeOutput":
		if atcSoundCOM2 is not None:
			atcSoundCOM2.set_volume(new)


	

	# TODO react on transponder code change

	# React if we tune to ATIS freq
	global atisPlaying
	global atisPlayingOnRadio
	if not atisPlaying:
		if (name == "COM1Frequency" or name == "COM1AudioSelectButton") and radioPanel.COM1AudioSelectButton:
			if aeroflySettings.origin_airport_atis_frequency and round(radioPanel.COM1Frequency/1000000, 2) == round(aeroflySettings.origin_airport_atis_frequency,2):
				startPlayingATIS(aeroflySettings.origin_name, "COM1")
			elif aeroflySettings.destination_airport_atis_frequency and round(radioPanel.COM1Frequency/1000000, 2) == round(aeroflySettings.destination_airport_atis_frequency,2):
				startPlayingATIS(aeroflySettings.destination_name, "COM1")
		elif (name == "COM2Frequency" or name == "COM2AudioSelectButton") and radioPanel.COM2AudioSelectButton:
			if aeroflySettings.origin_airport_atis_frequency and round(radioPanel.COM2Frequency/1000000, 2) == round(aeroflySettings.origin_airport_atis_frequency,2):
				startPlayingATIS(aeroflySettings.origin_name, "COM2")
			elif aeroflySettings.destination_airport_atis_frequency and round(radioPanel.COM2Frequency/1000000, 2) == round(aeroflySettings.destination_airport_atis_frequency,2):
				startPlayingATIS(aeroflySettings.destination_name, "COM2")
	elif atisPlaying and atisPlayingOnRadio == "COM1":
		if (name == "COM1AudioSelectButton" and not radioPanel.COM1AudioSelectButton) or name == "COM1Frequency":
			stopPlayingATIS()
	elif atisPlaying and atisPlayingOnRadio == "COM2":			
		if (name == "COM2AudioSelectButton" and not radioPanel.COM2AudioSelectButton) or name == "COM2Frequency":
			stopPlayingATIS()


	if name == "COM1AudioSelectButton" and new == 0.0 and atcSoundCOM1 is not None:
			atcSoundCOM1.stop()
			atcSoundCOM1 = None

	if name == "COM2AudioSelectButton" and new == 0.0 and atcSoundCOM2 is not None:
			atcSoundCOM2.stop()
			atcSoundCOM2 = None

	print(f"{name} changed: {old} to {new}")



def startPlayingATIS(airportCode, atisPlayingOn):
	stopPlayingATIS()
	atisFilename = os.path.join("Temp", airportCode + "_atis.wav")
	global atisPlaying
	global atisPlayingOnRadio 
	global atisThread
	global atcChannelCOM1
	global atcChannelCOM2
	global atcSoundCOM1
	global atcSoundCOM2

	atisPlayingOnRadio = atisPlayingOn
	

	COM1VolumeOutput = 0.7
	COM2VolumeOutput = 0.7
	if radioPanel:
		COM1VolumeOutput = radioPanel.COM1VolumeOutput
		COM2VolumeOutput = radioPanel.COM2VolumeOutput
	
	if atisPlayingOnRadio == "COM1":
		if atcSoundCOM1 is not None:
			atcSoundCOM1.stop()
		atcSoundCOM1 = pygame.mixer.Sound(atisFilename)
		atcSoundCOM1.set_volume(COM1VolumeOutput)
		atisPlaying = True
		atcChannelCOM1 = atcSoundCOM1.play(loops=-1)
	elif atisPlayingOnRadio == "COM2":
		if atcSoundCOM2 is not None:
			atcSoundCOM2.stop()
		atcSoundCOM2 = pygame.mixer.Sound(atisFilename)
		atcSoundCOM2.set_volume(COM2VolumeOutput)
		atisPlaying = True
		atcChannelCOM2 = atcSoundCOM2.play(loops=-1)
	else:
		print("Unknown receiving radio, not playing ATIS sound: ", atisPlayingOnRadio)
	
	

def stopPlayingATIS():
	print("Stopping ATIS playback.")
	global atisPlaying
	global atisThread
	global atisPlayingOnRadio
	global atcChannelCOM1
	global atcChannelCOM2

	
	
	if atisPlayingOnRadio == "COM1":
		if atcChannelCOM1 is not None:
			atcChannelCOM1.stop()
	elif atisPlayingOnRadio == "COM2":
		if atcChannelCOM2 is not None:
			atcChannelCOM2.stop()
	else:
		print("Unknown receiving radio, not stopping ATIS sound: ", atisPlayingOnRadio)

	atisPlaying = False
	atisPlayingOnRadio = ""
		


def setAeroflyVolume(volume=0.4):
	if MAC_PLATFORM:
		return
	
	sessions = AudioUtilities.GetAllSessions()
	for session in sessions:
		try:
			if session.Process and session.Process.name() == "aerofly_fs_4.exe":
				session.SimpleAudioVolume.SetMasterVolume(volume, None)
				print("Aerofly volume set to: ", volume)
				session.SimpleAudioVolume.SetMute(0, None)  # unmute
				break
		except Exception as e:
			print(e)
			continue

def safe_shutdown():
	if not MAC_PLATFORM:
		print("Shutting down OpenVR")
		openvr.shutdown()

# Get airport name by ICAO code
def get_airport_name(icao_code):
	icao_code = icao_code.upper()
	for airport in airports:
		if airport.get("icao").upper() == icao_code:
			return airport.get("name")
	return ''  # If not found

def get_airport_size(icao_code):
	icao_code = icao_code.upper()
	for airport in airports:
		if airport.get("icao").upper() == icao_code:
			return airport.get("type")
	return ''  # If not found

def get_airport_country(icao_code):
	icao_code = icao_code.upper()
	for airport in airports:
		if airport.get("icao").upper() == icao_code:
			return airport.get("iso_country")
	return ''  # If not found

def get_airport_frequencies(icao_code):
    icao_code = icao_code.upper()
    for airport in airports:
        if airport.get("icao", "").upper() == icao_code:
            return airport.get("freq", [])  # Return the list of frequency dicts
    return []  # If airport not found, return empty list



# Write to PDF file
def write_lines_with_paragraph(pdf_path, lines, firstLineInBold, withFlightPlan):
	# Define margins in millimeters
	left_margin = 10 * mm    # 10mm
	right_margin = 10 * mm   # 10mm  
	top_margin = 10 * mm     # 10mm
	bottom_margin = 10 * mm  # 10mm
    
	doc = SimpleDocTemplate(
		pdf_path, 
		pagesize=A4,
		leftMargin=left_margin,
		rightMargin=right_margin,
		topMargin=top_margin,
		bottomMargin=bottom_margin
	)

	courier_style = ParagraphStyle(
		name="CourierStyle",
		fontName="Courier",
		fontSize=12,
		leading=15,  
	)

	flight_plan_style = ParagraphStyle(
		name="CourierStyle",
		fontName="Courier",
		fontSize=15,
		leading=15,
		spaceBefore=0,    
		spaceAfter=0,
		textColor=colors.black,
	)

	courier_bold_style = ParagraphStyle(
		name="CourierBold",
		fontName="Courier-Bold",
		fontSize=15,
		leading=15, 
	)

	story = []
	cnt = 1
	for line in lines:
		if (withFlightPlan and cnt <= 2): # first 2 lines of flight plan, with tight line spacing
			story.append(Paragraph(line, flight_plan_style))
		elif (firstLineInBold and cnt == 4): #first line after flight plan = latest ATC message
			story.append(Paragraph(line, courier_bold_style))
			story.append(Paragraph("", courier_style))
			story.append(Paragraph("-" * 20, courier_style))
			story.append(Paragraph("", courier_style))
		else:
			story.append(Paragraph(line, courier_style))
		story.append(Spacer(1, 12))
		cnt = cnt + 1
	doc.build(story)

# Write entire message and debug history to PDF files
def writeRadioLogToFile():
	global aeroflySettings
	
	radioLines = []
	debugLines = []

	deleteRadioLogFiles()

	# add flight plan at the top of the radio log
	origFreqs = get_airport_frequencies(aeroflySettings.origin_name)
	originAirportFrequencies = ", ".join(f"{f['description']}:{f['frequency_mhz']}" for f in origFreqs)
	destFreqs = get_airport_frequencies(aeroflySettings.destination_name)
	destinationAirportFrequencies = ", ".join(f"{f['description']}:{f['frequency_mhz']}" for f in destFreqs)
	radioLines.append("From: " + aeroflySettings.origin_name + aeroflySettings.departure_runway + " ["+ originAirportFrequencies + "]")
	radioLines.append("To:   " + aeroflySettings.destination_name + aeroflySettings.destination_runway + ", alt:" + str(int(aeroflySettings.destination_runway_altitude_msl)) + "ft ["+ destinationAirportFrequencies + "]")
	radioLines.append("-" * 72)

	global chatSession
	for message in reversed(chatSession.messages):
		role = message["role"]
		if (role == "user"):
			# Write to debug log
			line = "PILOT: \n" + message["content"]
			debugLines.append(line)
		elif (role == "assistant" and message['content']):
			# Write to both radio and debug log
			atcResponse = ATCResponse(message['content'])
			line = atcResponse.ENTITY.upper() + ": \n" + atcResponse.ATC_VOICE
			debugLines.append(line)
			radioLines.append(line)

			# Write to debug log
			line = "ATC COMMENTS: \n" + atcResponse.COMMENTS
			debugLines.append(line)
		elif (role == "tool" and message['content']):
			# Write to debug log
			line = "TOOL CALL: \nname:" + message['name'] + ", response:" + message['content']
			debugLines.append(line)
			
	write_lines_with_paragraph("RadioLogDebug.pdf", debugLines, False, False)
	write_lines_with_paragraph("RadioLog.pdf", radioLines, True, True)

# Create radio chatter between other pilots and ATC
def createRadioExchange():
	global chatterTimer
	if RADIO_CHATTER_PROBABILITY == 0.0:
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return
	
	clearTempFolder("chatter")
	
	# Only if no user communication with AI ongoing or ATIS playback
	if communicationWithAIInProgress or atisPlaying:
		print("Communication with AI ongoing, not creating radio exchange")
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return
	
	reachableFrequencies = getReachableFrequencies()
	reachableFrequencies = [s for s in reachableFrequencies if s.get("description") != "ATIS"] # Remove ATIS frequencies
	randomStation = None
	if len(reachableFrequencies) > 0:
		randomStation = random.choice(reachableFrequencies)
	if not randomStation:
		print("No reachable frequencies found, not creating radio exchange")
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start() # do this again in XX seconds
		return

	# Decide with random chance whether to generate an exchange or not
	# Take airport size into account, bigger airports = more likely
	print("random station: ", randomStation)
	airportSizeModifier = float(randomStation["airportSizeModifier"])
	randomNum = float(random.randint(0, 100))
	if RADIO_CHATTER_PROBABILITY * airportSizeModifier <= randomNum:
		print("Skipping radio exchange generation due to probability setting (rnd=" + str(randomNum) + ", airportSizeModifier=" + str(airportSizeModifier) + ", RADIO_CHATTER_PROBABILITY * airportSizeModifier=" + str(RADIO_CHATTER_PROBABILITY * airportSizeModifier))
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return

	# Check if the radio is active on audio panel
	if randomStation["receivingRadio"] == "COM1" and not radioPanel.COM1AudioSelectButton:
		print("Skipping radio exchange generation, COM1 not active on audio panel")
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return
	elif randomStation["receivingRadio"] == "COM2" and not radioPanel.COM2AudioSelectButton:
		print("Skipping radio exchange generation, COM2 not active on audio panel")
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return

	prompt = "Create a single exchange between a pilot and ATC (airport: " + randomStation["airport"] + ", airport size: " + randomStation["airportType"] + ", ATC service/frequency description: " + randomStation["description"] + "). "
	
	if gameTelemetry and gameTelemetry.current_location:
		prompt += "If speaking as Center, it should be center ATC close to the current location: latitude: " + str(gameTelemetry.current_location.latitude) + ", longitude: " + str(gameTelemetry.current_location.longitude) + "."
	else:
		prompt += "If speaking as Center, do not mention current location, as it is unknown."

	# Init AI session
	global trafficChatSession
	if not trafficChatSession:
		trafficChatSession = ChatSession(RADIO_CHATTER_GENERATION_PROMPT, aiTools=None)

	trafficChatSession.add_user_message(prompt)
	response = trafficChatSession.get_response()

	# Check again if user is communicating
	if communicationWithAIInProgress or atisPlaying:
		print("Communication with AI ongoing, discarding radio exchange")
		chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
		return

	aiTrafficGenerationResponse = AITrafficGenerationResponse(response)

	if aiTrafficGenerationResponse and aiTrafficGenerationResponse.message1Entity and aiTrafficGenerationResponse.message1Text and aiTrafficGenerationResponse.message2Entity and aiTrafficGenerationResponse.message2Text:
		# Speak the first message
		sayWithRadioEffect(aiTrafficGenerationResponse.message1Entity, aiTrafficGenerationResponse.message1Text, randomStation["receivingRadio"], True, "chatter")

		# Speak the second message after a delay. 
		time.sleep(3)

		# Check again if user is communicating
		if communicationWithAIInProgress or atisPlaying:
			print("Communication with AI ongoing, discarding second message of radio exchange")
			chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
			return

		# Check again if the radio is active on audio panel
		if randomStation["receivingRadio"] == "COM1" and not radioPanel.COM1AudioSelectButton:
			print("Skipping second chatter message, COM1 not active on audio panel")
			chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
			return
		elif randomStation["receivingRadio"] == "COM2" and not radioPanel.COM2AudioSelectButton:
			print("Skipping second chatter message, COM2 not active on audio panel")
			chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start()
			return

		sayWithRadioEffect(aiTrafficGenerationResponse.message2Entity, aiTrafficGenerationResponse.message2Text, randomStation["receivingRadio"], True, "chatter")
	
	chatterTimer = threading.Timer(RADIO_CHATTER_TIMER, createRadioExchange).start() # do this again in XX seconds


def deleteRadioLogFiles():
	file_path = "RadioLog.pdf"
	if os.path.exists(file_path):
		os.remove(file_path)
		#print(f"{file_path} deleted.")
		
	file_path = "RadioLogDebug.pdf"
	if os.path.exists(file_path):
		os.remove(file_path)
		#print(f"{file_path} deleted.")

def clearTempFolder(fileNamePrefix=""):
    temp_dir = os.path.join(os.getcwd(), "Temp")  # "Temp" inside current folder
    pattern = os.path.join(temp_dir, fileNamePrefix + "*.*")     

    for file_path in glob.glob(pattern):
        try:
            os.remove(file_path)
            #print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Could not delete {file_path}: {e}")


def on_test_transmit_press(event):
	global button_held
	button_held = True
	print("test transmit button pressed")
	
	pygame.mixer.Sound('radio-on.mp3').play()
	
	recognizer.start_continuous_recognition()
	global communicationWithAIInProgress
	communicationWithAIInProgress = True


def on_test_transmit_release(event):
	global button_held
	button_held = False
	print("test transmit button released")
	pygame.mixer.Sound('radio-off.mp3').play()

	recognizer.stop_continuous_recognition()



entry = None
def createAppWindow():
	global root
	global atc_text_box
	
	# Open app window
	root = tk.Tk()
	root.title("ATC")
	

	root.geometry("800x300")
	root.rowconfigure(0, weight=0)
	root.rowconfigure(1, weight=0)
	
	pttButton = ttk.Button(root, text='Push to Talk')
	if MAC_PLATFORM:
		pttButton.place(x=10,y=10)	
	else:
		pttButton.place(x=10,y=10, width=100, height=100)	
	pttButton.bind("<ButtonPress-1>", on_test_transmit_press)
	pttButton.bind("<ButtonRelease-1>", on_test_transmit_release)

	global entry
	entry = tk.Entry(root)
	entry.place(x=250,y=10, width=440, height=30)	
	entry.insert(0, "ATC, radio check.")
	entry.focus()
	transmitTextBtn = tk.Button(root, text="Send text", command=onTransmitTextBtnSubmit)
	if MAC_PLATFORM:
		transmitTextBtn.place(x=700,y=10)
	else:
		transmitTextBtn.place(x=700,y=10, width=60, height=30)
	
	tbutton = tk.Button(root, text="Test", command=testButton)
	#tbutton.place(x=10,y=100)	

	atc_font = tkfont.Font(family="Courier New", size=18)
	atc_text_box = tk.Text(root, height=6, width=55, font=atc_font, fg='#000000', bg='#ffffff', bd=0, highlightthickness=0, wrap="word")
	atc_text_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=120)
	#atc_text_box.insert(tk.END, "Baron 58, Basel Tower, runway 28, wind calm, cleared for takeoff. Right turn after departure, heading three-six-zero.")
	atc_text_box.config(insertontime=0)
	



def testButton():
	createRadioExchange()
	

def onTransmitTextBtnSubmit():
	global entry
	value = entry.get()
	print("Entry value:", value)
	trySendingMessage(value)


def main():
	global root
	global synthesizer
	global speech_config
	
	if MAC_PLATFORM:
		print("Mac platform detected, some features may not work (radio panel, volume controls).")

	clearTempFolder()

	# Load environment variables with API keys
	load_dotenv()
	global DEEPSEEK_API_KEY, MSSPEECH_API_KEY, MSSPEECH_API_REGION, OPENAI_API_KEY
	DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") 
	MSSPEECH_API_KEY=os.environ.get("MSSPEECH_API_KEY") 
	MSSPEECH_API_REGION=os.environ.get("MSSPEECH_API_REGION")
	OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
	
	# Create app window
	createAppWindow()

	# Init sound player
	pygame.mixer.init()
	
	# Load list of all airports
	global airports
	with open("all_airports.json", "r", encoding="utf-8") as f:
		airports = json.load(f)

	# Init Azure TTS
	speech_config = speechsdk.SpeechConfig(subscription=MSSPEECH_API_KEY, region=MSSPEECH_API_REGION)
	speech_config.speech_synthesis_voice_name = "en-US-GuyNeural"

	# Load Aerofly settings from main.mcf file
	loadAeroflySettings()

	# Register callback for OpenVR shutdown
	if not MAC_PLATFORM:
		atexit.register(safe_shutdown)

	# If Windows keep removing this app from audio sessions, try to keep it alive. Not sure if it is needed.
	#keep_audio_session_alive()
	#keep_audio_session_alive_sounddevice()
	
	# Modify volume of Aerofly app, to better align it with volume of this app
	setAeroflyVolume()

	# Start monitoring VR controller input
	if not MAC_PLATFORM:
		global controllerMonitorThread
		controllerMonitorThread = threading.Thread(target=controllerInputListen, daemon=True)
		controllerMonitorThread.start()
	
	# Start speech recognizer thread	
	global recognizer_thread
	recognizer_thread = threading.Thread(target=runSpeechRecognizer, daemon=True)
	recognizer_thread.start()
	
	'''
	# Test available voices
	for voice in VOICES:
		print("Assigned voice " + voice)
		speech_config.speech_synthesis_voice_name = voice
		synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
		result = synthesizer.speak_text_async("testing").get()
		print("speech result: ", result)
	'''

	# Init AI session with initial instructions
	#global chatSession
	#chatSession = ChatSession(ATC_INIT_INSTRUCTIONS_WITH_FLIGHT_PLAN, ATC_AI_TOOLS)
	
	# Start receiving UDP telemetry
	global gameTelemetry
	gameTelemetry = Telemetry()
	
	# Delete old radio log files
	#deleteRadioLogFiles()
	
	root.mainloop()
	

if __name__ == "__main__":
	try:
		main()
	except Exception as e:
		print("The program crashed with an error:")
		print(e)
		#global openvr
		if not MAC_PLATFORM:
			openvr.shutdown()
		input("Press Enter to close the window...")
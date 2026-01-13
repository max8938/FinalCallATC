FinalCallATC AI ATC for Aerofly makes your flights feel alive with realistic air traffic control. It tunes into the actual airport frequencies from your flight plan and lets you talk to ATC by voice, with natural replies from a variety of AI voices. Push-to-talk works through your VR controller, the audio panel, or a simple button in the app.

You’ll only hear ATC if your radios are set up correctly, and they’ll only hear you if your mic is on the right channel — just like in real life. It even takes radio range into account, with Guard and Center always available, and throws in random chatter from other planes to keep the skies busy.

The app also ties into the Cessna 172 and Baron 58 panels (more planes will be added), so you can actually use the radios, audio selectors, and transponder. ATC picks up your squawk code, altitude, and live telemetry with every call, and can even give you headings and distances to help line up on final approach.

All your comms are saved in a radio log, along with a handy flight plan summary and ATIS reports, so you can review or even display them in-cockpit with third-party tools.

This is still a work in progress, the code is far from stellar, but it works :)

**Functionalities:**
- AI ATC (all services), working on actual airport frequencies (origin and destination airports from the active navigation plan).
- Communicating with ATC using voice and hearing their replies.
- Push to talk either by holding top button of the left VR controller (e.g. triangle on PSVR2 controller. OpenVR needed), or using Push-to-talk button in airplane (if visible), or activating AUX switch/button on audio panel or holding PTT button in app's window.
- AI can calculate heading and distance to the start of the final approach for the destination runway.
- Working audio panel, radios & transponder controls on Cessna 172, Baron 58, Robin DR400, King Air and Q400. For other planes, radio panel cannot be controlled at the moment.
- Individual radio volume controls.
- You can hear ATC only if tuned to the correct frequency and radio is active on the audio panel.
- ATC can hear you only if you are tuned correctly and the correct mic output is selected.
- Random chatter between ATC and other airplanes (configurable how often messages are heard) on origin, destination, Center (134.00) and Guard (121.50).
- Station distance taken into account, you cannot connect to the ones too far away (Guard and Center are always reachable).
- Transponder code (and optionally the altitude) sent to ATC, depending on the selected transponder mode.
- Plane telemetry sent to ATC with each message (location, heading, ground speed).
- 10+ different voices.
- Radio log & more detailed logs saved as PDF files, can be displayed in cockpit using 3rd-party tools.
- Flight plan summary displayed on top of radio log (origin, destination, runways, altitudes, radio frequencies).
- ATIS generated looping messages for origin and destination (if ATIS is available there).
- Airport diagrams for origin and destination are generated in AirportDiagrams subfolder, to be optionally displayed in cockpit.

**Requirements:**
- Windows for full functionalities. Most work on Mac as well, except radio panel controls; ATC can be controlled via its app window.
- Python (v3.13 works fine for me) + all needed libraries installed
- Openrouter, Deep Seek or OpenAI AI API access (Gemini 3 Flash Preview model via Openrouter seems the best so far)
- Azure voice services API access
- (optional) OpenVR for PTT control via VR controller
- (optional) OpenKneeboard (or similar overlay app) for displaying radio log files in flatscreen and VR

AI and Azure API access is not hard to set up. Costs: max couple of dozen cents per hour (if it is talking all the time).

**TODO:**
- Add support for more planes
- Add more voices and regional accents
- Periodically send telemetry to AI so ATC can contact the plane if needed
- Ability to tune to stations other than origin and destination airports
- Morse code sound for tuned VOR
- Settings UI
- Better error handling
- Optimize AI prompts to reduce costs (although it is already quite cheap)
- Any other ideas? Let me know!

**Bugs & limitations:**
- AI is not aware of terrain clearances, you need to choose the altitude correctly in the flight plan.
- AI does not know about airport layouts and taxiways.
- VR controller button binding for PTT is hardcoded, but it can be changed in the top of ai_atc.py file.

**Setup:**
- Store your API keys in ".env" file in the folder with ai_atc.py (see: ".env.example"). You need Azure key & region plus either Deep Seek or OpenAI keys, not both. Depending on which ones you have, set USE_DEEPSEEK variable appropriately at the top of ai_atc.py.
	- Deep Seek platform: https://platform.deepseek.com/sign_in
	- OpenAI platform: https://auth.openai.com/log-in
	- Azure: https://azure.microsoft.com/en-us/get-started/azure-portal. You need to create a Speech Services instance and get its API key.
- Install Python, pip3 and its needed libraries:
	- Windows: pip3 install pygame python-dotenv pycaw pydub reportlab openvr azure-cognitiveservices-speech openai psutil audioop-lts AppKit
	- Mac: pip3 install pygame python-dotenv pycaw pydub reportlab azure-cognitiveservices-speech openai psutil audioop-lts AppKit
- Enable "Broadcast flight info to IP address" in Aerofly Settings/Miscellaneous and set "Broadcast IP address" to .255 IP address in the same range as your computer. E.g. if your computer's IP address is 192.168.1.33, set Broadcase IP address to 192.168.1.255. Set "Broadcast IP port" to 49002.
- Copy files and folders from "customizations" folder to Aerofly FS4 user folder (C:\Users\%USERNAME%\Documents\Aerofly FS 4)
- 
**Running:**
- (optional for VR) start SteamVR
- If you want to use a non-supported plane, set ENABLE_RADIO_PANEL = False near the top of ai_atc.py file.
- Start ATC app ("python3 ai_atc.py" in terminal)
- Start Aerofly
- Make a flight/navigation plan. In case you are deleting the old plan, always manually re-select your origin as well (even though the game seems to do it)
- Start the flight
- Say "start session" to ATC. This will: attach ATC app to Aerofly to read radio panel state, start receiving telemetry, delete old radio log file and update it with the new flight plan. It will also reduce Aerofly volume in Windows sound mixer, to better hear the radio.
- The list of valid frequencies will be in your flight plan on top of Radio Log document. (also available: guard at 121.50 and center at 134.00)
- If you change the flight plan (want to start a new flight), say "reset session", it will reload everything.
- If you speak on freq with no listening stations, you will hear radio static. If you speak to a station but do not enable that radio in the audio panel, they will hear you but you will hear just 2 warning tones.

Wishlist for IPACS to make this better:
- Add following sender nodes to aircraft TMD files: radio volumes, active frequencies, audio panel controls, transponder code/mode/ident button press, navigation plan, plane model, weather info (wind, visibility, clouds). Also would be nice: nearby airports.
- Send traffic with UDP telemetry (XTRAFFIC object)

Thanks to Aerofly Missionsgerät for main.mcf parsing logic and aeroflyToSayintentions (need to see how to integrate with them) for list of airports and frequencies.

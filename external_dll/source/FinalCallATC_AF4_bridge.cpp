///////////////////////////////////////////////////////////////////////////////////////////////////
//
// file aerofly_fs_4_external_dll_sample.cpp
//
// PLEASE NOTE:  THE INTERFACE IN THIS FILE AND ALL DATA TYPES COULD BE SUBJECT TO SUBSTANTIAL
//               CHANGES WHILE AEROFLY FS 4 IS STILL RECEIVING UPDATES
//
// FURTHER NOTE: This sample just shows you how to read and send messages from the simulation
//               Some sample code is provided so see how to read and send messages
//
// 2024-12-19 - th/mb
//
// ---------------------------------------------------------------------------
//
// copyright (C) 2005-2024, Dr. Torsten Hans, Dr. Marc Borchers
// All rights reserved.
//
// Redistribution  and  use  in  source  and  binary  forms,  with  or  without
// modification, are permitted provided that the following conditions are met:
//
//  - Redistributions of  source code must  retain the above  copyright notice,
//    this list of conditions and the disclaimer below.
//  - Redistributions in binary form must reproduce the above copyright notice,
//    this  list of  conditions  and  the  disclaimer (as noted below)  in  the
//    documentation and/or other materials provided with the distribution.
//  - Neither the name of the copyright holder nor the names of its contributors
//    may be used to endorse or promote products derived from this software
//    without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT  HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR  IMPLIED WARRANTIES, INCLUDING,  BUT NOT  LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND  FITNESS FOR A PARTICULAR  PURPOSE
// ARE  DISCLAIMED.
//
///////////////////////////////////////////////////////////////////////////////////////////////////

#if defined(WIN32) || defined(WIN64)
  #if defined(_MSC_VER)
    #pragma warning ( disable : 4530 )  // C++ exception handler used, but unwind semantics are not enabled
    #pragma warning ( disable : 4577 )  // 'noexcept' used with no exception handling mode specified; termination on exception is not guaranteed. Specify /EHsc
  #endif
#endif

#include "tm_external_message.h"

#include <windows.h>
#include <thread>
#include <vector>
#include <mutex>
#include <cmath>
#include <unordered_map>
#include <string>
#include <cstring>
#include <sstream>
#include <iomanip>

static HINSTANCE global_hDLLinstance = NULL;



static HANDLE hMapFile = NULL;
static void* pSharedMemory = NULL;
static const size_t SHARED_MEMORY_SIZE = 65536; // 64KB for JSON data



//////////////////////////////////////////////////////////////////////////////////////////////////
//
// some ugly macros. we use this to be able to translate from string hash id to string
//
//////////////////////////////////////////////////////////////////////////////////////////////////
#define TM_MESSAGE( a1, a2, a3, a4, a5, a6, a7 )       static tm_external_message Message##a1( ##a2, a3, a4, a5, a6 );
#define TM_MESSAGE_NAME( a1, a2, a3, a4, a5, a6, a7 )  a2,




//////////////////////////////////////////////////////////////////////////////////////////////////
//
// list of messages that can be send/received
// to ease the interpretation of the messages, type, access flags and units are specified
//
//////////////////////////////////////////////////////////////////////////////////////////////////
#define MESSAGE_LIST(F) \
F( AircraftUniversalTime,                 "Aircraft.UniversalTime",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "universal time of day (UTC)                                                                                  " ) \
F( AircraftAltitude,                      "Aircraft.Altitude",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "altitude as measured by altimeter                                                                            " ) \
F( AircraftVerticalSpeed,                 "Aircraft.VerticalSpeed",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "vertical speed                                                                                               " ) \
F( AircraftPitch,                         "Aircraft.Pitch",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "pitch angle                                                                                                  " ) \
F( AircraftBank,                          "Aircraft.Bank",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "bank angle                                                                                                   " ) \
F( AircraftIndicatedAirspeed,             "Aircraft.IndicatedAirspeed",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "indicated airspeed                                                                                           " ) \
F( AircraftIndicatedAirspeedTrend,        "Aircraft.IndicatedAirspeedTrend",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "indicated airspeed trend                                                                                     " ) \
F( AircraftGroundSpeed,                   "Aircraft.GroundSpeed",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "ground speed                                                                                                 " ) \
F( AircraftMagneticHeading,               "Aircraft.MagneticHeading",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( AircraftTrueHeading,                   "Aircraft.TrueHeading",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( AircraftLatitude,                      "Aircraft.Latitude",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( AircraftLongitude,                     "Aircraft.Longitude",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( AircraftHeight,                        "Aircraft.Height",                          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( AircraftPosition,                      "Aircraft.Position",                        tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( AircraftOrientation,                   "Aircraft.Orientation",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftVelocity,                      "Aircraft.Velocity",                        tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "velocity vector         in body system if 'Body' flag is set, in global system otherwise                     " ) \
F( AircraftAngularVelocity,               "Aircraft.AngularVelocity",                 tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::RadiantPerSecond,         "angular velocity        in body system if 'Body' flag is set (roll rate pitch rate yaw rate) in global system" ) \
F( AircraftAcceleration,                  "Aircraft.Acceleration",                    tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecondSquared,    "aircraft acceleration   in body system if 'Body' flag is set, in global system otherwise                     " ) \
F( AircraftGravity,                       "Aircraft.Gravity",                         tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecondSquared,    "gravity acceleration    in body system if 'Body' flag is set                                                 " ) \
F( AircraftWind,                          "Aircraft.Wind",                            tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "wind vector at current aircraft position                                                                     " ) \
F( AircraftRateOfTurn,                    "Aircraft.RateOfTurn",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::RadiantPerSecond,         "rate of turn                                                                                                 " ) \
F( AircraftMachNumber,                    "Aircraft.MachNumber",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "mach number                                                                                                  " ) \
F( AircraftAngleOfAttack,                 "Aircraft.AngleOfAttack",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "angle of attack indicator                                                                                    " ) \
F( AircraftAngleOfAttackLimit,            "Aircraft.AngleOfAttackLimit",              tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "angle of attack limit (stall)                                                                                " ) \
F( AircraftAccelerationLimit,             "Aircraft.AccelerationLimit",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecondSquared,    "acceleration limit (g-load max/min)                                                                          " ) \
F( AircraftGear,                          "Aircraft.Gear",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "current gear position, zero is up, one is down, in between in transit                                        " ) \
F( AircraftFlaps,                         "Aircraft.Flaps",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "selected flaps                                                                                               " ) \
F( AircraftSlats,                         "Aircraft.Slats",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "selected slats                                                                                               " ) \
F( AircraftThrottle,                      "Aircraft.Throttle",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "current throttle setting                                                                                     " ) \
F( AircraftAirBrake,                      "Aircraft.AirBrake",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftGroundSpoilersArmed,           "Aircraft.GroundSpoilersArmed",             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto ground spoiler armed                                                                                    " ) \
F( AircraftGroundSpoilersExtended,        "Aircraft.GroundSpoilersExtended",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto ground spoiler extended                                                                                 " ) \
F( AircraftParkingBrake,                  "Aircraft.ParkingBrake",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "parking brake                                                                                                " ) \
F( AircraftAutoBrakeSetting,              "Aircraft.AutoBrakeSetting",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto brake position                                                                                          " ) \
F( AircraftAutoBrakeEngaged,              "Aircraft.AutoBrakeEngaged",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto brake engaged                                                                                           " ) \
F( AircraftAutoBrakeRejectedTakeOff,      "Aircraft.AutoBrakeRejectedTakeOff",        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto brake RTO armed                                                                                         " ) \
F( AircraftRadarAltitude,                 "Aircraft.RadarAltitude",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "radar altitude above ground                                                                                  " ) \
F( AircraftName,                          "Aircraft.Name",                            tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "current aircraft short name ( name of folder in aircraft directory, eg c172 )                                " ) \
F( AircraftNearestAirportIdentifier,      "Aircraft.NearestAirportIdentifier",        tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftNearestAirportName,            "Aircraft.NearestAirportName",              tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftNearestAirportLocation,        "Aircraft.NearestAirportLocation",          tm_msg_data_type::Vector2d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftNearestAirportElevation,       "Aircraft.NearestAirportElevation",         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestAirportIdentifier,         "Aircraft.BestAirportIdentifier",           tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestAirportName,               "Aircraft.BestAirportName",                 tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestAirportLocation,           "Aircraft.BestAirportLocation",             tm_msg_data_type::Vector2d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestAirportElevation,          "Aircraft.BestAirportElevation",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestRunwayIdentifier,          "Aircraft.BestRunwayIdentifier",            tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestRunwayElevation,           "Aircraft.BestRunwayElevation",             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestRunwayThreshold,           "Aircraft.BestRunwayThreshold",             tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftBestRunwayEnd,                 "Aircraft.BestRunwayEnd",                   tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftCategoryJet,                   "Aircraft.Category.Jet",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftCategoryGlider,                "Aircraft.Category.Glider",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftOnGround,                      "Aircraft.OnGround",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "set if aircraft is on ground                                                                                 " ) \
F( AircraftOnRunway,                      "Aircraft.OnRunway",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "set if aircraft is on ground and on a runway                                                                 " ) \
F( AircraftCrashed,                       "Aircraft.Crashed",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftPower,                         "Aircraft.Power",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftNormalizedPower,               "Aircraft.NormalizedPower",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftNormalizedPowerTarget,         "Aircraft.NormalizedPowerTarget",           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftTrim,                          "Aircraft.Trim",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftPitchTrim,                     "Aircraft.PitchTrim",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftPitchTrimScaling,              "Aircraft.PitchTrimScaling",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftPitchTrimOffset,               "Aircraft.PitchTrimOffset",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftRudderTrim,                    "Aircraft.RudderTrim",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftAutoPitchTrim,                 "Aircraft.AutoPitchTrim",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "automatic pitch trim active (FBW)                                                                            " ) \
F( AircraftYawDamperEnabled,              "Aircraft.YawDamperEnabled",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "automatic rudder damping active (yaw damper)                                                                 " ) \
F( AircraftRudderPedalsDisconnected,      "Aircraft.RudderPedalsDisconnected",        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "steering disconnect button active                                                                            " ) \
F( AircraftStarter,                       "Aircraft.Starter",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "generic engine starter                                                                                       " ) \
F( AircraftStarter1,                      "Aircraft.Starter1",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 1 starter                                                                                             " ) \
F( AircraftStarter2,                      "Aircraft.Starter2",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 2 starter                                                                                             " ) \
F( AircraftStarter3,                      "Aircraft.Starter3",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 3 starter                                                                                             " ) \
F( AircraftStarter4,                      "Aircraft.Starter4",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 4 starter                                                                                             " ) \
F( AircraftIgnition,                      "Aircraft.Ignition",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "generic engine ignition                                                                                      " ) \
F( AircraftIgnition1,                     "Aircraft.Ignition1",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 1 ignition                                                                                            " ) \
F( AircraftIgnition2,                     "Aircraft.Ignition2",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 2 ignition                                                                                            " ) \
F( AircraftIgnition3,                     "Aircraft.Ignition3",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 3 ignition                                                                                            " ) \
F( AircraftIgnition4,                     "Aircraft.Ignition4",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 4 ignition                                                                                            " ) \
F( AircraftThrottleLimit,                 "Aircraft.ThrottleLimit",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine throttle limit (max throttle for takeoff)                                                             " ) \
F( AircraftReverse,                       "Aircraft.Reverse",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine reverse thrust selected                                                                               " ) \
F( AircraftEngineMaster1,                 "Aircraft.EngineMaster1",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 1 master switch                                                                                       " ) \
F( AircraftEngineMaster2,                 "Aircraft.EngineMaster2",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 2 master switch                                                                                       " ) \
F( AircraftEngineMaster3,                 "Aircraft.EngineMaster3",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 3 master switch                                                                                       " ) \
F( AircraftEngineMaster4,                 "Aircraft.EngineMaster4",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 4 master switch                                                                                       " ) \
F( AircraftEngineThrottle1,               "Aircraft.EngineThrottle1",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 1 throttle position                                                                                   " ) \
F( AircraftEngineThrottle2,               "Aircraft.EngineThrottle2",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 2 throttle position                                                                                   " ) \
F( AircraftEngineThrottle3,               "Aircraft.EngineThrottle3",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 3 throttle position                                                                                   " ) \
F( AircraftEngineThrottle4,               "Aircraft.EngineThrottle4",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine 4 throttle position                                                                                   " ) \
F( AircraftEngineRotationSpeed1,          "Aircraft.EngineRotationSpeed1",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRotationSpeed2,          "Aircraft.EngineRotationSpeed2",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRotationSpeed3,          "Aircraft.EngineRotationSpeed3",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRotationSpeed4,          "Aircraft.EngineRotationSpeed4",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRunning1,                "Aircraft.EngineRunning1",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRunning2,                "Aircraft.EngineRunning2",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRunning3,                "Aircraft.EngineRunning3",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftEngineRunning4,                "Aircraft.EngineRunning4",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( AircraftAPUAvailable,                  "Aircraft.APUAvailable",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( PerformanceSpeedVS0,                   "Performance.Speed.VS0",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "minimum speed with flaps down, lower end of white arc                                                        " ) \
F( PerformanceSpeedVS1,                   "Performance.Speed.VS1",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "minimum speed with flaps retracted, lower end of green arc                                                   " ) \
F( PerformanceSpeedVFE,                   "Performance.Speed.VFE",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "maximum speed with flaps extended, upper end of white arc                                                    " ) \
F( PerformanceSpeedVNO,                   "Performance.Speed.VNO",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "maneuvering speed, lower end of yellow arc                                                                   " ) \
F( PerformanceSpeedVNE,                   "Performance.Speed.VNE",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "never exceed speed, red line                                                                                 " ) \
F( PerformanceSpeedVAPP,                  "Performance.Speed.VAPP",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "approach airspeed                                                                                            " ) \
F( PerformanceSpeedMinimum,               "Performance.Speed.Minimum",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "stall speed in current configuration                                                                         " ) \
F( PerformanceSpeedMaximum,               "Performance.Speed.Maximum",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "maximum speed in current configuration                                                                       " ) \
F( PerformanceSpeedMinimumFlapRetraction, "Performance.Speed.MinimumFlapRetraction",  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "minimum speed for next flap up                                                                               " ) \
F( PerformanceSpeedMaximumFlapExtension,  "Performance.Speed.MaximumFlapExtension",   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "maximum speed for next flap down                                                                             " ) \
F( ConfigurationSelectedTakeOffFlaps,     "Configuration.SelectedTakeOffFlaps",       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "FMS selected takeoff flaps                                                                                   " ) \
F( ConfigurationSelectedLandingFlaps,     "Configuration.SelectedLandingFlaps",       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "FMS selected landing flaps                                                                                   " ) \
F( FMSFlightNumber,                       "FlightManagementSystem.FlightNumber",      tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "FMS flight number                                                                                            " ) \
F( NavigationSelectedCourse1,             "Navigation.SelectedCourse1",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Radiant,                  "NAV1 selected course (OBS1)                                                                                  " ) \
F( NavigationSelectedCourse2,             "Navigation.SelectedCourse2",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Radiant,                  "NAV2 selected course (OBS2)                                                                                  " ) \
F( NavigationNAV1Identifier,              "Navigation.NAV1Identifier",                tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "NAV1 station identifier                                                                                      " ) \
F( NavigationNAV1Frequency,               "Navigation.NAV1Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "NAV1 receiver active frequency                                                                               " ) \
F( NavigationNAV1StandbyFrequency,        "Navigation.NAV1StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "NAV1 receiver standby frequency                                                                              " ) \
F( NavigationNAV1FrequencySwap,           "Navigation.NAV1FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "NAV1 frequency swap                                                                                          " ) \
F( NavigationNAV2Identifier,              "Navigation.NAV2Identifier",                tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "NAV2 station identifier                                                                                      " ) \
F( NavigationNAV2Frequency,               "Navigation.NAV2Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "NAV2 receiver active frequency                                                                               " ) \
F( NavigationNAV2StandbyFrequency,        "Navigation.NAV2StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "NAV2 receiver standby frequency                                                                              " ) \
F( NavigationNAV2FrequencySwap,           "Navigation.NAV2FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "NAV2 frequency swap                                                                                          " ) \
F( NavigationDME1Frequency,               "Navigation.DME1Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME1 active frequency                                                                                        " ) \
F( NavigationDME1Distance,                "Navigation.DME1Distance",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME1 distance                                                                                                " ) \
F( NavigationDME1Time,                    "Navigation.DME1Time",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME1 time                                                                                                    " ) \
F( NavigationDME1Speed,                   "Navigation.DME1Speed",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME1 speed                                                                                                   " ) \
F( NavigationDME2Frequency,               "Navigation.DME2Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME2 active frequency                                                                                        " ) \
F( NavigationDME2Distance,                "Navigation.DME2Distance",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME2 distance                                                                                                " ) \
F( NavigationDME2Time,                    "Navigation.DME2Time",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME2 time                                                                                                    " ) \
F( NavigationDME2Speed,                   "Navigation.DME2Speed",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "DME2 speed                                                                                                   " ) \
F( NavigationILS1Identifier,              "Navigation.ILS1Identifier",                tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "ILS1 station identifier                                                                                      " ) \
F( NavigationILS1Course,                  "Navigation.ILS1Course",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Radiant,                  "ILS1 selected course                                                                                         " ) \
F( NavigationILS1Frequency,               "Navigation.ILS1Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ILS1 receiver active frequency                                                                               " ) \
F( NavigationILS1StandbyFrequency,        "Navigation.ILS1StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ILS1 receiver standby frequency                                                                              " ) \
F( NavigationILS1FrequencySwap,           "Navigation.ILS1FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "ILS1 frequency swap                                                                                          " ) \
F( NavigationILS2Identifier,              "Navigation.ILS2Identifier",                tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "ILS2 station identifier                                                                                      " ) \
F( NavigationILS2Course,                  "Navigation.ILS2Course",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Radiant,                  "ILS2 selected course                                                                                         " ) \
F( NavigationILS2Frequency,               "Navigation.ILS2Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ILS2 receiver active frequency                                                                               " ) \
F( NavigationILS2StandbyFrequency,        "Navigation.ILS2StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ILS2 receiver standby frequency                                                                              " ) \
F( NavigationILS2FrequencySwap,           "Navigation.ILS2FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "ILS2 frequency swap                                                                                          " ) \
F( NavigationADF1Frequency,               "Navigation.ADF1Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ADF1 receiver active frequency                                                                               " ) \
F( NavigationADF1StandbyFrequency,        "Navigation.ADF1StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ADF1 receiver standby frequency                                                                              " ) \
F( NavigationADF1FrequencySwap,           "Navigation.ADF1FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "ADF1 frequency swap                                                                                          " ) \
F( NavigationADF2Frequency,               "Navigation.ADF2Frequency",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ADF2 receiver active frequency                                                                               " ) \
F( NavigationADF2StandbyFrequency,        "Navigation.ADF2StandbyFrequency",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "ADF2 receiver standby frequency                                                                              " ) \
F( NavigationADF2FrequencySwap,           "Navigation.ADF2FrequencySwap",             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "ADF2 frequency swap                                                                                          " ) \
F( NavigationCOM1Frequency,               "Communication.COM1Frequency",              tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM1 transceiver active frequency                                                                            " ) \
F( NavigationCOM1Volume,                  "Communication.COM1Volume",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "COM1 transceiver volume                                                                            " ) \
F( NavigationCOM1AudioSelect,             "Communication.COM1AudioSelect",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "COM1 transceiver volume                                                                            " ) \
F( NavigationCOM1StandbyFrequency,        "Communication.COM1StandbyFrequency",       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM1 transceiver standby frequency                                                                           " ) \
F( NavigationCOM1FrequencySwap,           "Communication.COM1FrequencySwap",          tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "COM1 frequency swap                                                                                          " ) \
F( NavigationCOM2Frequency,               "Communication.COM2Frequency",              tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM2 transceiver active frequency                                                                            " ) \
F( NavigationCOM2Volume,                  "Communication.COM2Volume",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "COM1 transceiver volume                                                                            " ) \
F( NavigationCOM2AudioSelect,             "Communication.COM2AudioSelect",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "COM1 transceiver volume                                                                            " ) \
F( NavigationCOM2StandbyFrequency,        "Communication.COM2StandbyFrequency",       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM2 transceiver standby frequency                                                                           " ) \
F( NavigationCOM2FrequencySwap,           "Communication.COM2FrequencySwap",          tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "COM2 frequency swap                                                                                          " ) \
F( NavigationCOM3Frequency,               "Communication.COM3Frequency",              tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM3 transceiver active frequency                                                                            " ) \
F( NavigationCOM3StandbyFrequency,        "Communication.COM3StandbyFrequency",       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Hertz,                    "COM3 transceiver standby frequency                                                                           " ) \
F( NavigationCOM3FrequencySwap,           "Communication.COM3FrequencySwap",          tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "COM3 frequency swap                                                                                          " ) \
F( NavigationAUXAudioSelect,              "Communication.AUXAudioSelect",             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "COM1 transceiver volume                                                                            " ) \
F( TransponderCode,                       "Communication.TransponderCode",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "Transponder code                                                                                             " ) \
F( TransponderMode,                       "Communication.TransponderMode",            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "Transponder code                                                                                             " ) \
F( TransponderIdent,                      "Communication.TransponderIdent",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "Transponder code                                                                                             " ) \
F( TransponderCursor,                     "Communication.TransponderCursor",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "Transponder blinking cursor position                                                                         " ) \
F( MicrophoneSelect,                      "Communication.MicrophoneSelect",           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "Transponder code                                                                                             " ) \
F( AutopilotMaster,                       "Autopilot.Master",                         tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( AutopilotDisengage,                    "Autopilot.Disengage",                      tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "disengage all autopilots                                                                                     " ) \
F( AutopilotHeading,                      "Autopilot.Heading",                        tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( AutopilotVerticalSpeed,                "Autopilot.VerticalSpeed",                  tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::MeterPerSecond,           "                                                                                                             " ) \
F( AutopilotSelectedSpeed,                "Autopilot.SelectedSpeed",                  tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::MeterPerSecond,           "                                                                                                             " ) \
F( AutopilotSelectedAirspeed,             "Autopilot.SelectedAirspeed",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::MeterPerSecond,           "autopilot/flight director selected airspeed, speed bug                                                       " ) \
F( AutopilotSelectedHeading,              "Autopilot.SelectedHeading",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Radiant,                  "autopilot/flight director selected heading, heading bug                                                      " ) \
F( AutopilotSelectedAltitude,             "Autopilot.SelectedAltitude",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::Meter,                    "autopilot/flight director selected altitude                                                                  " ) \
F( AutopilotSelectedVerticalSpeed,        "Autopilot.SelectedVerticalSpeed",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::MeterPerSecond,           "autopilot/flight director selected vertical speed                                                            " ) \
F( AutopilotSelectedAltitudeScale,        "Autopilot.SelectedAltitudeScale",          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director selected altitude step size small/large                                            " ) \
F( AutopilotActiveLateralMode,            "Autopilot.ActiveLateralMode",              tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name of the active lateral  mode                                          " ) \
F( AutopilotArmedLateralMode,             "Autopilot.ArmedLateralMode",               tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name of the armed  lateral  mode                                          " ) \
F( AutopilotActiveVerticalMode,           "Autopilot.ActiveVerticalMode",             tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name of the active vertical mode                                          " ) \
F( AutopilotArmedVerticalMode,            "Autopilot.ArmedVerticalMode",              tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name of the armed  vertical mode                                          " ) \
F( AutopilotArmedApproachMode,            "Autopilot.ArmedApproachMode",              tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name of the armed  approach mode                                          " ) \
F( AutopilotActiveAutoThrottleMode,       "Autopilot.ActiveAutoThrottleMode",         tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name the active autothrottle mode                                         " ) \
F( AutopilotActiveCollectiveMode,         "Autopilot.ActiveCollectiveMode",           tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name the active helicopter collective mode                                " ) \
F( AutopilotArmedCollectiveMode,          "Autopilot.ArmedCollectiveMode",            tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot/flight director internal name the armed  helicopter collective mode                                " ) \
F( AutopilotType,                         "Autopilot.Type",                           tm_msg_data_type::String,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot type installed                                                                                     " ) \
F( AutopilotEngaged,                      "Autopilot.Engaged",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "set if autopilot is engaged                                                                                  " ) \
F( AutopilotUseMachNumber,                "Autopilot.UseMachNumber",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot mach/speed toggle state                                                                            " ) \
F( AutopilotSpeedManaged,                 "Autopilot.SpeedManaged",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot managed/selected speed state                                                                       " ) \
F( AutopilotTargetAirspeed,               "Autopilot.TargetAirspeed",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot target airspeed                                                                                    " ) \
F( AutopilotAileron,                      "Autopilot.Aileron",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot aileron command                                                                                    " ) \
F( AutopilotElevator,                     "Autopilot.Elevator",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "autopilot elevator command                                                                                   " ) \
F( AutoAutoThrottleType,                  "AutoThrottle.Type",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto-throttle type installed                                                                                 " ) \
F( AutopilotThrottleEngaged,              "Autopilot.ThrottleEngaged",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto-throttle state                                                                                          " ) \
F( AutopilotThrottleCommand,              "Autopilot.ThrottleCommand",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "auto-throttle command                                                                                        " ) \
F( FlightDirectorPitch,                   "FlightDirector.Pitch",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "flight director pitch angle relative to current pitch                                                        " ) \
F( FlightDirectorBank,                    "FlightDirector.Bank",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "flight director bank angle relative to current bank                                                          " ) \
F( FlightDirectorYaw,                     "FlightDirector.Yaw",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "flight director yaw command                                                                                  " ) \
F( CopilotHeading,                        "Copilot.Heading",                          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( CopilotAltitude,                       "Copilot.Altitude",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( CopilotAirspeed,                       "Copilot.Airspeed",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "                                                                                                             " ) \
F( CopilotVerticalSpeed,                  "Copilot.VerticalSpeed",                    tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::MeterPerSecond,           "                                                                                                             " ) \
F( CopilotAileron,                        "Copilot.Aileron",                          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( CopilotElevator,                       "Copilot.Elevator",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( CopilotThrottle,                       "Copilot.Throttle",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( CopilotAutoRudder,                     "Copilot.AutoRudder",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Read,      tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrottle,                      "Controls.Throttle",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "generic throttle position                                                                                    " ) \
F( ControlsThrottle1,                     "Controls.Throttle1",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "throttle position for engine 1                                                                               " ) \
F( ControlsThrottle2,                     "Controls.Throttle2",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "throttle position for engine 2                                                                               " ) \
F( ControlsThrottle3,                     "Controls.Throttle3",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "throttle position for engine 3                                                                               " ) \
F( ControlsThrottle4,                     "Controls.Throttle4",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "throttle position for engine 4                                                                               " ) \
F( ControlsThrottle1Move,                 "Controls.Throttle1",                       tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::PerSecond,                "throttle rate of change for engine 1                                                                         " ) \
F( ControlsThrottle2Move,                 "Controls.Throttle2",                       tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::PerSecond,                "throttle rate of change for engine 2                                                                         " ) \
F( ControlsThrottle3Move,                 "Controls.Throttle3",                       tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::PerSecond,                "throttle rate of change for engine 3                                                                         " ) \
F( ControlsThrottle4Move,                 "Controls.Throttle4",                       tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::PerSecond,                "throttle rate of change for engine 4                                                                         " ) \
F( ControlsPitchInput,                    "Controls.Pitch.Input",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPitchInputOffset,              "Controls.Pitch.Input",                     tm_msg_data_type::Double,   tm_msg_flag::Offset, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsRollInput,                     "Controls.Roll.Input",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsRollInputOffset,               "Controls.Roll.Input",                      tm_msg_data_type::Double,   tm_msg_flag::Offset, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsYawInput,                      "Controls.Yaw.Input",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsYawInputActive,                "Controls.Yaw.Input",                       tm_msg_data_type::Double,   tm_msg_flag::Active, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsFlaps,                         "Controls.Flaps",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsFlapsEvent,                    "Controls.Flaps",                           tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsGear,                          "Controls.Gear",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "gear lever                                                                                                   " ) \
F( ControlsGearToggle,                    "Controls.Gear",                            tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "gear lever                                                                                                   " ) \
F( ControlsWheelBrakeLeft,                "Controls.WheelBrake.Left",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsWheelBrakeRight,               "Controls.WheelBrake.Right",                tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsWheelBrakeLeftActive,          "Controls.WheelBrake.Left",                 tm_msg_data_type::Double,   tm_msg_flag::Active, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsWheelBrakeRightActive,         "Controls.WheelBrake.Right",                tm_msg_data_type::Double,   tm_msg_flag::Active, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsAirBrake,                      "Controls.AirBrake",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsAirBrakeActive,                "Controls.AirBrake",                        tm_msg_data_type::Double,   tm_msg_flag::Active, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsAirBrakeArm,                   "Controls.AirBrake.Arm",                    tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsGliderAirBrake,                "Controls.GliderAirBrake",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPropellerSpeed1,               "Controls.PropellerSpeed1",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPropellerSpeed2,               "Controls.PropellerSpeed2",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPropellerSpeed3,               "Controls.PropellerSpeed3",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPropellerSpeed4,               "Controls.PropellerSpeed4",                 tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsMixture,                       "Controls.Mixture",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsMixture1,                      "Controls.Mixture1",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsMixture2,                      "Controls.Mixture2",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsMixture3,                      "Controls.Mixture3",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsMixture4,                      "Controls.Mixture4",                        tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrustReverse,                 "Controls.ThrustReverse",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrustReverse1,                "Controls.ThrustReverse1",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrustReverse2,                "Controls.ThrustReverse2",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrustReverse3,                "Controls.ThrustReverse3",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsThrustReverse4,                "Controls.ThrustReverse4",                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsCollective,                    "Controls.Collective",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsCyclicPitch,                   "Controls.CyclicPitch",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsCyclicRoll,                    "Controls.CyclicRoll",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsTailRotor,                     "Controls.TailRotor",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsRotorBrake,                    "Controls.RotorBrake",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsHelicopterThrottle1,           "Controls.HelicopterThrottle1",             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsHelicopterThrottle2,           "Controls.HelicopterThrottle2",             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsTrim,                          "Controls.Trim",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsTrimStep,                      "Controls.Trim",                            tm_msg_data_type::Double,   tm_msg_flag::Step,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsTrimMove,                      "Controls.Trim",                            tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsAileronTrim,                   "Controls.AileronTrim",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsRudderTrim,                    "Controls.RudderTrim",                      tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsTiller,                        "Controls.Tiller",                          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPedalsDisconnect,              "Controls.PedalsDisconnect",                tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsNoseWheelSteering,             "Controls.NoseWheelSteering",               tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsLightingPanel,                 "Controls.Lighting.Panel",                  tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsLightingInstruments,           "Controls.Lighting.Instruments",            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsPressureSetting0,              "Controls.PressureSetting0",                tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "captain pressure setting in Pa                                                                               " ) \
F( ControlsPressureSettingStandard0,      "Controls.PressureSettingStandard0",        tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "captain pressure setting is STD                                                                              " ) \
F( ControlsPressureSettingUnit0,          "Controls.PressureSettingUnit0",            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "captain pressure setting is set display inHg                                                                 " ) \
F( ControlsPressureSetting1,              "Controls.PressureSetting1",                tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "f/o     pressure setting in Pa                                                                               " ) \
F( ControlsPressureSettingStandard1,      "Controls.PressureSettingStandard1",        tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "f/o     pressure setting is STD                                                                              " ) \
F( ControlsPressureSettingUnit1,          "Controls.PressureSettingUnit1",            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "f/o     pressure setting is set display inHg                                                                 " ) \
F( ControlsPressureSetting2,              "Controls.PressureSetting2",                tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "standby pressure setting in Pa                                                                               " ) \
F( ControlsPressureSettingStandard2,      "Controls.PressureSettingStandard2",        tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "standby pressure setting is STD                                                                              " ) \
F( ControlsPressureSettingUnit2,          "Controls.PressureSettingUnit2",            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "standby pressure setting is set display inHg                                                                 " ) \
F( ControlsTransitionAltitude,            "Controls.TransitionAltitude",              tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "pressure setting transition altitude (QNH->STD)                                                              " ) \
F( ControlsTransitionLevel,               "Controls.TransitionLevel",                 tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::Meter,                    "pressure setting transition level    (STD->QNH)                                                              " ) \
F( PressurizationLandingElevation,        "Pressurization.LandingElevation",          tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( PressurizationLandingElevationManual,  "Pressurization.LandingElevationManual",    tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( WarningsMasterWarning,                 "Warnings.MasterWarning",                   tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "master warning active                                                                                        " ) \
F( WarningsMasterCaution,                 "Warnings.MasterCaution",                   tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "master caution active                                                                                        " ) \
F( WarningsEngineFire,                    "Warnings.EngineFire",                      tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "engine fire active                                                                                           " ) \
F( WarningsLowOilPressure,                "Warnings.LowOilPressure",                  tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "low oil pressure warning active                                                                              " ) \
F( WarningsLowFuelPressure,               "Warnings.LowFuelPressure",                 tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "low fuel pressure warning active                                                                             " ) \
F( WarningsLowHydraulicPressure,          "Warnings.LowHydraulicPressure",            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "low hydraulic pressure warning active                                                                        " ) \
F( WarningsLowVoltage,                    "Warnings.LowVoltage",                      tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "low voltage warning active                                                                                   " ) \
F( WarningsAltitudeAlert,                 "Warnings.AltitudeAlert",                   tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "altitude alert warning active                                                                                " ) \
F( WarningsWarningActive,                 "Warnings.WarningActive",                   tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "warnings active                                                                                              " ) \
F( WarningsWarningMute,                   "Warnings.WarningMute",                     tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Read,      tm_msg_unit::None,                     "warning suppression                                                                                          " ) \
F( ViewDisplayName,                       "View.DisplayName",                         tm_msg_data_type::String,   tm_msg_flag::None,   tm_msg_access::Read,      tm_msg_unit::None,                     "name of current view                                                                                         " ) \
F( ViewInternal,                          "View.Internal",                            tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "set view to last internal view                                                                               " ) \
F( ViewFollow,                            "View.Follow",                              tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "set view to last follow view                                                                                 " ) \
F( ViewExternal,                          "View.External",                            tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "set view to last external view                                                                               " ) \
F( ViewCategory,                          "View.Category",                            tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "change to next / previous view category (internal,follow,external), set last view in this category           " ) \
F( ViewMode,                              "View.Mode",                                tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "set next / previous view in current category                                                                 " ) \
F( ViewZoom,                              "View.Zoom",                                tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewPanHorizontal,                     "View.Pan.Horizontal",                      tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewPanHorizontalMove,                 "View.Pan.Horizontal",                      tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewPanVertical,                       "View.Pan.Vertical",                        tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewPanVerticalMove,                   "View.Pan.Vertical",                        tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewPanCenter,                         "View.Pan.Center",                          tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewLookHorizontal,                    "View.Look.Horizontal",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "momentarily look left / right                                                                                " ) \
F( ViewLookVertical,                      "View.Look.Vertical",                       tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "momentarily look up / down                                                                                   " ) \
F( ViewRoll,                              "View.Roll",                                tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewOffsetX,                           "View.OffsetX",                             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "offset (forward/backward) from view's default position                                                       " ) \
F( ViewOffsetXMove,                       "View.OffsetX",                             tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "change offset (forward/backward) from view's default position                                                " ) \
F( ViewOffsetY,                           "View.OffsetY",                             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "lateral offset from view's default position                                                                  " ) \
F( ViewOffsetYMove,                       "View.OffsetY",                             tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "change lateral offset from view's default position                                                           " ) \
F( ViewOffsetZ,                           "View.OffsetZ",                             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "vertical offset from view's default position                                                                 " ) \
F( ViewOffsetZMove,                       "View.OffsetZ",                             tm_msg_data_type::Double,   tm_msg_flag::Move,   tm_msg_access::Write,     tm_msg_unit::None,                     "change vertical offset from view's default position                                                          " ) \
F( ViewPosition,                          "View.Position",                            tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewDirection,                         "View.Direction",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewUp,                                "View.Up",                                  tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewFieldOfView,                       "View.FieldOfView",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewAspectRatio,                       "View.AspectRatio",                         tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewFreePosition,                      "View.FreePosition",                        tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::Meter,                    "the following 4 messages allow you to implement your own view                                                " ) \
F( ViewFreeLookDirection,                 "View.FreeLookDirection",                   tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewFreeUp,                            "View.FreeUp",                              tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ViewFreeFieldOfView,                   "View.FreeFieldOfView",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::Radiant,                  "                                                                                                             " ) \
F( SimulationPause,                       "Simulation.Pause",                         tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::ReadWrite, tm_msg_unit::None,                     "toggle pause on/off                                                                                          " ) \
F( SimulationFlightInformation,           "Simulation.FlightInformation",             tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "show/hide the flight information at the top of the screen                                                    " ) \
F( SimulationMovingMap,                   "Simulation.MovingMap",                     tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "show/hide the moving map window                                                                              " ) \
F( SimulationSound,                       "Simulation.Sound",                         tm_msg_data_type::Double,   tm_msg_flag::Toggle, tm_msg_access::Write,     tm_msg_unit::None,                     "toggle sound on/off                                                                                          " ) \
F( SimulationLiftUp,                      "Simulation.LiftUp",                        tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "lift up the aircraft from current position                                                                   " ) \
F( SimulationSettingPosition,             "Simulation.SettingPosition",               tm_msg_data_type::Vector3d, tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( SimulationSettingOrientation,          "Simulation.SettingOrientation",            tm_msg_data_type::Vector4d, tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( SimulationSettingVelocity,             "Simulation.SettingVelocity",               tm_msg_data_type::Vector3d, tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::MeterPerSecond,           "                                                                                                             " ) \
F( SimulationSettingSet,                  "Simulation.SettingSet",                    tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( SimulationTimeChange,                  "Simulation.TimeChange",                    tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "change time of day                                                                                           " ) \
F( SimulationVisibility,                  "Simulation.Visibility",                    tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "                                                                                                             " ) \
F( SimulationTime,                        "Simulation.Time",                          tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "                                                                                                             " ) \
F( SimulationUseMouseControl,             "Simulation.UseMouseControl",               tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::ReadWrite, tm_msg_unit::None,                     "                                                                                                             " ) \
F( SimulationPlaybackStart,               "Simulation.PlaybackStart",                 tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "start playback if simulation is paused                                                                       " ) \
F( SimulationPlaybackStop,                "Simulation.PlaybackStop",                  tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "stop playback                                                                                                " ) \
F( SimulationPlaybackSetPosition,         "Simulation.PlaybackPosition",              tm_msg_data_type::Double,   tm_msg_flag::None,   tm_msg_access::Write,     tm_msg_unit::None,                     "set playback position 0 - 1                                                                                  " ) \
F( SimulationExternalPosition,            "Simulation.ExternalPosition",              tm_msg_data_type::Vector3d, tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::Meter,                    "                                                                                                             " ) \
F( SimulationExternalOrientation,         "Simulation.ExternalOrientation",           tm_msg_data_type::Vector4d, tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandExecute,                        "Command.Execute",                          tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandBack,                           "Command.Back",                             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandUp,                             "Command.Up",                               tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandDown,                           "Command.Down",                             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandLeft,                           "Command.Left",                             tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandRight,                          "Command.Right",                            tm_msg_data_type::Double,   tm_msg_flag::Event,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandMoveHorizontal,                 "Command.MoveHorizontal",                   tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandMoveVertical,                   "Command.MoveVertical",                     tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandRotate,                         "Command.Rotate",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( CommandZoom,                           "Command.Zoom",                             tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "                                                                                                             " ) \
F( ControlsSpeed,                         "Controls.Speed",                           tm_msg_data_type::Double,   tm_msg_flag::Value,  tm_msg_access::Write,     tm_msg_unit::None,                     "ignore/do not use  combined throttle, brake and reverse, copilot splits into other                           " ) \
F( FMSData0,                              "FlightManagementSystem.Data0",             tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  FMS binary datablock                                                                      " ) \
F( FMSData1,                              "FlightManagementSystem.Data1",             tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  FMS binary datablock                                                                      " ) \
F( NAV1Data,                              "Navigation.NAV1Data",                      tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  NAV1 binary datablock                                                                     " ) \
F( NAV2Data,                              "Navigation.NAV2Data",                      tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  NAV2 binary datablock                                                                     " ) \
F( NAV3Data,                              "Navigation.NAV3Data",                      tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  NAV3 binary datablock                                                                     " ) \
F( ILS1Data,                              "Navigation.ILS1Data",                      tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  ILS1 binary datablock                                                                     " ) \
F( ILS2Data,                              "Navigation.ILS2Data",                      tm_msg_data_type::None,     tm_msg_flag::Value,  tm_msg_access::None,      tm_msg_unit::None,                     "ignore/do not use  ILS2 binary datablock                                                                     " ) \

MESSAGE_LIST( TM_MESSAGE )




//////////////////////////////////////////////////////////////////////////////////////////////////
//
// a small helper function that shows the name of a message as plain text if an ID is passed
//
//////////////////////////////////////////////////////////////////////////////////////////////////
struct tm_message_type
{
  tm_string       String;
  tm_string_hash  StringHash;
  template <tm_uint32 N> constexpr tm_message_type( const char( &str )[N] ) : String{ str }, StringHash{ str } { }
};

static std::vector<tm_message_type> MessageTypeList =
{
  MESSAGE_LIST( TM_MESSAGE_NAME )
};

static tm_string GetMessageName( const tm_external_message &message )
{
  for ( const auto &mt : MessageTypeList )
  {
    if ( message.GetID() == mt.StringHash.GetHash() ) { return mt.String; }
  }

  return tm_string( "unknown" );
}


// Helper function to convert double to string with precision
std::string DoubleToString(double value) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(6) << value;
    return oss.str();
}

// Helper function to escape JSON strings
std::string EscapeJson(const std::string& s) {
    std::string result;
    for (char c : s) {
        if (c == '"' || c == '\\') result += '\\';
        result += c;
    }
    return result;
}

// Helper function to build JSON from messages
std::string BuildJsonFromMessages(const std::vector<tm_external_message>& messages, double timestamp) {
    std::ostringstream json;
    json << "{";
    json << "\"timestamp\":" << DoubleToString(timestamp) << ",";

    bool first = true;
    for (const auto& message : messages) {
        auto message_name = GetMessageName(message);

        
        if (!first) json << ",";
        first = false;

        json << "\"" << EscapeJson(message_name.c_str()) << "\":";

        switch (message.GetDataType()) {
        case tm_msg_data_type::Int:
            json << message.GetInt();
            break;
        case tm_msg_data_type::Double:
            json << DoubleToString(message.GetDouble());
            break;
        case tm_msg_data_type::Vector2d: {
            auto v = message.GetVector2d();
            json << "[" << DoubleToString(v.x) << "," << DoubleToString(v.y) << "]";
            break;
        }
        case tm_msg_data_type::Vector3d: {
            auto v = message.GetVector3d();
            json << "[" << DoubleToString(v.x) << "," << DoubleToString(v.y) << "," << DoubleToString(v.z) << "]";
            break;
        }
        case tm_msg_data_type::Vector4d: {
            auto v = message.GetVector4d();
            json << "[" << DoubleToString(v.x) << "," << DoubleToString(v.y) << "," << DoubleToString(v.z) << "," << DoubleToString(v.w) << "]";
            break;
        }
        case tm_msg_data_type::String:
        case tm_msg_data_type::String8: {
            auto s = message.GetString();
            json << "\"" << EscapeJson(s.c_str()) << "\"";
            break;
        }
        default:
            json << "null";
            break;
        }
    }

    json << "}";
    return json.str();
}


//////////////////////////////////////////////////////////////////////////////////////////////////
//
// code that opens a window and displays the received messages as text
// its meant just as a simple helper to get started with the DLL
//
// THIS CODE SHOULD NOT BE USED IN A PRODUCTION DLL
//
//////////////////////////////////////////////////////////////////////////////////////////////////
#include <gdiplus.h>
#pragma message("including lib: gdiplus.lib")
#pragma comment(lib, "gdiplus.lib")

static ULONG_PTR                         Global_DebugOutput_gdiplusToken = NULL;
static std::thread                       Global_DebugOutput_Thread;
static HWND                              Global_DebugOutput_Window = NULL;
static bool                              Global_DebugOutput_WindowCloseMessage = false;

static std::vector<tm_external_message>  MessageListReceive;
static std::vector<tm_external_message>  MessageListCopy;
static std::vector<tm_external_message>  MessageListDebugOutput;
static std::mutex                        MessageListMutex;
static double                            MessageDeltaTime = 0;

static std::mutex                        VR_DataMutex;
static tm_vector3d                       VR_Head_Position;
static tm_matrix3d                       VR_Head_Orientation;
static int                               VR_NumControllers = 0;
static tm_vector3d                       VR_Controller0_Position;
static tm_quaterniond                    VR_Controller0_Orientation;
static tm_vector3d                       VR_Controller1_Position;
static tm_quaterniond                    VR_Controller1_Orientation;

const int SAMPLE_WINDOW_WIDTH  = 1600;
const int SAMPLE_WINDOW_HEIGHT = 1280;

void DebugOutput_Draw( HDC hDC )
{
  // clear and draw to a bitmap instead to the hdc directly to avoid flicker
  Gdiplus::Bitmap     backbuffer( SAMPLE_WINDOW_WIDTH, SAMPLE_WINDOW_HEIGHT, PixelFormat24bppRGB );
  Gdiplus::Graphics   graphics( &backbuffer );
  Gdiplus::SolidBrush black( Gdiplus::Color( 255, 0, 0, 0 ) );
  Gdiplus::FontFamily fontFamily( L"Courier New" );
  Gdiplus::Font       font( &fontFamily, 12, Gdiplus::FontStyleRegular, Gdiplus::UnitPixel );
  Gdiplus::Color      clearcolor( 255, 220, 232, 244 );

  graphics.Clear( clearcolor );

  if ( !MessageListCopy.empty() )
  {
    std::lock_guard<std::mutex> lock_guard{ MessageListMutex };
    MessageListDebugOutput.swap( MessageListCopy );
  }

  const float indent = 500.0f;

  {
    float x = 0.0f;
    float y = 4.0f;
    WCHAR text1[256];
    WCHAR text2[256];


    tm_vector3d head_pos;
    tm_matrix3d head_orientation;
    tm_vector3d controller0_pos;
    tm_vector3d controller1_pos;
    int         vr_num_controllers = 0;
    {
      std::lock_guard<std::mutex> lock_guard{ VR_DataMutex };
      head_pos = VR_Head_Position;
      head_orientation = VR_Head_Orientation;
      vr_num_controllers = VR_NumControllers;
      if ( vr_num_controllers > 0 ) { controller0_pos = VR_Controller0_Position; }
      if ( vr_num_controllers > 1 ) { controller1_pos = VR_Controller1_Position; }
    }

    _snwprintf_s( &text1[0], 255, _TRUNCATE, L"vrpos = %.3f %.3f %.3f", head_pos.x, head_pos.y, head_pos.z );
    graphics.DrawString( &text1[0], -1, &font, Gdiplus::PointF( x + 10, y ), &black );

    y += 16;

    if ( vr_num_controllers > 0 )
    {
      if      ( vr_num_controllers > 1 ) { _snwprintf_s( &text1[0], 255, _TRUNCATE, L"vrc0pos = %.3f %.3f %.3f  vrc0pos = %.3f %.3f %.3f", controller0_pos.x, controller0_pos.y, controller0_pos.z, controller1_pos.x, controller1_pos.y, controller1_pos.z ); }
      else if ( vr_num_controllers > 0 ) { _snwprintf_s( &text1[0], 255, _TRUNCATE, L"vrc0pos = %.3f %.3f %.3f", controller0_pos.x, controller0_pos.y, controller0_pos.z ); }
      graphics.DrawString( &text1[0], -1, &font, Gdiplus::PointF( x + 10, y ), &black );
      y += 16;
    }

    _snwprintf_s( &text1[0], 255, _TRUNCATE, L"messages = %llu  dt=%f", MessageListDebugOutput.size(), MessageDeltaTime );
    graphics.DrawString( &text1[0], -1, &font, Gdiplus::PointF( x + 10, y ), &black );
    y += 16;

    int index = 0;
    for ( auto &message : MessageListDebugOutput )
    {
      switch ( message.GetDataType() )
      {
        case tm_msg_data_type::None:     {                                       _snwprintf_s( &text1[0], 255, _TRUNCATE, L"none" );                                      } break;
        case tm_msg_data_type::Int:      { const auto v = message.GetInt();      _snwprintf_s( &text1[0], 255, _TRUNCATE, L"%lld", v );                                   } break;
        case tm_msg_data_type::Double:   { const auto v = message.GetDouble();   _snwprintf_s( &text1[0], 255, _TRUNCATE, L"%.3f", v );                                   } break;
        case tm_msg_data_type::Vector2d: { const auto v = message.GetVector2d(); _snwprintf_s( &text1[0], 255, _TRUNCATE, L"(%.1f %.1f)", v.x, v.y );                     } break;
        case tm_msg_data_type::Vector3d: { const auto v = message.GetVector3d(); _snwprintf_s( &text1[0], 255, _TRUNCATE, L"(%.1f %.1f %.1f)", v.x, v.y, v.z );           } break;
        case tm_msg_data_type::Vector4d: { const auto v = message.GetVector4d(); _snwprintf_s( &text1[0], 255, _TRUNCATE, L"(%.1f %.1f %.1f %.1f)", v.x, v.y, v.z, v.w ); } break;
        case tm_msg_data_type::String:   { const auto v = message.GetString();   _snwprintf_s( &text1[0], 255, _TRUNCATE, L"'%hs'", v.c_str() );                          } break;
        case tm_msg_data_type::String8:  { const auto v = message.GetString();   _snwprintf_s( &text1[0], 255, _TRUNCATE, L"'%hs'", v.c_str() );                          } break;
      }

      //_snwprintf_s( &text2[0], 255, _TRUNCATE, L"%3u:  size=%u", ++index, message.GetMessageSize() );
      _snwprintf_s( &text2[0], 255, _TRUNCATE, L"%3u:", ++index );
      graphics.DrawString( &text2[0], -1, &font, Gdiplus::PointF( x +  0, y ), &black );

      graphics.DrawString( &text1[0], -1, &font, Gdiplus::PointF( x + 40, y ), &black );

      auto message_name = GetMessageName( message );
      _snwprintf_s( &text1[0], 255, _TRUNCATE, L"'%hs'  flags=%llu", message_name.c_str(), message.GetFlags().GetFlags() );
      graphics.DrawString( &text1[0], -1, &font, Gdiplus::PointF( x + 140, y ), &black );

      y += 16;

      if ( y > SAMPLE_WINDOW_HEIGHT - 60 )
      {
        y = 4.0f;
        x += indent;
      }

      if ( x > SAMPLE_WINDOW_WIDTH )
      {
        break;
      }
    }
  }

  // copy 'backbuffer' image to screen
  Gdiplus::Graphics graphics_final( hDC );
  graphics_final.DrawImage( &backbuffer, 0, 0 );
}

LRESULT WINAPI DebugOutput_WndProc( HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam )
{
  switch ( msg )
  {
    case WM_PAINT:
      {
        PAINTSTRUCT ps;
        auto hDC = BeginPaint( hWnd, &ps );
        DebugOutput_Draw( hDC );
        EndPaint( hWnd, &ps );
      }
      return 0;

    case WM_TIMER:
      InvalidateRect( hWnd, 0, FALSE );
      return 0;

    case WM_CLOSE:
      Global_DebugOutput_WindowCloseMessage = true;
      break;

    case WM_DESTROY:
      PostQuitMessage( 0 );
      return 0;
  }

  return DefWindowProc( hWnd, msg, wParam, lParam );
}

void DebugOutput_CreateWindow( HINSTANCE hInstance )
{
  const char classname[] = "aerofly_external_dll_sample";

  //
  // init gdi+
  //
  Gdiplus::GdiplusStartupInput startupinput;
  auto status = GdiplusStartup( &Global_DebugOutput_gdiplusToken, &startupinput, NULL );

  if ( status != Gdiplus::Status::Ok )
  {
    // bummer
    return;
  }

  //
  // fill in window class structure and register the class
  //
  WNDCLASS wc;
  wc.style         = CS_HREDRAW | CS_VREDRAW;
  wc.lpfnWndProc   = DebugOutput_WndProc;                // Window Procedure
  wc.cbClsExtra    = 0;
  wc.cbWndExtra    = 0;
  wc.hInstance     = hInstance;                          // Owner of this class
  wc.hIcon         = LoadIcon( NULL, IDI_INFORMATION );
  wc.hCursor       = LoadCursor( NULL, IDC_ARROW );
  wc.hbrBackground = (HBRUSH) ( COLOR_BACKGROUND + 1 );      // Default color
  wc.lpszMenuName  = NULL;
  wc.lpszClassName = classname;
  RegisterClass( &wc );

  Global_DebugOutput_WindowCloseMessage = false;

  Global_DebugOutput_Window = CreateWindow( classname, "Aerofly External DLL Sample",
                                            WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN | WS_CLIPSIBLINGS, CW_USEDEFAULT,
                                            0, SAMPLE_WINDOW_WIDTH, SAMPLE_WINDOW_HEIGHT,
                                            NULL,       // no parent window
                                            NULL,       // Use the window class menu.
                                            hInstance,  // This instance owns this window
                                            NULL );     // We don't use any extra data


  auto s_width  = GetSystemMetrics( SM_CXSCREEN );
//auto s_height = GetSystemMetrics( SM_CYSCREEN );

  SetWindowPos( Global_DebugOutput_Window, HWND_TOP, s_width - SAMPLE_WINDOW_WIDTH, 0, SAMPLE_WINDOW_WIDTH, SAMPLE_WINDOW_HEIGHT, SWP_SHOWWINDOW );
  // set up timers
  SetTimer( Global_DebugOutput_Window, 0, 500, 0 );

  MSG msg;
  while ( !Global_DebugOutput_WindowCloseMessage && GetMessage( &msg, Global_DebugOutput_Window, 0, 0 ) )
  {
    TranslateMessage( &msg );
    DispatchMessage( &msg );
  }

  DestroyWindow( Global_DebugOutput_Window );
  Global_DebugOutput_Window = NULL;

  //
  // shutdown gdi+
  //
  Gdiplus::GdiplusShutdown( Global_DebugOutput_gdiplusToken );
}

void DebugOutput_WindowUpdate( const double delta_time, const std::vector<tm_external_message> &message_list_receive )
{
  // this is just for the debug output window
  std::lock_guard<std::mutex> lock_guard{ MessageListMutex };
  MessageListCopy = message_list_receive;
  MessageDeltaTime = delta_time;
}

void DebugOutput_WindowOpen()
{
  Global_DebugOutput_Thread = std::thread( DebugOutput_CreateWindow, global_hDLLinstance );
}

void DebugOutput_WindowClose()
{
  if ( Global_DebugOutput_Window != NULL )
  {
    PostMessage( Global_DebugOutput_Window, WM_QUIT, 0, 0 );
  }
  Global_DebugOutput_Thread.join();
}




//////////////////////////////////////////////////////////////////////////////////////////////////
//
// the main entry point for the DLL
//
//////////////////////////////////////////////////////////////////////////////////////////////////
BOOL WINAPI DllMain( HANDLE hdll, DWORD reason, LPVOID reserved )
{
  switch ( reason )
  {
    case DLL_THREAD_ATTACH:
      break;
    case DLL_THREAD_DETACH:
      break;
    case DLL_PROCESS_ATTACH:
      global_hDLLinstance = (HINSTANCE) hdll;
      break;
    case DLL_PROCESS_DETACH:
      break;
  }

  

  return TRUE;
}




//////////////////////////////////////////////////////////////////////////////////////////////////
//
// interface functions to Aerofly FS 4
//
//////////////////////////////////////////////////////////////////////////////////////////////////
extern "C"
{
  __declspec( dllexport ) int Aerofly_FS_4_External_DLL_GetInterfaceVersion()
  {
    return TM_DLL_INTERFACE_VERSION;
  }

  __declspec( dllexport ) bool Aerofly_FS_4_External_DLL_Init( const HINSTANCE Aerofly_FS_4_hInstance )
  {
    //DebugOutput_WindowOpen();
    
    // Create shared memory
    hMapFile = CreateFileMappingA(
        INVALID_HANDLE_VALUE,
        NULL,
        PAGE_READWRITE,
        0,
        SHARED_MEMORY_SIZE,
        "Local\\AeroflyFS4Data"  // Name that Python will use
    );

    if (hMapFile == NULL) {
        // Failed to create shared memory
        return false;
    }

    pSharedMemory = MapViewOfFile(
        hMapFile,
        FILE_MAP_ALL_ACCESS,
        0,
        0,
        SHARED_MEMORY_SIZE
    );

    if (pSharedMemory == NULL) {
        CloseHandle(hMapFile);
        hMapFile = NULL;
        return false;
    }

    // Initialize memory to zeros
    memset(pSharedMemory, 0, SHARED_MEMORY_SIZE);

    
    return true;
  }

  __declspec( dllexport ) void Aerofly_FS_4_External_DLL_Shutdown()
  {
      // Cleanup shared memory
      if (pSharedMemory != NULL) {
          UnmapViewOfFile(pSharedMemory);
          pSharedMemory = NULL;
      }

      if (hMapFile != NULL) {
          CloseHandle(hMapFile);
          hMapFile = NULL;
      }

      //DebugOutput_WindowClose();
  }

  __declspec(dllexport) void Aerofly_FS_4_External_DLL_Update(const tm_double         delta_time,
      const tm_uint8* const  message_list_received_byte_stream,
      const tm_uint32         message_list_received_byte_stream_size,
      const tm_uint32         message_list_received_num_messages,
      tm_uint8* message_list_sent_byte_stream,
      tm_uint32& message_list_sent_byte_stream_size,
      tm_uint32& message_list_sent_num_messages,
      const tm_uint32         message_list_sent_byte_stream_size_max)
  {
      //////////////////////////////////////////////////////////////////////////////////////////////
      //
      // build a list of messages that the simulation is sending
      //
      MessageListReceive.clear();

      tm_uint32 message_list_received_byte_stream_pos = 0;
      for (tm_uint32 i = 0; i < message_list_received_num_messages; ++i)
      {
          auto edm = tm_external_message::GetFromByteStream(message_list_received_byte_stream, message_list_received_byte_stream_pos);
          MessageListReceive.emplace_back(edm);
      }


      //////////////////////////////////////////////////////////////////////////////////////////////
      //
      // this is just for the debug output window
      //
      //DebugOutput_WindowUpdate(delta_time, MessageListReceive);

      // Build JSON and write to shared memory
      static double time = 0.0;
      time += delta_time;

      if (pSharedMemory != NULL && !MessageListReceive.empty())
      {
          std::string json = BuildJsonFromMessages(MessageListReceive, time);

          // Make sure we don't overflow the shared memory
          size_t json_size = json.size() + 1; // +1 for null terminator
          if (json_size <= SHARED_MEMORY_SIZE)
          {
              memset(pSharedMemory, 0, SHARED_MEMORY_SIZE);
              memcpy(pSharedMemory, json.c_str(), json_size);
          }
      }

      
  }
}



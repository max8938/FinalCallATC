#!/usr/bin/env python3
# pointer_read_double.py
# Follow a pointer path and read a double from another process (Windows).

import ctypes, struct, sys, time
from ctypes import wintypes
import psutil

TARGET_EXE = "aerofly_fs_4.exe"

# When game exe updates, this offset likely needs to be updated.

#BASE_OFFSET = 0x01669608 # exe from 23.9.2025
BASE_OFFSET = 0x0166A608 # exe from 30.9.2025


# ----------------- WIN32 CONSTANTS -----------------
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
TH32CS_SNAPMODULE = 0x00000008
MAX_PATH = 260

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
                                ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
ReadProcessMemory.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

# MODULE ENTRY STRUCT for EnumProcessModules / GetModuleBaseName fallback
# We'll try a simple approach: use psutil to get exe path, then enumerate modules via psapi
EnumProcessModules = psapi.EnumProcessModules
EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
EnumProcessModules.restype = wintypes.BOOL

GetModuleFileNameEx = psapi.GetModuleFileNameExA
GetModuleFileNameEx.argtypes = [wintypes.HANDLE, wintypes.HMODULE, ctypes.c_char_p, wintypes.DWORD]
GetModuleFileNameEx.restype = wintypes.DWORD

class MemoryReader():
    # ----------------- USER / GLOBALS -----------------
    

    

    # ----------------- HELPERS -----------------
    def find_pid_by_name(self, name):
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] and proc.info["name"].lower() == name.lower():
                return proc.info["pid"]
        return None

    def get_main_module_base(self, pid):
        """Return the base address of the main module (exe) or None if we can't find it."""
        h = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            return None
        try:
            # allocate an array to receive module handles
            needed = wintypes.DWORD()
            # first call to EnumProcessModules to get needed size
            # allocate capacity for, say, 1024 modules
            count = 1024
            arr_type = wintypes.HMODULE * count
            arr = arr_type()
            if not EnumProcessModules(h, arr, ctypes.sizeof(arr), ctypes.byref(needed)):
                return None
            n_mods = needed.value // ctypes.sizeof(wintypes.HMODULE)
            # iterate modules and look for module whose filename matches process exe name
            buf = ctypes.create_string_buffer(MAX_PATH)
            for i in range(min(n_mods, count)):
                mod = arr[i]
                if mod:
                    res = GetModuleFileNameEx(h, mod, buf, MAX_PATH)
                    if res:
                        path = buf.value.decode(errors='ignore')
                        # check if this module path ends with the target exe name
                        if path.lower().endswith("\\" + TARGET_EXE.lower()) or path.lower().endswith("/" + TARGET_EXE.lower()) or path.lower().endswith(TARGET_EXE.lower()):
                            # module handle returned by EnumProcessModules is the base address in practice
                            # convert module handle to integer base address
                            base_addr = ctypes.cast(mod, ctypes.c_void_p).value
                            return base_addr
            # fallback: return first module handle as base
            if n_mods > 0:
                return ctypes.cast(arr[0], ctypes.c_void_p).value
            return None
        finally:
            CloseHandle(h)

    def read_bytes(self, pid, address, size):
        h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not h:
            print("OpenProcess failed: run as admin or check permissions")
        try:
            buf = (ctypes.c_ubyte * size)()
            nread = ctypes.c_size_t()
            ok = ReadProcessMemory(h, ctypes.c_void_p(address), buf, size, ctypes.byref(nread))
            if not ok:
                print(f"ReadProcessMemory failed at 0x{address:X}")
            return bytes(buf[:nread.value])
        finally:
            CloseHandle(h)

    def read_qword(self, pid, address):
        data = self.read_bytes(pid, address, 8)
        return struct.unpack('<Q', data)[0]

    def read_double_at(self, pid, address):
        data = self.read_bytes(pid, address, 8)
        return struct.unpack('<d', data)[0]

    # ----------------- POINTER WALK MODES -----------------
    def walk_mode_a(self, offsets):
        """
        Mode A (common): start = base_addr
        For each offset in offsets:
            read qword at start -> p
            start = p + offset
        After loop: final_address = start
        Read double at final_address
        """
        

        cur = self.start_addr
        for off in offsets:
            p = self.read_qword(self.pid, cur)
            cur = p + off
            #print(f"cur: 0x{cur:X}")
        # cur now candidate address containing the double
        val = self.read_double_at(self.pid, cur)
        return cur, val



   

    pid = None
    start_addr = None

    def calculateStartAddress(self):
        import struct
        
        
        if (self.start_addr is None):
            self.pid = self.find_pid_by_name(TARGET_EXE)
            if self.pid is None:
                pass
                #print(f"Process {TARGET_EXE} not found. Start the process and retry.")
                #sys.exit(1)
            else:
                print(f"Found {TARGET_EXE} PID={self.pid}")

                module_base = self.get_main_module_base(self.pid)
                if module_base:
                    print(f"Main module base: 0x{module_base:X} (using module base + BASE_OFFSET)")
                    self.start_addr = module_base + BASE_OFFSET
                else:
                    print("Could not determine module base; treating BASE_OFFSET as absolute address")
                    self.start_addr = BASE_OFFSET

                #print(f"Computed starting address: 0x{self.start_addr:X}")

    def __init__(self):
        self.calculateStartAddress()
        

        
        

    def getDoubleMemValue(self, offsets):
        if (self.start_addr is None):
            self.calculateStartAddress()

        if (self.start_addr is None):
            return -1.0
        try:
            addrA, valA = self.walk_mode_a(offsets)
            #print(f"Address: 0x{addrA:X}  -> double: {valA}")
            return valA
        except Exception as e:
            print(f"Memory read failed: {e}")

    


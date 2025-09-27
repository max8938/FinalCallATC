import pygame
import time
import numpy as np

# Initialize mixer
pygame.mixer.init(frequency=44100, size=-16, channels=1)

# Morse code dictionary
MORSE_CODE = {
    'A': '.-',    'B': '-...',  'C': '-.-.',  'D': '-..',   'E': '.',
    'F': '..-.',  'G': '--.',   'H': '....',  'I': '..',    'J': '.---',
    'K': '-.-',   'L': '.-..',  'M': '--',    'N': '-.',    'O': '---',
    'P': '.--.',  'Q': '--.-',  'R': '.-.',   'S': '...',   'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',   'X': '-..-',  'Y': '-.--',
    'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--',
    '4': '....-', '5': '.....', '6': '-....',
    '7': '--...', '8': '---..', '9': '----.'
}

def make_tone(duration=0.1, freq=800, volume=0.2):
    """Generate a sine wave tone baked with volume scaling."""
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration), False)

    # Generate sine wave
    wave = np.sin(2 * np.pi * freq * t)

    # Scale to int16 with volume baked in
    wave = (32767 * volume * wave).astype(np.int16)

    # Create Sound object directly from buffer
    return pygame.mixer.Sound(buffer=wave)

# Pre-generate dit and dah
DIT = make_tone(0.1, freq=600, volume=0.2)  # short beep
DAH = make_tone(0.3, freq=600, volume=0.2)  # long beep

def play_morse(text):
    text = text.upper()
    for char in text:
        if char == " ":
            time.sleep(0.7)  # word gap
            continue
        if char not in MORSE_CODE:
            continue
        code = MORSE_CODE[char]
        for symbol in code:
            if symbol == ".":
                DIT.play()
                time.sleep(0.1)
            elif symbol == "-":
                DAH.play()
                time.sleep(0.3)
            time.sleep(0.1)  # gap between symbols
        time.sleep(0.3)  # gap between letters

# Example usage
if __name__ == "__main__":
    play_morse("CQ TEST")
    time.sleep(2)


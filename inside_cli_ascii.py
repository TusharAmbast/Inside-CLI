import sys
import time
import os
import random

# Your 9-letter blocks
BLOCKS = [
    ([" ██╗", " ██║", " ██║", " ██║", " ██║", " ╚═╝"], 4), # I
    (["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"], 10), # N
    (["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"], 8), # S
    (["██╗", "██║", "██║", "██║", "██║", "╚═╝"], 3), # I
    (["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "], 8), # D
    (["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"], 8), # E
    (["     ██████╗", "    ██╔════╝", "    ██║     ", "    ██║     ", "    ╚██████╗", "     ╚═════╝"], 12), # C
    (["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"], 8), # L
    (["██╗", "██║", "██║", "██║", "██║", "╚═╝"], 3)  # I
]

# Your custom 8-bit ANSI pairs (Text, Shadow)
# I've added a few more to make sure we have at least 9
COLOR_PAIRS = [
    ("\033[38;5;51m",  "\033[38;5;214m"),   # Cyan text & Bright Orange shadow
    ("\033[38;5;118m", "\033[38;5;213m"),   # Lime Green text & Hot Pink shadow
    ("\033[38;5;226m", "\033[38;5;93m"),    # Bright Yellow text & Bright Purple shadow
    ("\033[38;5;210m", "\033[38;5;51m"),    # Salmon text & Cyan shadow
    ("\033[38;5;171m", "\033[38;5;118m"),   # Violet text & Lime Green shadow
    ("\033[38;5;218m", "\033[38;5;230m"),   # Soft Pink & Cornsilk
    ("\033[38;5;220m" ,"\033[38;5;160m"),   # RED and gold
    ("\033[38;5;231m", "\033[38;5;160m"),   # Pure White / Crimson
    ("\033[38;5;210m", "\033[38;5;220m")    # Salmon text, Yellow 
]

RESET = "\033[0m"

def draw_letter(idx, text_color, shadow_color):
    x_offset = sum(b[1] for b in BLOCKS[:idx])
    for row, line in enumerate(BLOCKS[idx][0]):
        # Position cursor relative to terminal home
        sys.stdout.write(f"\033[{row+3};{x_offset+5}H") 
        
        # Replace structural/shadow characters with the shadow color
        styled = ""
        for char in line:
            if char in "═ ╝ ║ ╗ ╔ ╚ ":
                styled += f"{shadow_color}{char}{text_color}"
            else:
                styled += char
        sys.stdout.write(f"{text_color}{styled}{RESET}")
    sys.stdout.flush()

def main_animation():
    os.system('clear')
    sys.stdout.write("\033[?25l") # Hide cursor
    
    # 1. Shuffle the list of pairs so letters get different themes each run
    random.shuffle(COLOR_PAIRS)
    
    # 2. Decide on the 'Final' theme (the 9th pair in our shuffled list)
    final_pair = COLOR_PAIRS[-1]
    # Randomly flip the final pair's text/shadow role
    if random.choice([True, False]):
        final_pair = (final_pair[1], final_pair[0])

    # Store what we actually use for each letter to reference in the wave
    applied_themes = []

    try:
        # Phase 1: Left to Right
        for i in range(len(BLOCKS)):
            pair = COLOR_PAIRS[i]
            # Randomly decide to reverse THIS specific pair for this run
            if random.choice([True, False]):
                pair = (pair[1], pair[0])
            
            applied_themes.append(pair)
            draw_letter(i, pair[0], pair[1])
            time.sleep(0.15)

        time.sleep(0.6)

        # Phase 2: Right to Left (Wave turns everything into the 9th letter's theme)
        for i in range(len(BLOCKS)-1, -1, -1):
            # The 'Pulse' effect: Flash white before settling into the final color
            draw_letter(i, "\033[38;5;255m", "\033[38;5;250m")
            time.sleep(0.07)
            draw_letter(i, final_pair[0], final_pair[1])
            time.sleep(0.1)
            
        # Move cursor down and print 2 blank lines before ending
        sys.stdout.write(f"\033[10;5H")

    finally:
        sys.stdout.write("\033[?25h") # Show cursor

if __name__ == "__main__":
    main_animation()
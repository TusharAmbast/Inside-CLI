import time
import sys

def animate_left_aligned_sequence():
    # ==========================================
    # COLOR PALETTE CONFIGURATION
    # ==========================================
    green = "\033[1m\033[38;5;46m"        # Intro Text Color
    face_color = "\033[1m\033[38;5;220m"   # "Inside CLI" Royal Gold
    shadow_color = "\033[1m\033[38;5;57m" # "Inside CLI" Deep Purple
    
    reset = "\033[0m"
    shadow_chars = "╗║═╝╔╚"

    # ==========================================
    # 6-LINE ASCII ART DICTIONARIES
    # ==========================================
    art_hello = [
        r" ██╗  ██╗███████╗██╗     ██╗     ██████╗ ",
        r" ██║  ██║██╔════╝██║     ██║    ██╔═══██╗",
        r" ███████║█████╗  ██║     ██║    ██║   ██║",
        r" ██╔══██║██╔══╝  ██║     ██║    ██║   ██║",
        r" ██║  ██║███████╗███████╗███████╗╚██████╔╝",
        r" ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝ ╚═════╝ "
    ]

    art_amp = [
        r"      ███╗   ",
        r"     ██╔═██╗ ",
        r"     ╚███╔██╗",
        r"     ██╔═╝██║",
        r"     ╚█████╔╝",
        r"      ╚════╝ "
    ]

    art_welcome = [
        r" ██╗    ██╗███████╗██╗      ██████╗ ██████╗ ███╗   ███╗███████╗",
        r" ██║    ██║██╔════╝██║     ██╔════╝██╔═══██╗████╗ ████║██╔════╝",
        r" ██║ █╗ ██║█████╗  ██║     ██║     ██║   ██║██╔████╔██║█████╗  ",
        r" ██║███╗██║██╔══╝  ██║     ██║     ██║   ██║██║╚██╔╝██║██╔══╝  ",
        r" ╚███╔███╔╝███████╗███████╗╚██████╗╚██████╔╝██║ ╚═╝ ██║███████╗",
        r"  ╚══╝╚══╝ ╚══════╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝"
    ]

    art_to = [
        r" ████████╗ ██████╗ ",
        r" ╚══██╔══╝██╔═══██╗",
        r"    ██║   ██║   ██║",
        r"    ██║   ██║   ██║",
        r"    ██║   ╚██████╔╝",
        r"    ╚═╝    ╚═════╝ "
    ]

    art_inside_cli = [
        r" ██╗███╗   ██╗███████╗██╗██████╗ ███████╗     ██████╗██╗     ██╗",
        r" ██║████╗  ██║██╔════╝██║██╔══██╗██╔════╝    ██╔════╝██║     ██║",
        r" ██║██╔██╗ ██║███████╗██║██║  ██║█████╗      ██║     ██║     ██║",
        r" ██║██║╚██╗██║╚════██║██║██║  ██║██╔══╝      ██║     ██║     ██║",
        r" ██║██║ ╚████║███████║██║██████╔╝███████╗    ╚██████╗███████╗██║",
        r" ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝╚═════╝ ╚══════╝     ╚═════╝╚══════╝╚═╝"
    ]

    # ==========================================
    # ANIMATION HELPERS (Left-Aligned)
    # ==========================================
    def swipe_from_top(art_lines, text_color):
        # 1. Slide down reveal (flush left)
        for frame in range(1, 7):
            for i in range(frame):
                sys.stdout.write(text_color + art_lines[i] + reset + "\033[K\n")
            # Print empty lines for the rest of the 6-line block
            for i in range(6 - frame):
                sys.stdout.write("\033[K\n")
            
            sys.stdout.flush()
            time.sleep(0.03) # Reveal speed
            sys.stdout.write("\033[6A") # Move cursor up 6 lines
            
        # 2. Hold the word on screen
        for i in range(6):
            sys.stdout.write(text_color + art_lines[i] + reset + "\033[K\n")
        sys.stdout.flush()
        time.sleep(0.4) # How long the word stays on screen
        sys.stdout.write("\033[6A")
        
        # 3. Clear the block before the next word
        for i in range(6):
            sys.stdout.write("\033[K\n")
        sys.stdout.write("\033[6A")

    def swipe_from_left(art_lines):
        banner_width = max(len(line) for line in art_lines)
        lines = [line.ljust(banner_width) for line in art_lines]
        
        # We only need to animate for the width of the banner now
        total_frames = banner_width
        
        for frame in range(1, total_frames + 1):
            for line in lines:
                # Slicing from the end makes it look like it's pushing out of the left wall
                visible_text = line[-frame:]
                
                # Apply the 2-color palette safely after string slicing
                rendered_line = ""
                for char in visible_text:
                    if char == '█':
                        rendered_line += face_color + char
                    elif char in shadow_chars:
                        rendered_line += shadow_color + char
                    else:
                        rendered_line += reset + char
                        
                sys.stdout.write(rendered_line + reset + "\033[K\n")
            
            sys.stdout.flush()
            if frame < total_frames:
                sys.stdout.write("\033[6A")
                time.sleep(0.008) # Slide-in speed

    # ==========================================
    # MAIN EXECUTION
    # ==========================================
    sys.stdout.write("\033[?25l\n") # Hide cursor & add padding
    
    try:
        # Phase 1: The Green Sequence
        intro_words = [art_hello, art_amp, art_welcome, art_to]
        for word in intro_words:
            swipe_from_top(word, green)
            
        # Phase 2: The Logo Slide
        swipe_from_left(art_inside_cli)
        
    finally:
        sys.stdout.write("\033[?25h\n") # Restore cursor safely
        sys.stdout.flush()

if __name__ == "__main__":
    animate_left_aligned_sequence()
import time
import sys
import shutil

def animate_terminal_slide():
    ascii_art = r"""
 ██╗███╗   ██╗███████╗██╗██████╗ ███████╗     ██████╗██╗     ██╗
 ██║████╗  ██║██╔════╝██║██╔══██╗██╔════╝    ██╔════╝██║     ██║
 ██║██╔██╗ ██║███████╗██║██║  ██║█████╗      ██║     ██║     ██║
 ██║██║╚██╗██║╚════██║██║██║  ██║██╔══╝      ██║     ██║     ██║
 ██║██║ ╚████║███████║██║██████╔╝███████╗    ╚██████╗███████╗██║
 ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝╚═════╝ ╚══════╝     ╚═════╝╚══════╝╚═╝
    """

    purple = "\033[38;5;218m"
    gold = "\033[38;5;230m"
    # gold = "\033[38;5;238m"
    # purple = "\033[38;5;210m"
    reset = "\033[0m"
    shadow_chars = "╗║═╝╔╚"

    # Clean up the raw string and split into lines
    raw_lines = ascii_art.strip('\n').split('\n')
    num_lines = len(raw_lines)
    
    # Find the max width of the banner and pad all lines evenly
    banner_width = max(len(line) for line in raw_lines)
    lines = [line.ljust(banner_width) for line in raw_lines]

    # Dynamically get the user's terminal width
    term_width = shutil.get_terminal_size().columns
    
    # Calculate how far right we need to slide to perfectly center the banner
    target_indent = max(0, (term_width - banner_width) // 2)

    # Total frames = Sliding out from the wall + Sliding to the center
    total_frames = banner_width + target_indent

    # Hide cursor to prevent flickering
    sys.stdout.write("\033[?25l\n")
    
    try:
        for frame in range(1, total_frames + 1):
            for line in lines:
                # Calculate the visible text for the current frame
                if frame <= banner_width:
                    # Slicing the string to make it slide out from the left edge
                    visible_text = line[-frame:]
                else:
                    # Banner is fully revealed, now add spaces to push it to the center
                    indent_spaces = frame - banner_width
                    visible_text = (" " * indent_spaces) + line
                
                # Apply colors AFTER slicing so we don't accidentally cut ANSI codes in half
                rendered_line = ""
                for char in visible_text:
                    if char == '█':
                        rendered_line += gold + char
                    elif char in shadow_chars:
                        rendered_line += purple + char
                    else:
                        rendered_line += reset + char
                        
                # Print the line and clear to the end of the line (\033[K) to prevent ghosting
                sys.stdout.write(rendered_line + reset + "\033[K\n")
            
            sys.stdout.flush()
            
            # If not the last frame, move cursor back up to draw the next frame
            if frame < total_frames:
                sys.stdout.write(f"\033[{num_lines}A")
                time.sleep(0.01) # Speed of the slide (0.01 is a smooth, fast glide)
                
    finally:
        # Restore the cursor!
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()
        
# def animate_neon_power_up():
#     ascii_art = r"""
#  ██╗███╗   ██╗███████╗██╗██████╗ ███████╗     ██████╗██╗     ██╗
#  ██║████╗  ██║██╔════╝██║██╔══██╗██╔════╝    ██╔════╝██║     ██║
#  ██║██╔██╗ ██║███████╗██║██║  ██║█████╗      ██║     ██║     ██║
#  ██║██║╚██╗██║╚════██║██║██║  ██║██╔══╝      ██║     ██║     ██║
#  ██║██║ ╚████║███████║██║██████╔╝███████╗    ╚██████╗███████╗██║
#  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝╚═════╝ ╚══════╝     ╚═════╝╚══════╝╚═╝
#     """

#     shadow_chars = "╗║═╝╔╚"
#     reset = "\033[0m"

#     # Define the color gradient frames from "off" to "fully ignited"
#     # Each tuple is (Face Color, Shadow Color)
#     animation_frames = [
#         ("\033[38;5;235m", "\033[38;5;235m"),   # Frame 1: Very dark gray (Almost off)
#         ("\033[38;5;238m", "\033[38;5;237m"),   # Frame 2: Dark gray (Warming up)
#         ("\033[38;5;58m",  "\033[38;5;17m"),    # Frame 3: Dim brown/gold & Dark midnight blue
#         ("\033[38;5;136m", "\033[38;5;54m"),    # Frame 4: Medium gold & Dim purple
#         ("\033[38;5;178m", "\033[38;5;55m"),    # Frame 5: Brighter yellow & Medium purple
#         ("\033[1m\033[38;5;220m", "\033[1m\033[38;5;57m") # Frame 6: FULL POWER (Bold Royal Gold & Purple)
#     ]

#     # Clean up the raw string and calculate lines for cursor math
#     lines = ascii_art.strip('\n').split('\n')
#     num_lines = len(lines)

#     # Hide the terminal cursor for a clean animation
#     sys.stdout.write("\033[?25l\n")
    
#     try:
#         # Loop through each color gradient frame
#         for i, (gold_grad, purple_grad) in enumerate(animation_frames):
#             for line in lines:
#                 rendered_line = ""
#                 for char in line:
#                     if char == '█':
#                         rendered_line += gold_grad + char
#                     elif char in shadow_chars:
#                         rendered_line += purple_grad + char
#                     else:
#                         rendered_line += reset + char
#                 sys.stdout.write(rendered_line + reset + "\n")
            
#             sys.stdout.flush()
            
#             # If it's not the final frame, pause and move the cursor back up to overwrite
#             if i < len(animation_frames) - 1:
#                 time.sleep(0.12) # Delay between brightness levels (adjust for speed)
#                 sys.stdout.write(f"\033[{num_lines}A")
                
#     finally:
#         # ALWAYS ensure the cursor is restored, even if the user hits Ctrl+C mid-animation
#         sys.stdout.write("\033[?25h\n")
#         sys.stdout.flush()


# import time
# import sys
# import shutil

# def animate_terminal_slide11():
#     ascii_art = r"""
#  █████                     ███      █████                    █████████  █████       █████   
# ░░███                     ░░░      ░░███                    ███░░░░░███░░███       ░░███                    
#  ░███  ████████    █████  ████   ███████   ██████          ███     ░░░  ░███        ░███    
#  ░███ ░░███░░███  ███░░  ░░███  ███░░███  ███░░███        ░███          ░███        ░███  
#  ░███  ░███ ░███ ░░█████  ░███ ░███ ░███ ░███████         ░███          ░███        ░███    
#  ░███  ░███ ░███  ░░░░███ ░███ ░███ ░███ ░███░░░          ░░███     ███ ░███      █ ░███ 
#  █████ ████ █████ ██████  █████░░████████░░██████          ░░█████████  ███████████ █████  
# ░░░░░ ░░░░ ░░░░░ ░░░░░░  ░░░░░  ░░░░░░░░  ░░░░░░            ░░░░░░░░░  ░░░░░░░░░░░ ░░░░░  
#     """

#     gold = "\033[38;5;220m"
#     purple = "\033[38;5;160m"
#     reset = "\033[0m"
#     shadow_chars = "░"

#     # Clean up the raw string and split into lines
#     raw_lines = ascii_art.strip('\n').split('\n')
#     num_lines = len(raw_lines)
    
#     # Find the max width of the banner and pad all lines evenly
#     banner_width = max(len(line) for line in raw_lines)
#     lines = [line.ljust(banner_width) for line in raw_lines]

#     # Dynamically get the user's terminal width
#     term_width = shutil.get_terminal_size().columns
    
#     # Calculate how far right we need to slide to perfectly center the banner
#     target_indent = max(0, (term_width - banner_width) // 2)

#     # Total frames = Sliding out from the wall + Sliding to the center
#     total_frames = banner_width + target_indent

#     # Hide cursor to prevent flickering
#     sys.stdout.write("\033[?25l\n")
    
#     try:
#         for frame in range(1, total_frames + 1):
#             for line in lines:
#                 # Calculate the visible text for the current frame
#                 if frame <= banner_width:
#                     # Slicing the string to make it slide out from the left edge
#                     visible_text = line[-frame:]
#                 else:
#                     # Banner is fully revealed, now add spaces to push it to the center
#                     indent_spaces = frame - banner_width
#                     visible_text = (" " * indent_spaces) + line
                
#                 # Apply colors AFTER slicing so we don't accidentally cut ANSI codes in half
#                 rendered_line = ""
#                 for char in visible_text:
#                     if char == '█':
#                         rendered_line += gold + char
#                     elif char in shadow_chars:
#                         rendered_line += purple + char
#                     else:
#                         rendered_line += reset + char
                        
#                 # Print the line and clear to the end of the line (\033[K) to prevent ghosting
#                 sys.stdout.write(rendered_line + reset + "\033[K\n")
            
#             sys.stdout.flush()
            
#             # If not the last frame, move cursor back up to draw the next frame
#             if frame < total_frames:
#                 sys.stdout.write(f"\033[{num_lines}A")
#                 time.sleep(0.01) # Speed of the slide (0.01 is a smooth, fast glide)
                
#     finally:
#         # Restore the cursor!
#         sys.stdout.write("\033[?25h\n")
#         sys.stdout.flush()



if __name__ == "__main__":
    animate_terminal_slide()
    animate_neon_power_up()
    animate_terminal_slide11()
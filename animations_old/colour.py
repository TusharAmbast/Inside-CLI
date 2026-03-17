import sys

# Your original pairs
COLOR_PAIRS = [
    ("\033[38;5;218m", "\033[38;5;230m"),
    ("\033[38;5;238m", "\033[38;5;210m"),
    ("\033[38;5;117m", "\033[38;5;24m"),
    ("\033[38;5;155m", "\033[38;5;22m"),
    ("\033[38;5;208m", "\033[38;5;52m"),
    ("\033[38;5;141m", "\033[38;5;54m"),
    ("\033[38;5;200m", "\033[38;5;89m"),
    ("\033[38;5;51m",  "\033[38;5;23m"),
    ("\033[38;5;226m", "\033[38;5;94m"),
    ("\033[38;5;220m" ,"\033[38;5;160m")
]

char_i = [" ██╗", " ██║", " ██║", " ██║", " ██║", " ╚═╝"]
RESET = "\033[0m"

def print_side_by_side():
    # Optional: Print headers side-by-side to align with the blocks
    for i in range(len(COLOR_PAIRS)):
        # Format " V1   ", " V2   ", etc., to match the width
        sys.stdout.write(f"V{i + 1:<4} ")
    sys.stdout.write("\n")

    # Outer loop: Iterate through each line (row) of the ASCII character
    for line in char_i:
        
        # Inner loop: For this specific row, draw it in every color pair
        for text_color, shadow_color in COLOR_PAIRS:
            styled = ""
            for char in line:
                # If the character is a line/corner, use shadow color
                if char in "═╝║╗╔╚":
                    styled += f"{shadow_color}{char}{text_color}"
                else:
                    # Otherwise, it stays in the default text_color (for the █ blocks)
                    styled += char
            
            # Write the styled line, keeping it on the same console line, plus spacing
            sys.stdout.write(f"{text_color}{styled}{RESET}  ")
            
        
        for shadow_color, text_color in COLOR_PAIRS:
            styled = ""
            for char in line:
                # If the character is a line/corner, use shadow color
                if char in "═╝║╗╔╚":
                    styled += f"{shadow_color}{char}{text_color}"
                else:
                    # Otherwise, it stays in the default text_color (for the █ blocks)
                    styled += char
            
            # Write the styled line, keeping it on the same console line, plus spacing
            sys.stdout.write(f"{text_color}{styled}{RESET}  ")
            
        # After printing the current row for all color variants, drop down to the next line
        sys.stdout.write("\n")
    sys.stdout.write("\n")

if __name__ == "__main__":
    print_side_by_side()
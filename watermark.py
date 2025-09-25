WATERMARK = "code with bhuro"

def print_watermark():
    text = f"🚀 {WATERMARK} 🚀"
    tagline = "🔎 Search on YouTube: @code_with_bhuro"

    # Function to calculate display width (emojis count as 2 characters)
    def display_width(s):
        width = 0
        for char in s:
            # Check if character is wide (emojis, CJK characters, etc.)
            if ord(char) > 127 or char in '🚀🔎':
                width += 2
            else:
                width += 1
        return width

    # Calculate the width needed for proper centering
    text_width = display_width(text)
    tagline_width = display_width(tagline)
    max_width = max(text_width, tagline_width)
    box_width = max_width + 4  # Add padding for the box borders

    # Create the box components
    top = "╔" + "═" * box_width + "╗"
    mid = "║" + text.center(box_width) + "║"
    sep = "╠" + "═" * box_width + "╣"
    info = "║" + tagline.center(box_width) + "║"
    bot = "╚" + "═" * box_width + "╝"

    print("\n".join([top, mid, sep, info, bot]))


if __name__ == "__main__":
    print_watermark()
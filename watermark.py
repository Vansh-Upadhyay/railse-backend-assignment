WATERMARK = "code with bhuro"

def print_watermark():
    text = f"🚀 {WATERMARK} 🚀"
    tagline = "🔎 Search on YouTube: @code_with_bhuro"

    # Calculate the width needed for proper centering
    # Use the longer line as base and add some padding
    max_text_length = max(len(text), len(tagline))
    width = max_text_length + 20  # Extra padding for better visual balance

    top  = "╔" + "═" * width + "╗"
    mid  = "║" + text.center(width) + "║"
    sep  = "╠" + "═" * width + "╣"
    info = "║" + tagline.center(width) + "║"
    bot  = "╚" + "═" * width + "╝"

    print("\n".join([top, mid, sep, info, bot]))


if __name__ == "__main__":
    print_watermark()
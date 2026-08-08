"""
Generate icon.png from the SVG logo for the system tray.
Run this once: python generate_icon.py
"""
from PIL import Image, ImageDraw

def create_icon():
    """Create a 256x256 icon with the PrintBridge brand color."""
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Blue circle background (#3056D3)
    padding = 10
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=(48, 86, 211, 255)
    )

    # White printer icon (simplified)
    cx, cy = size // 2, size // 2

    # Printer body
    draw.rounded_rectangle(
        [cx - 50, cy - 20, cx + 50, cy + 30],
        radius=8,
        fill=(255, 255, 255, 255)
    )

    # Paper coming out top
    draw.rectangle(
        [cx - 30, cy - 55, cx + 30, cy - 15],
        fill=(255, 255, 255, 255)
    )

    # Paper tray bottom
    draw.rounded_rectangle(
        [cx - 35, cy + 15, cx + 35, cy + 50],
        radius=6,
        fill=(255, 255, 255, 255)
    )

    # Lines on paper
    for i in range(3):
        y = cy - 48 + i * 12
        draw.line(
            [cx - 20, y, cx + 20, y],
            fill=(48, 86, 211, 200),
            width=2
        )

    # Save multiple sizes
    img.save('icon.png')
    print('Created icon.png (256x256)')

    # Create .ico for Windows (multi-size)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [img.resize(s, Image.LANCZOS) for s in sizes]
    icons[0].save('icon.ico', format='ICO', sizes=sizes, append_images=icons[1:])
    print('Created icon.ico (multi-size)')

    # Create .icns for macOS (just use the 256px PNG — pyinstaller handles conversion)
    img.save('icon_macos.png')
    print('Created icon_macos.png for macOS packaging')


if __name__ == '__main__':
    create_icon()

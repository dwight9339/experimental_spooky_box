import board

# Rotate the built-in display so boot/status text is inverted
if hasattr(board, "DISPLAY"):
    board.DISPLAY.rotation = 180  # options: 0, 90, 180, 270
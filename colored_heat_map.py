import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.colors import ListedColormap, BoundaryNorm
# -----------------------
# Configuration
# -----------------------
INPUT_FILE = "errors/Logged_errors.txt"

# SRAM size of Arduino Mega (ATmega2560)
SRAM_START = 0x100
SRAM_END   = 0x21FF

GRID_WIDTH = 64      # bytes per row

# Priority (higher wins)
priority = {
    "1": 1,
    "RESET": 2,
    "UNKNOWN": 3,
    "HANG": 4
}

# Color indices
color_index = {
    0: "white",      # no data
    1: "green",
    2: "yellow",
    3: "orange",
    4: "red"
}

# -----------------------
# Parse file
# -----------------------

byte_state = {}

pattern = re.compile(
    r"FLIP\s*@\s*0x([0-9A-Fa-f]+)\s*bit\s*\d+\s*-\s*(.+)"
)

with open(INPUT_FILE) as f:
    for line in f:
        m = pattern.match(line.strip())
        if not m:
            continue

        address = int(m.group(1), 16)
        result = m.group(2).strip().upper()

        if result == "1":
            state = 1
        elif result == "RESET":
            state = 2
        elif result == "UNKNOWN":
            state = 3
        elif result == "HANG":
            state = 4
        else:
            continue

        if address not in byte_state:
            byte_state[address] = state
        else:
            byte_state[address] = max(byte_state[address], state)

# -----------------------
# Build grid
# -----------------------

num_bytes = SRAM_END - SRAM_START + 1
height = (num_bytes + GRID_WIDTH - 1) // GRID_WIDTH

grid = np.zeros((height, GRID_WIDTH), dtype=int)

for addr, state in byte_state.items():
    if SRAM_START <= addr <= SRAM_END:
        index = addr - SRAM_START
        row = index // GRID_WIDTH
        col = index % GRID_WIDTH
        grid[row, col] = state

# -----------------------
# Plot
# -----------------------

# Define the colors for each state
cmap = ListedColormap([
    "white",   # 0 = No data
    "green",   # 1
    "yellow",  # RESET
    "orange",  # UNKNOWN
    "red"      # HANG
])

# Tell matplotlib these are discrete categories
norm = BoundaryNorm(
    [-0.5, 0.5, 1.5, 2.5, 3.5, 4.5],
    cmap.N
)

fig, ax = plt.subplots(figsize=(12, 20))

img = ax.imshow(
    grid,
    cmap=cmap,
    norm=norm,
    interpolation="nearest",
    origin="upper",
    aspect="equal"
)

ax.set_title("Arduino Mega SRAM Heat Map")
ax.set_xlabel("Byte Offset")
ax.set_ylabel("SRAM Address")

# X-axis ticks every 10 columns, plus the last column
x_ticks = list(range(0, GRID_WIDTH, 10))
if x_ticks[-1] != GRID_WIDTH - 1:
    x_ticks.append(GRID_WIDTH - 1)

ax.set_xticks(x_ticks)
ax.set_xticklabels(x_ticks)

# Y-axis ticks every 15 rows, plus the last row
y_ticks = list(range(0, height, 15))
if y_ticks[-1] != height - 1:
    y_ticks.append(height - 1)

y_labels = [hex(SRAM_START + row * GRID_WIDTH) for row in y_ticks]

ax.set_yticks(y_ticks)
ax.set_yticklabels(y_labels, fontsize=8)


# Add a color bar
cbar = fig.colorbar(img, ax=ax, ticks=[0, 1, 2, 3, 4])

cbar.ax.set_yticklabels([
    "No Data",
    "1",
    "RESET",
    "UNKNOWN",
    "HANG"
])

cbar.set_label("Result")

plt.tight_layout()
plt.show()
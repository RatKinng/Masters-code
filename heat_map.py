import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

def parse_file(filename):
    data = []
    addresses = []

    with open(filename, 'r') as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) != 2:
                continue

            addr_str = parts[0].strip()
            groups = parts[1].strip().split()

            row = []
            for group in groups:
                # Break each 8-character group into individual characters
                for ch in group:
                    try:
                        row.append(int(ch))
                    except ValueError:
                        row.append(-1)  # unknown byte

            data.append(row)
            addresses.append(int(addr_str))  # store address

    return np.array(data), addresses

def create_colormap():
    colors = [
        'gray',   # -1 (we'll shift indices later)
        'blue',  # 0
        'green',   # 1
        'yellow',  # 2
        'orange', # 3
        'red', # 4
        'black'     # 5
    ]

    return ListedColormap(colors)

def plot_pixel_map(data, addresses):
    shifted = data + 1
    cmap = create_colormap()

    rows, cols = data.shape

    plt.figure(figsize=(cols * 0.4, rows * 0.4), dpi=150)

    plt.imshow(shifted, cmap=cmap, vmin=0, vmax=6, interpolation='nearest')

    # --- Y-axis labeling ---
    tick_positions = []
    tick_labels = []

    for i in range(rows):
        if i == 0 or i == rows - 1 or i % 10 == 0:
            tick_positions.append(i)
            tick_labels.append(str(addresses[i]))

    plt.yticks(tick_positions, tick_labels)

    plt.xticks([])  # keep x clean
    plt.xlabel('Byte Index')
    plt.ylabel('Memory Address')

    plt.title('Memory Pixel Map')
    legend_elements = [
        Patch(facecolor='gray', label='Untested'),
        Patch(facecolor='black', label='Lock up'),
        Patch(facecolor='blue', label='No Effect'),
        Patch(facecolor='green', label='Minor Effect'),
        Patch(facecolor='yellow', label='Reset'),
        Patch(facecolor='orange', label='Unknown'),
        Patch(facecolor='red', label='Altered Execution')
    ]

    plt.legend(
        handles=legend_elements,
        loc='upper right',
        bbox_to_anchor=(1.15, 1),  # pushes legend outside plot
        borderaxespad=0.
    )
    plt.show()

if __name__ == "__main__":
    filename = "vis_output7.txt"
    data, addresses = parse_file(filename)
    plot_pixel_map(data, addresses)
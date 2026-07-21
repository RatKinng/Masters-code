import re

INPUT_FILE = "errors/Logged_errors.txt"
OUTPUT_FILE = "results_sorted.txt"

# Match lines like:
# FLIP @ 0x329 bit 6 - RESET
pattern = re.compile(
    r"FLIP\s*@\s*0x([0-9A-Fa-f]+)\s*bit\s*(\d+)\s*-\s*(.+)"
)

entries = []

with open(INPUT_FILE, "r") as f:
    for line in f:
        line = line.rstrip("\n")
        m = pattern.match(line)

        if m:
            address = int(m.group(1), 16)
            bit = int(m.group(2))

            # Store address, bit, and original line
            entries.append((address, bit, line))
        else:
            # Keep unrecognized lines at the end
            entries.append((float("inf"), float("inf"), line))

# Sort by address, then bit
entries.sort(key=lambda x: (x[0], x[1]))

# Write sorted file
with open(OUTPUT_FILE, "w") as f:
    for _, _, line in entries:
        f.write(line + "\n")

print(f"Sorted {len(entries)} lines.")
print(f"Output written to '{OUTPUT_FILE}'")
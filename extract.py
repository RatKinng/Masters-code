import sys
import re
import os

# Arduino Uno SRAM size
RAM_SIZE = 2048  # bytes
BYTES_PER_LINE = 4

def extract_flips(input_file, output_file):
    pattern = re.compile(r'Flipping address (\d+), bit (\d+)')

    address_bits = {}

    with open(input_file, 'r') as infile:
        for line in infile:
            for match in pattern.finditer(line):
                address = int(match.group(1))
                bit = int(match.group(2))

                if address not in address_bits:
                    address_bits[address] = set()

                address_bits[address].add(bit)

    # Convert to flip list for visualization
    flips = []
    for address, bits in address_bits.items():
        for bit in bits:
            flips.append((address, bit))

    # Write cleaned output file
    with open(output_file, 'w') as outfile:
        for address in sorted(address_bits):
            bits = sorted(address_bits[address])
            bit_list = ", ".join(str(b) for b in bits)
            outfile.write(f"Flipping address {address}, bits [{bit_list}]\n")

    return flips

import re

def extract_tagged_flips(input_file):
    pattern = re.compile(r'Flipping address (\d+), bits \[(.*?)\]\s*-\s*(N/A|String|Reboot)')

    address_bits = {}
    address_tags = {}

    with open(input_file, 'r') as infile:
        for line in infile:
            match = pattern.search(line)

            if match:
                address = int(match.group(1))
                bits = [int(b.strip()) for b in match.group(2).split(",")]
                tag = match.group(3)

                address_bits[address] = bits
                address_tags[address] = tag

    return address_bits, address_tags

def create_ram_visualization(data, output_file, append=False, tags=None):
    """
    Unified RAM visualization.

    Parameters:
        data: 
            - list of (address, bit) tuples for raw flips
            - OR dict {address: [bits]} for tagged flips
        tags: dict {address: tag} for tagged flips (optional)
        output_file: path to write visualization
        append: whether to append to file
    """
    ram = [['X'] * 8 for _ in range(RAM_SIZE)]

    tag_values = {
        "N/A": '0',
        "String": '1',
        "Reboot": '2'
    }

    if isinstance(data, list):
        # RAW MODE: list of (address, bit) tuples
        for address, bit in data:
            if 0 <= address < RAM_SIZE and 0 <= bit < 8:
                ram[address][7 - bit] = 'O'
    elif isinstance(data, dict):
        # TAGGED MODE: dict {address: [bits]}, optional tags dict
        for address, bits in data.items():
            if tags and address in tags:
                tag = tags[address]
                if tag in tag_values:
                    ram[address] = [tag_values[tag]] * 8
                    continue
            # otherwise mark flipped bits normally
            for bit in bits:
                if 0 <= bit < 8:
                    ram[address][7 - bit] = 'O'
    else:
        raise ValueError("Invalid data type for visualization")

    mode = 'a' if append else 'w'
    with open(output_file, mode) as f:
        if append:
            f.write("\n" + "="*40 + "\n")
        for i in range(0, RAM_SIZE, BYTES_PER_LINE):
            f.write(f"{i:04d}: ")
            for j in range(BYTES_PER_LINE):
                if i + j < RAM_SIZE:
                    f.write("".join(ram[i + j]))
                    if j < BYTES_PER_LINE - 1:
                        f.write(" ")
            f.write("\n")

    print(f"RAM visualization written to {output_file}")

if __name__ == "__main__":
    tagged_mode = '--tagged' in sys.argv
    append = '--update' in sys.argv

    if tagged_mode:

        if len(sys.argv) < 3:
            print("Usage (tagged): python script.py <tagged_flips> <ram_visual_output> --tagged")
            sys.exit(1)

        input_path = sys.argv[1]
        ram_visual_path = sys.argv[2]

        address_bits, address_tags = extract_tagged_flips(input_path)
        create_ram_visualization(address_bits, ram_visual_path, tags=address_tags)

    else:

        if len(sys.argv) < 4:
            print("Usage (raw): python script.py <input_log> <filtered_output> <ram_visual_output> [--update]")
            sys.exit(1)

        input_path = sys.argv[1]
        filtered_path = sys.argv[2]
        ram_visual_path = sys.argv[3]

        flips = extract_flips(input_path, filtered_path)
        create_ram_visualization(flips, ram_visual_path, append=append)
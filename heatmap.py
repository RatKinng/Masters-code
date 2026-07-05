import argparse
import csv
import os
import re

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

# ---------------------------------------------------------------------
# ATmega2560 SRAM
# ---------------------------------------------------------------------

SRAM_START = 0x0100
SRAM_END = 0x21FF
WIDTH = 64  # bytes per row in the heatmap

# ---------------------------------------------------------------------
# Regular Expressions
# ---------------------------------------------------------------------

DATA_PATTERN = re.compile(
    r"^\[.*?\] Uptime:\s*\d+\s*\|\s*Analog:\s*\d+\s*\|"
)

FLIP_PATTERN = re.compile(
    r"^\[.*?\] FLIP\s*@\s*(0x[0-9A-Fa-f]+)\s*bit\s*(\d+)"
)

TARGET_PATTERN = re.compile(
    r"^\[.*?\] New target address:\s*0x[0-9A-Fa-f]+"
)

CMD_PATTERN = re.compile(
    r"^\[.*?\] CMD -> .+"
)

SWITCH_PATTERN = re.compile(
    r"^\[.*?\] SWITCHED TO ADDRESS .+"
)

REBOOT_PATTERN = re.compile(
    r"^\[.*?\] (Software restart requested\.\.\.|REBOOT.*|Reset Cause:.*|MPU6050 Found!|Commands:|restart|0x[0-9A-Fa-f]+|\d+)"
)

HEADER_PATTERN = re.compile(
    r"^\[.*?\] (={5,}|FAULT INJECTION EXPERIMENT START|LOG FILE:.*|SERIAL PORT:.*|BAUD RATE:.*|START ADDRESS:.*|END ADDRESS:.*|STEP SIZE:.*|INTERVAL SECONDS:.*|HANG TIMEOUT:.*)"
)

# ---------------------------------------------------------------------


def parse_log(filename):
    flipped = set()

    telemetry_lines = 0
    flip_events = 0

    data_since_flip = 0

    unknown_lines = []
    warnings = []

    with open(filename, "r") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip()

            # ---------------- Telemetry ----------------
            if DATA_PATTERN.match(line):
                telemetry_lines += 1
                data_since_flip += 1
                continue

            # ---------------- Flip ----------------
            m = FLIP_PATTERN.match(line)
            if m:
                flip_events += 1

                addr = int(m.group(1), 16)

                if SRAM_START <= addr <= SRAM_END:
                    flipped.add(addr)
                else:
                    warnings.append(
                        f"Line {lineno}: SRAM address {hex(addr)} outside valid range."
                    )

                if data_since_flip not in (3, 4):
                    warnings.append(
                        f"Line {lineno}: FLIP occurred after "
                        f"{data_since_flip} telemetry lines "
                        f"(expected 3-4)."
                    )

                data_since_flip = 0
                continue

            # ---------------- Other recognized lines ----------------
            if (
                TARGET_PATTERN.match(line)
                or CMD_PATTERN.match(line)
                or SWITCH_PATTERN.match(line)
                or REBOOT_PATTERN.match(line)
                or HEADER_PATTERN.match(line)
            ):
                continue

            # ---------------- Unknown ----------------
            unknown_lines.append((lineno, line))

    return (
        flipped,
        telemetry_lines,
        flip_events,
        unknown_lines,
        warnings,
    )


def build_heatmap(flipped):
    num_bytes = SRAM_END - SRAM_START + 1
    height = (num_bytes + WIDTH - 1) // WIDTH

    heat = np.zeros((height, WIDTH), dtype=np.uint8)

    for addr in flipped:
        index = addr - SRAM_START
        row = index // WIDTH
        col = index % WIDTH
        heat[row, col] = 1

    return heat


def save_heatmap(heat, outfile, affected):
    cmap = ListedColormap(["white", "red"])

    plt.figure(figsize=(12, 16))
    plt.imshow(
        heat,
        cmap=cmap,
        interpolation="nearest",
        aspect="equal",
    )

    plt.title(
        f"Arduino Mega SRAM Bit Flip Map\n"
        f"{affected} of {SRAM_END - SRAM_START + 1} bytes affected"
    )

    plt.xlabel("Byte Offset (64 bytes per row)")
    plt.ylabel("SRAM Rows")

    plt.xticks(np.arange(0, WIDTH, 8))
    plt.grid(color="lightgray", linewidth=0.25)

    plt.tight_layout()
    plt.savefig(outfile, dpi=300)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate an SRAM bit-flip heatmap."
    )
    parser.add_argument("logfile", help="Arduino experiment log")
    args = parser.parse_args()

    (
        flipped,
        telemetry_lines,
        flip_events,
        unknown_lines,
        warnings,
    ) = parse_log(args.logfile)

    heat = build_heatmap(flipped)

    os.makedirs("results", exist_ok=True)
    os.makedirs("errors", exist_ok=True)
    os.makedirs("summary", exist_ok=True)

    basename = os.path.splitext(os.path.basename(args.logfile))[0]

    outfile = os.path.join(
        "results",
        f"{basename}_heatmap.png",
    )

    errorfile = os.path.join(
        "errors",
        f"{basename}_errors.txt",
    )

    all_error_file = os.path.join(
        "errors",
        "all_errors.txt",
    )

    summary_file = os.path.join(
        "summary",
        "all_results.csv",
    )

    save_heatmap(heat, outfile, len(flipped))

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------

    summary = []
    summary.append("========== Summary ==========")
    summary.append(f"Telemetry lines : {telemetry_lines}")
    summary.append(f"Flip events     : {flip_events}")
    summary.append(f"Affected bytes  : {len(flipped)}")
    summary.append(f"Warnings        : {len(warnings)}")
    summary.append(f"Unknown lines   : {len(unknown_lines)}")
    summary.append(f"Heatmap saved   : {outfile}")

    for line in summary:
        print(line)

        # -----------------------------------------------------------------
        # Save individual error report
        # -----------------------------------------------------------------

        with open(errorfile, "w") as ef:

            ef.write("\n".join(summary))
            ef.write("\n\n")

            if warnings:
                ef.write("========== Warnings ==========\n")
                for warning in warnings:
                    ef.write(warning + "\n")
                    print(warning)
            else:
                ef.write("No warnings.\n")

            ef.write("\n")

            if unknown_lines:
                ef.write("====== Unrecognized Lines ======\n")
                for lineno, line in unknown_lines:
                    ef.write(f"Line {lineno}: {line}\n")
                    print(f"Line {lineno}: {line}")
            else:
                ef.write("No unrecognized log lines.\n")

        print(f"\nIndividual error report saved to: {errorfile}")

        # -----------------------------------------------------------------
        # Append to master error report
        # -----------------------------------------------------------------

        with open(all_error_file, "a") as ef:

            ef.write("=" * 80 + "\n")
            ef.write(f"Log File: {os.path.basename(args.logfile)}\n")
            ef.write("=" * 80 + "\n")

            ef.write("\n".join(summary))
            ef.write("\n\n")

            if warnings:
                ef.write("Warnings\n")
                for warning in warnings:
                    ef.write(warning + "\n")

            if unknown_lines:
                ef.write("\nUnknown Lines\n")
                for lineno, line in unknown_lines:
                    ef.write(f"Line {lineno}: {line}\n")

            ef.write("\n\n")

        print(f"Master error report updated: {all_error_file}")

        # -----------------------------------------------------------------
        # Append experiment summary to CSV
        # -----------------------------------------------------------------

        csv_exists = os.path.exists(summary_file)

        with open(summary_file, "a", newline="") as csvfile:

            writer = csv.writer(csvfile)

            if not csv_exists:
                writer.writerow([
                    "Log File",
                    "Telemetry Lines",
                    "Flip Events",
                    "Affected Bytes",
                    "Warnings",
                    "Unknown Lines"
                ])

            writer.writerow([
                os.path.basename(args.logfile),
                telemetry_lines,
                flip_events,
                len(flipped),
                len(warnings),
                len(unknown_lines)
            ])

        print(f"Summary CSV updated: {summary_file}")


if __name__ == "__main__":
    main()
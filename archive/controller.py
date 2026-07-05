import serial
import time
from datetime import datetime

# =========================
# CONFIG
# =========================

SERIAL_PORT = "COM5"      # change this (Linux: /dev/ttyACM0)
BAUD_RATE = 115200

START_ADDRESS = 0x0100
STEP_SIZE = 100
INTERVAL_SECONDS = 60

LOG_FILE = "arduino_log.txt"

# =========================
# SETUP
# =========================

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)  # allow Arduino reset

current_address = START_ADDRESS

print("Connected to Arduino on", SERIAL_PORT)

# =========================
# LOG FUNCTION
# =========================

def log_line(line: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {line}"

    print(formatted)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

# =========================
# SEND COMMAND
# =========================

def send_command(cmd: str):
    ser.write((cmd + "\n").encode("utf-8"))
    log_line(f"CMD -> {cmd}")

# =========================
# MAIN LOOP
# =========================

last_switch_time = time.time()

send_command(hex(current_address))

while True:
    # ---------------------------------
    # 1. Read Arduino output continuously
    # ---------------------------------
    if ser.in_waiting:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                log_line(line)
        except Exception as e:
            log_line(f"READ ERROR: {e}")

    # ---------------------------------
    # 2. Check timer
    # ---------------------------------
    now = time.time()

    if now - last_switch_time >= INTERVAL_SECONDS:
        # Step address
        current_address += STEP_SIZE

        # Optional wrap safety (Arduino SRAM range)
        if current_address > 0x21FF:
            current_address = 0x0100

        # Send restart first
        send_command("restart")

        # small delay to let reboot begin
        time.sleep(2)

        # Send new address
        send_command(hex(current_address))

        log_line(f"SWITCHED TO ADDRESS 0x{current_address:X}")

        last_switch_time = now

    time.sleep(0.01)
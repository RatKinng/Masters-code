import os
import time
import serial
from datetime import datetime

# CONFIGURATION

SERIAL_PORT = "COM5"
BAUD_RATE = 115200

START_ADDRESS = 0x0100
END_ADDRESS = 0x21FF

STEP_SIZE = 20
INTERVAL_SECONDS = 60
# How long without serial output before declaring a hang
HANG_TIMEOUT_SECONDS = 5

# LOGGING SETUP

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

LOG_FILE = os.path.join(
    LOG_DIR,
    f"fault_injection_{timestamp}.txt"
)

# GLOBALS

current_address = START_ADDRESS
last_data_time = time.time()

# LOGGING

def log_line(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"

    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as logfile:
        logfile.write(line + "\n")

# SERIAL CONNECTION
def connect_serial():
    ser = serial.Serial(
        SERIAL_PORT,
        BAUD_RATE,
        timeout=1
    )

    # Allow Arduino to boot
    time.sleep(2)
    ser.reset_input_buffer()

    return ser

# RESET ARDUINO
def reset_arduino():
    global ser
    log_line("ARDUINO RESET VIA DTR")

    try:
        ser.setDTR(False)
        time.sleep(0.2)
        ser.setDTR(True)
        time.sleep(2)
    except Exception as e:
        log_line(f"DTR RESET ERROR: {e}")
    try:
        ser.close()
    except Exception:
        pass

    ser = connect_serial()

# COMMANDS
def send_command(command):
    ser.write((command + "\n").encode("utf-8"))
    log_line(f"CMD -> {command}")

def send_address(address):
    send_command(hex(address))

# HANG DETECTION
def check_for_hang():
    global last_data_time
    global current_address

    elapsed = time.time() - last_data_time

    if elapsed > HANG_TIMEOUT_SECONDS:

        log_line("ERROR: HANG")

        log_line(
            f"HANG DETECTED AT ADDRESS "
            f"0x{current_address:04X}"
        )

        reset_arduino()

        advance_address()

        time.sleep(2)

        send_address(current_address)

        log_line(
            f"ADVANCING TO ADDRESS "
            f"0x{current_address:04X}"
        )

        last_data_time = time.time()

        return True

    return False

# ADDRESS CYCLING
def advance_address():
    global current_address
    current_address += STEP_SIZE
    if current_address > END_ADDRESS:
        current_address = START_ADDRESS

def perform_cycle():
    global current_address
    send_command("restart")
    # Allow reboot
    time.sleep(2)
    advance_address()
    send_address(current_address)
    log_line(
        f"SWITCHED TO ADDRESS 0x{current_address:04X}"
    )

# STARTUP
ser = connect_serial()
log_line("================================================")
log_line("FAULT INJECTION EXPERIMENT START")
log_line("================================================")
log_line(f"LOG FILE: {LOG_FILE}")
log_line(f"SERIAL PORT: {SERIAL_PORT}")
log_line(f"BAUD RATE: {BAUD_RATE}")
log_line(f"START ADDRESS: 0x{START_ADDRESS:04X}")
log_line(f"END ADDRESS: 0x{END_ADDRESS:04X}")
log_line(f"STEP SIZE: {STEP_SIZE}")
log_line(f"INTERVAL SECONDS: {INTERVAL_SECONDS}")
log_line(f"HANG TIMEOUT: {HANG_TIMEOUT_SECONDS}")
log_line("================================================")

# Send first address
send_address(current_address)
cycle_start_time = time.time()

# MAIN LOOP
while True:
    # Read Arduino Output
    if ser.in_waiting:
        try:
            line = (
                ser.readline()
                .decode("utf-8", errors="ignore")
                .strip()
            )

            if line:
                log_line(line)
                last_data_time = time.time()

        except Exception as e:
            log_line(f"SERIAL READ ERROR: {e}")

    hang_detected = check_for_hang()

    if hang_detected:

        log_line(
            f"ADDRESS 0x{current_address:04X} CAUSED HANG"
        )

        # Move to next address
        advance_address()

        time.sleep(2)

        send_address(current_address)

        log_line(
            f"ADVANCING TO ADDRESS 0x{current_address:04X}"
        )

        cycle_start_time = time.time()

    # Address Cycling
    if time.time() - cycle_start_time >= INTERVAL_SECONDS:
        perform_cycle()
        cycle_start_time = time.time()

    time.sleep(0.01)
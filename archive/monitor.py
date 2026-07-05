import serial
import time
import threading

# ---------------- CONFIG ----------------
PORT = 'COM3'          # Change to your port (e.g., /dev/ttyUSB0 on Linux)
BAUD = 115200
LOG_FILE = 'arduino_log.txt'

EXPECTED_STRINGS = [
    "INIT_OK",
    "LOOP_RUNNING"
]

HEARTBEAT_TIMEOUT = 5.0      # seconds before assuming lockup
TASK_TIMEOUT = 2.0           # max allowed task duration
RESET_WAIT = 3.0             # wait after reset

# ----------------------------------------

class ArduinoMonitor:
    def __init__(self):
        self.ser = serial.Serial(PORT, BAUD, timeout=1)
        time.sleep(2)  # allow Arduino to reset on connect
        
        self.log_file = open(LOG_FILE, 'a')

        self.last_heartbeat = time.time()
        self.current_tasks = {}
        self.expected_index = 0  # next byte index to flip

        self.running = True

    def log(self, line):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {line}"
        print(entry)
        self.log_file.write(entry + '\n')
        self.log_file.flush()

    # 1 & 2: Monitor + Save Output
    def read_serial(self):
        while self.running:
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line:
                    self.handle_line(line)
            except Exception as e:
                print("Read error:", e)

    # 3 & 4: Detect differences + timing issues
    def handle_line(self, line):
        self.log(line)

        # ---- Expected string check ----
        for expected in EXPECTED_STRINGS:
            if expected not in line:
                self.log(f"WARNING: Missing expected string: {expected}")

        # ---- Heartbeat detection ----
        if "HEARTBEAT" in line:
            self.last_heartbeat = time.time()

        # ---- Task tracking ----
        if line.startswith("TASK_START:"):
            task = line.split(":")[1]
            self.current_tasks[task] = time.time()

        elif line.startswith("TASK_END:"):
            task = line.split(":")[1]
            if task in self.current_tasks:
                duration = time.time() - self.current_tasks[task]
                if duration > TASK_TIMEOUT:
                    self.log(f"WARNING: Task {task} too slow ({duration:.2f}s)")
                del self.current_tasks[task]

    # 5: Detect lockup
    def watchdog(self):
        while self.running:
            time.sleep(1)

            # heartbeat timeout
            if time.time() - self.last_heartbeat > HEARTBEAT_TIMEOUT:
                self.log("ERROR: Arduino appears locked up")
                self.reset_arduino()

            # task timeout
            for task, start_time in list(self.current_tasks.items()):
                if time.time() - start_time > TASK_TIMEOUT:
                    self.log(f"ERROR: Task {task} stalled")
                    self.reset_arduino()

    # Reset via DTR toggle
    def reset_arduino(self):
        self.log("Resetting Arduino...")

        self.ser.setDTR(False)
        time.sleep(1)
        self.ser.setDTR(True)

        time.sleep(RESET_WAIT)

        # 6: Send next byte index
        self.send_next_byte_index()

        # reset tracking
        self.last_heartbeat = time.time()
        self.current_tasks.clear()

    def send_next_byte_index(self):
        cmd = f"SET_BYTE:{self.expected_index}\n"
        self.ser.write(cmd.encode())
        self.log(f"Sent: {cmd.strip()}")

        self.expected_index += 1

    def start(self):
        t1 = threading.Thread(target=self.read_serial)
        t2 = threading.Thread(target=self.watchdog)

        t1.start()
        t2.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            self.log_file.close()
            self.ser.close()


if __name__ == "__main__":
    monitor = ArduinoMonitor()
    monitor.start()
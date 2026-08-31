import board
import digitalio
import rotaryio
import usb_cdc
import time
import json

# Matrix wiring for the 9 keyboard switches.
# Update these lists to match your row/column wiring on the Seed Studio RP2040.
ROW_PINS = [board.GP0, board.GP1, board.GP2]
COL_PINS = [board.GP3, board.GP4, board.GP5]

ENCODER_A_PIN = board.GP6
ENCODER_B_PIN = board.GP7
ENCODER_BUTTON_PIN = board.GP8

DEBOUNCE_MS = 20
STATE_REPORT_INTERVAL = 0.2

usb_console = usb_cdc.console


def make_row_pin(pin):
    pin_obj = digitalio.DigitalInOut(pin)
    pin_obj.direction = digitalio.Direction.OUTPUT
    pin_obj.value = True
    return pin_obj


def make_col_pin(pin):
    pin_obj = digitalio.DigitalInOut(pin)
    pin_obj.direction = digitalio.Direction.INPUT
    pin_obj.pull = digitalio.Pull.UP
    return pin_obj


class DebouncedKey:
    def __init__(self):
        self.value = False
        self.last_raw = False
        self.last_change = time.monotonic()

    def update(self, raw_pressed: bool):
        now = time.monotonic()
        if raw_pressed != self.last_raw:
            self.last_raw = raw_pressed
            self.last_change = now
            return False

        if raw_pressed != self.value and (now - self.last_change) >= DEBOUNCE_MS / 1000:
            self.value = raw_pressed
            return True

        return False


class DebouncedInput:
    def __init__(self, pin, active_low=True):
        self.pin = pin
        self.active_low = active_low
        self.value = self._normalize(pin.value)
        self.last_raw = self.value
        self.last_change = time.monotonic()

    def _normalize(self, raw_value: bool) -> bool:
        return not raw_value if self.active_low else raw_value

    def update(self):
        raw = self._normalize(self.pin.value)
        now = time.monotonic()
        if raw != self.last_raw:
            self.last_raw = raw
            self.last_change = now
            return False

        if raw != self.value and (now - self.last_change) >= DEBOUNCE_MS / 1000:
            self.value = raw
            return True

        return False


class RotaryEncoder:
    def __init__(self, pin_a, pin_b):
        self.encoder = rotaryio.IncrementalEncoder(pin_a, pin_b)
        self.position = self.encoder.position

    def update(self):
        new_position = self.encoder.position
        delta = new_position - self.position
        if delta != 0:
            self.position = new_position
        return delta


def write_line(text: str):
    usb_console.write((text + "\r\n").encode("utf-8"))


def send_state(keys, encoder_pos, encoder_button):
    payload = {
        "keys": [int(key.value) for key in keys],
        "encoder_position": encoder_pos,
        "encoder_button": int(encoder_button.value),
    }
    write_line("STATE:" + json.dumps(payload))


def print_menu():
    write_line("=== Seed Studio RP2040 Macro UI ===")
    write_line("Commands:")
    write_line("  h        Show this help text")
    write_line("  s        Send current state snapshot")
    write_line("  r        Reset encoder position to zero")
    write_line("  d        Toggle debug state reporting")
    write_line("  q        Quit (does not reboot board)")
    write_line("")


def parse_command(command: str, state):
    if command == "h":
        print_menu()
    elif command == "s":
        send_state(state["keys"], state["encoder"].position, state["button"])
    elif command == "r":
        state["encoder"].position = 0
        write_line("Encoder position reset to 0")
    elif command == "d":
        state["debug"] = not state["debug"]
        write_line(f"Debug reporting {'enabled' if state['debug'] else 'disabled'}")
    elif command == "q":
        write_line("Ready. Use your host terminal to disconnect.")
    elif command:
        write_line(f"Unknown command: {command}")
        print_menu()


def scan_matrix(rows, cols, key_states):
    changed = False
    num_cols = len(cols)

    for row_index, row_pin in enumerate(rows):
        row_pin.value = False
        time.sleep(0.001)

        for col_index, col_pin in enumerate(cols):
            key_index = row_index * num_cols + col_index
            raw_pressed = not col_pin.value
            if key_states[key_index].update(raw_pressed):
                changed = True

        row_pin.value = True

    return changed


def main():
    rows = [make_row_pin(pin) for pin in ROW_PINS]
    cols = [make_col_pin(pin) for pin in COL_PINS]
    keys = [DebouncedKey() for _ in range(len(rows) * len(cols))]
    encoder_button = DebouncedInput(make_col_pin(ENCODER_BUTTON_PIN), active_low=True)
    encoder = RotaryEncoder(ENCODER_A_PIN, ENCODER_B_PIN)

    state = {
        "keys": keys,
        "encoder": encoder,
        "button": encoder_button,
        "debug": True,
    }

    print_menu()
    last_report = time.monotonic()

    while True:
        if usb_console.in_waiting:
            raw = usb_console.readline().decode("utf-8", errors="ignore").strip().lower()
            parse_command(raw, state)

        changed = scan_matrix(rows, cols, keys)
        if encoder_button.update():
            changed = True

        delta = encoder.update()
        if delta != 0:
            changed = True

        now = time.monotonic()
        if changed or (now - last_report) >= STATE_REPORT_INTERVAL:
            if state["debug"]:
                send_state(keys, encoder.position, encoder_button)
            last_report = now

        time.sleep(0.02)


if __name__ == "__main__":
    main()

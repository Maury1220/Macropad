# Seed Studio RP2040 Macro Pad UI

This workspace contains:

- `main.py`: CircuitPython firmware for a Seed Studio RP2040 board with 9 switches, an EC11 rotary encoder, and an encoder push button.
- `host_ui.py`: Host-side Python UI script that connects to the board over USB serial and prints state updates.

## Setup

1. Copy `main.py` onto your RP2040 board running CircuitPython.
2. Adjust `KEY_PINS`, encoder pins, and `KEY_ACTIVE_HIGH` in `main.py` to match your wiring.
3. Install PySerial on your PC:

```bash
pip install pyserial
```

4. Run the host UI:

```bash
python host_ui.py
```

## Host UI commands

- `s`: request current state
- `r`: reset encoder position
- `d`: toggle debug reporting
- `h`: show help
- `q`: quit

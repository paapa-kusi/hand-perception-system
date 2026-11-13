import argparse
import time

import serial


def servo_target(value):
    try:
        pin, angle = map(int, value.split(":"))
    except ValueError:
        raise argparse.ArgumentTypeError("Expected PIN:ANGLE, for example 2:85.") from None
    if pin not in range(2, 8) or angle not in range(181):
        raise argparse.ArgumentTypeError("Use pins 2–7 and angles between 0 and 180.")
    return pin, angle


class PeacePose:
    def __init__(self, port, targets):
        self.targets = targets
        self.connection = serial.Serial(port, 9600, timeout=0.25, write_timeout=1)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if b"Multi-finger servo finder ready" in self.connection.readline():
                return
        self.connection.close()
        raise RuntimeError("The Mega did not identify itself as the servo tester.")

    def send(self, targets=None):
        for pin, angle in self.targets if targets is None else targets:
            self.connection.write(f"{pin}:{angle}\n".encode("ascii"))
            expected = f"Pin {pin} angle: {angle}".encode("ascii")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if self.connection.readline().strip() == expected:
                    break
            else:
                raise RuntimeError(f"The Mega did not acknowledge pin {pin} at {angle}°.")

    def close(self):
        self.connection.close()


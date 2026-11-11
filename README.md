# Robotic Hand Perception

Recognize hand poses from a webcam and send the matching calibrated servo positions to an Arduino Mega 2560. The Windows launcher creates an isolated Python environment and installs the application dependencies automatically. The two OpenCV hand models download on first run and are checked against pinned SHA-256 hashes.

## Quick start on Windows

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/) and enable the Python Launcher during installation.
2. Connect the webcam and the Mega 2560 running the project's multi-finger servo tester firmware.
3. Double-click `setup_and_run.bat`.

On first run, setup installs OpenCV, PySerial, and PyYAML into `.venv`, then downloads about 8 MB of OpenCV Zoo model data. Later launches reuse the environment and cached models. The app finds an Arduino Mega 2560 by USB VID/PID automatically. If no Mega is found, it starts in camera preview mode. To select a port manually, run `setup_and_run.bat --port COM3`; for preview only, run `setup_and_run.bat --preview-only`.

The camera window shows pose recognition and its three second hold countdown. Hold open palm first to reset the hand. Then hold a recognized pose for three seconds to send it once. Press **Q** to close the app.

## Recognized poses

- Open palm: reset all six motors.
- Peace sign: pointer and middle open; thumb, ring, and pinky closed.
- Fist: all fingers closed.
- Horns: pointer and pinky open; thumb, middle, and ring closed.
- OK: pointer, thumb, and palm move from the open palm reset position.

Servo pins and angles are in `hand-calibration.json`. The supplied values match the project hand. Change them if the hand's linkage or servo mounting differs. Pin angles are sent only after the Mega acknowledges each command.

## Other platforms

The Python app can run on macOS or Linux with Python 3.11+, the packages in `requirements.txt`, a webcam, and a serial connection to the Mega. Create a virtual environment, install the requirements, then run `python launch.py`. The one-click installer is for Windows; model files still download automatically on every platform.

## Verification

The CV app was run with the connected Logitech C270 and Mega 2560. Camera tracking and pose recognition were checked live for open palm, peace, and OK, with Mega acknowledgements observed for the configured commands. The three second hold timer and dropout recovery were also exercised. Servo acknowledgements confirm the Mega received each target; they do not verify that every mechanical fingertip reaches the exact pose. Fist and horns are included in the app but were not physically verified on the hand.


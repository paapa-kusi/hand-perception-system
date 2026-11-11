# MediaPipe Hand Tracking Application

## Peace and Open Palm demo

The webcam demo recognizes a single operator's `Victory` and `Open_Palm` gestures and emits the corresponding `PEACE` and `OPEN` pose names. Hold the pose for about 200 ms. A fist, an unclear pose, or a missing hand clears the pending gesture. The defaults are in `cv_hand_perception/config.yaml`.

From the repository root in PowerShell, install the dependencies and download the [MediaPipe model](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer).

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
curl.exe -fL https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task -o cv_hand_perception/gesture_recognizer.task
.\.venv\Scripts\python.exe cv_hand_perception/main.py --gesture-demo
```

With the Conda environment, run `./run.sh --gesture-demo` after downloading the model to the same location. `--model` can point to a different local copy. The preview shows the current prediction and the last accepted pose. Press `Q` to quit.

### Test the robot manually, then connect the camera

The [servo tester](firmware/servo-tester) can verify wiring one channel at a time. The [gesture controller](firmware/gesture-controller) contains the two pose targets and runs on the Mega 2560. These are the starting targets from the checked thumb/palm row and the bottom finger rows of the calibration sheet, mapped to the confirmed pins.

| Pin | Actuator | Open | Peace |
|---:|---|---:|---:|
| 2 | Pointer | 0° | 0° |
| 3 | Thumb | 180° | 0° |
| 4 | Pinky | 0° | 180° |
| 5 | Middle | 180° | 180° |
| 6 | Palm | 100° | 0° |
| 7 | Ring | 180° | 0° |

1. With the hand unloaded, verify the angles and travel on the actual build. Check ring clearance against the extended middle finger. On the first arm after a board reset, the controller applies the Open targets immediately, so verify and park the hand at Open first.
2. Build and upload with PlatformIO. Replace `COM5` with the Mega's port and close any serial monitor before opening the demo.

   ```powershell
   .\.venv\Scripts\python.exe -m pip install platformio
   .\.venv\Scripts\python.exe -m platformio run -d firmware/gesture-controller
   .\.venv\Scripts\python.exe -m platformio run -d firmware/gesture-controller -t upload --upload-port COM5
   .\.venv\Scripts\python.exe cv_hand_perception/main.py --manual --port COM5
   ```

3. Focus the preview and press `A` to arm, `2` for Peace, then `1` for Open. Peace closes ring and pinky before folding thumb and palm. Opening unfolds thumb and palm first. Verify clearance in both directions. `S` halts further steps, holds the current servo targets, and disarms. A lost USB heartbeat also disarms. Press `A` again to resume. `Q` stops and exits.
4. Start the integrated demo with `--gesture-demo --port COM5` and press `A` in the preview. The controller finishes an accepted move if tracking drops. Any new pose must qualify again after the controller is idle.

Use the terminal log to check gesture decisions, serial command delivery, and when the last target was sent to the servos. For the bench trial, film the operator and robot together. Time the completed gesture to first visible motion and to the settled pose separately. The goal is motion onset within 500 ms in at least 95% of trials. Count missed and unintended commands while alternating both poses and showing fist, moving between poses, and leaving the frame. `DONE` confirms the final commanded angles, so use the video to measure actual settling.

## Setup and Run

The easiest way to set up the environment and run the application is to use the `run.sh` script. This script will:
1. Check for `conda`.
2. Create the `cv_hand_perception` environment if it doesn't exist.
3. Install the Python dependencies from `requirements.txt`.
4. Activate the environment and start the program.

To run:
```sh
./run.sh
```

### Manual Setup

1. Create a conda environment:
   ```sh
   conda env create -f environment.yml
   ```
2. Activate it:
   ```sh
   conda activate cv_hand_perception
   ```
3. Run the application:
   ```sh
   cd cv_hand_perception
   python main.py
   ```

## Improvement Area 1: Robustness Testing

Test under different conditions:
- bright room
- dark room
- cluttered background
- different skin tones
- different camera angles
- fast movement
- partial occlusion
- hand near face
- hand leaving frame

Create a simple test matrix:

| Condition | FPS | Detection Rate | Jitter | Notes |
| :--- | :--- | :--- | :--- | :--- |
| | | | | |

Metrics:
- FPS
- detection success rate
- average landmark jitter
- angle jitter
- lost tracking events
- latency


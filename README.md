# MediaPipe Hand Tracking Application

## Setup and Run

The easiest way to set up the environment and run the application is to use the `run.sh` script. This script will:
1. Check for `conda`.
2. Create the `cv_hand_perception` environment if it doesn't exist.
3. Install dependencies (`mediapipe`, `opencv-python`, `pyyaml`).
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

## Improvement Areas

### Improvement Area 1: Robustness Testing

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

This turns the CV work into engineering, not just a demo.

### Improvement Area 2: Better Features

MediaPipe landmarks are the base. You can add derived features:

- **Finger Curl**: How bent each finger is.
- **Finger Spread**: Distance between adjacent fingertips. Useful for gestures.
- **Palm Orientation**: Is the palm facing camera, sideways, down?
- **Wrist Direction**: Useful for arm extension later.
- **Motion Velocity**: How fast each fingertip is moving.
- **Pinch Distance**: Distance between thumb tip and index tip. Useful for grasping.
- **Grasp State**: Open, closing, holding, releasing.

This prepares the system for Phase 2 and Phase 3.

### Improvement Area 3: Temporal Modeling

A single frame is weak. Motion happens over time.

Create a sliding window:
- last 10-30 frames

Use it to calculate:
- velocity
- acceleration
- smoothed gesture state
- motion intent

Example:
- index curl increasing quickly → user is closing index finger
- all fingers curl increasing → grasp command
- thumb/index distance decreasing → pinch command

This is where you start moving toward intelligent control.

### Improvement Area 4: Gesture Classifier

After logging data, build a small classifier.

Input:
- finger curls
- finger angles
- pinch distances
- palm orientation
- velocity features

Output:
- open_hand
- fist
- pinch
- point
- peace
- thumbs_up
- grab
- release

Start simple:
- rule-based thresholds

Then upgrade:
- Random Forest
- SVM
- small MLP
- LSTM for dynamic gestures

Not the main Phase 1 goal, though. It is a stretch goal. The main goal is continuous hand state, not just gesture labels.

### Improvement Area 5: Latency Optimization

For Phase 2, latency matters.

Target:
- camera → processed hand state under 50ms

Good enough:
- under 100ms

Measure:
- camera read time
- model inference time
- feature extraction time
- filtering time
- serial send time

Use a profiler or simple timestamps.

Potential optimizations:
- lower resolution
- separate camera thread
- process every other frame
- use async queue
- avoid heavy drawing during control
- use NumPy vectorization
- eventually ONNX/TFLite/edge inference

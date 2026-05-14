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


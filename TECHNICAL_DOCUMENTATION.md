# Technical Documentation: Real-Time Hand Perception & Teleoperation Pipeline

## 1. Project Overview
This project implements Phase 1 of a real-time computer vision hand perception and robotic teleoperation pipeline. It is designed to act as the sensory frontend for a modular robotics platform, translating human hand movements into actionable data for tendon-driven robotic hands. The current implementation focuses on webcam-based 2.5D tracking (scaled relative 3D), heuristic biomechanical feature extraction, and temporal filtering to produce stable, normalized control signals.

## 2. System Goals
**Immediate Phase 1 Goals (Implemented):**
*   Webcam-based monocular hand tracking using MediaPipe.
*   Low-latency extraction of finger joint angles.
*   Stabilization of outputs for robotic hand mirroring via adaptive filtering and dynamic calibration.
*   Standardized JSON telemetry output.

**Long-Term Vision (Not Currently Implemented):**
*   ROS2 integration and simulation environments.
*   Transformer-based true metric 3D reconstruction and MANO modeling.
*   Embodied AI, imitation learning, and autonomous manipulation.

## 3. Architecture Overview
The system utilizes a modular, frame-by-frame feedforward architecture:
1.  **Camera Input:** Frame acquisition via OpenCV.
2.  **Tracking:** MediaPipe Hands extracts 21 2.5D landmarks.
3.  **Feature Extraction:** Landmarks are projected onto a computed palm-plane to isolate flexion, and heuristic range-of-motion clamps are applied.
4.  **Temporal Filtering:** A One Euro Filter (1€) smooths raw curl values, and deadband logic suppresses micro-jitter.
5.  **Calibration:** A Sliding-Window Normalization (SWN) process maps absolute angles to a [0.0, 1.0] robotic control space.
6.  **Telemetry & Output:** The final state is logged and rendered on-screen.

## 4. Installation and Setup
```bash
conda env create -f environment.yml
conda activate hand_perception
pip install -r requirements.txt
cp cv_hand_perception/config.example.yaml cv_hand_perception/config.yaml
python main.py
```

**Session Management Workflow:**
To prevent pushing test sessions with specific operator names to version control and to avoid mixing up biomechanical parameters:
1. `config.yaml` is intentionally ignored by Git. A `config.example.yaml` is provided instead to track structure without personal data.
2. At runtime, `main.py` checks the `operator_name` in the configuration.
3. If the name is left as `"default_user"`, the system will pause in the terminal and prompt the operator to enter their name before launching the camera. This guarantees accurate, person-specific telemetry data without requiring manual file edits.

## 5. Runtime Requirements
*   **Hardware:** Standard RGB Webcam, x86 or ARM CPU (GPU optional but recommended for MediaPipe).
*   **Performance Target:** Real-time processing (>30 FPS) with sub-30ms end-to-end latency.

## 6. Dependency Breakdown
*   `opencv-python`: Camera interfacing and dashboard visualization.
*   `mediapipe`: Core machine learning inference for hand landmark detection.
*   `numpy`: Vector mathematics, cross-products, and Z-score calculations.
*   `pyyaml`: Configuration management (`config.yaml`).

## 7. Camera Input Pipeline
Implemented in `camera.py`. The `CameraManager` wraps `cv2.VideoCapture` to handle hardware interfacing. It includes basic error recovery, returning a boolean status flag to allow the main loop to gracefully handle dropped frames.

## 8. Hand Tracking Pipeline
Implemented in `hand_tracker.py` using MediaPipe Hands. 
*   **Reality Check:** This is a 2.5D pseudo-3D tracker (scaled relative 3D tracking). The X and Y coordinates are metric/pixel-accurate, but the Z coordinate represents relative depth proportional to the hand's scale, *not* true metric 3D depth. 
*   **Implementation:** Currently configured to track a single hand (Phase 1 constraint). It actively reverses MediaPipe's handedness classification to account for mirrored front-facing webcams.

## 9. Landmark Processing
The pipeline processes the 21 standard hand landmarks. Landmarks are returned in both normalized image coordinates [0, 1] and absolute pixel coordinates. Hidden or occluded joints are *not* explicitly reconstructed by our logic; the system relies entirely on MediaPipe's internal neural network estimations for occluded points.

## 10. Palm Normalization
Implemented in `features.py`. To separate finger flexion (bending) from abduction (spreading), the system computes a palm normal vector using the wrist, index MCP, and pinky MCP. Finger vectors (excluding the highly complex thumb) are projected onto the plane perpendicular to this normal before angles are calculated.

## 11. Finger Angle Extraction
Calculates the angles for MCP, PIP, and DIP joints using dot products. 
*   Angles are converted to a "bend" metric (180° - angle). 
*   **Biomechanical Constraints:** Heuristic Range of Motion (ROM) clamps are applied (e.g., PIP is clamped to [0, 100] degrees). This is a fast heuristic, *not* a formal kinematic optimization or inverse kinematics solver.

## 12. Finger Curl Estimation
Calculates a single `raw_curl` value per finger using a weighted sum of the MCP (25%), PIP (50%), and DIP (25%) bends. 
*   **Coupling Heuristic:** Under low-confidence conditions (< 0.5), a biomechanical coupling override is triggered, forcing `DIP = 0.67 * PIP`. This stabilizes the distal joints when MediaPipe's estimations degrade.

## 13. Temporal Filtering
Implemented in `filters.py`. 
*   **One Euro Filter:** Selected over Kalman filtering because it dynamically adjusts its cutoff frequency based on the speed of movement, providing low latency during fast motions and high smoothing during slow/static postures without requiring complex state-transition matrices.
*   **Deadband:** A static threshold prevents the filter from updating the output if the change is microscopic, preventing physical servos from burning out due to high-frequency jitter.

## 14. Calibration Pipeline
Implemented in `calibration.py`. Maps raw curl angles to a standardized [0.0, 1.0] range for servo control.
*   Uses a Sliding-Window Normalization (SWN) approach, calculating a Z-score based on a rolling buffer to adapt to the user's current range of motion dynamically.
*   Includes a fallback to peak-seeking hysteresis if the buffer is insufficiently populated.

## 15. Confidence Handling
Handled across `main.py` and `features.py`. If tracking is lost completely, the filter holds the last known valid state for a brief timeout (0.3s) to bridge single-frame drops, after which it resets to a neutral open-hand state.

## 16. Error Recovery
`main.py` monitors consecutive camera failures, terminating the application after 30 dropped frames.

## 17. Telemetry and Data Logging
Implemented in `telemetry.py`. Logs high-frequency frame data (angles, latencies, confidence, clamping flags) to JSON Lines (JSONL) files. A `SessionSummaryLogger` aggregates this data to track long-term stability and detection rates.

## 18. Visualization/Debugging
Implemented in `visualizer.py`. Renders the MediaPipe skeleton and an overlaid dashboard showing FPS, system latency, normalized curl values, and testing statuses.

## 19. Robotic Control Output
The final output of the pipeline is a dictionary of five fingers, each containing a `curl` value strictly bounded between [0.0, 1.0]. 

## 20. Servo Mapping Interface
**Status: Planned Future Work.** Currently, the pipeline terminates at data generation. Translating the [0.0, 1.0] state into actual PWM signals or ROS2 messages is reserved for Phase 2.

## 21. Real-Time Constraints
Formal inverse kinematics and global optimization were explicitly rejected for Phase 1 to guarantee sub-10ms processing latency on standard CPUs. Heuristic vector projection and simple scalar clamps provide sufficient accuracy for basic teleoperation while maximizing iteration speed.

## 22. Latency Considerations
The dominant latency sources are hardware camera exposure/transfer times and MediaPipe's neural network inference. The custom Python pipeline (extraction, filtering, calibration) executes in roughly 1-3ms.

## 23. Robotics Integration
**Status: Planned Future Work.** The current implementation is a standalone perception module.

## 24. Testing and Validation
Implemented via `tester.py`. The system includes a robustness testing suite that quantifies tracking stability by measuring landmark jitter (Euclidean distance changes across frames), angular jitter, detection rate, and biomechanical coupling violations.

## 25. Current Limitations
*   **Monocular Depth Ambiguity:** MediaPipe cannot resolve absolute scale; depth is entirely relative.
*   **Occlusion Mitigation:** Severe self-occlusion (e.g., tight fists at off-angles) or object interaction causes MediaPipe confidence to plummet and introduces severe landmark jitter. Current constraints act as heuristic occlusion safety rather than true occlusion handling.
*   **Kinematic Naivety:** The PIP-DIP coupling and ROM clamps are rigid heuristics. The system does not possess a true skeletal model that prevents physically impossible hand states (e.g., fingers passing through the palm).
*   **No Haptic/Force Feedback:** The system is purely open-loop perception.

## 26. Future Work (Phase 2 & Beyond)
*   **Phase 2:** Implement ROS2 node wrappers, integrate multi-camera support, and transition from heuristic occlusion safety to true occlusion handling (imagining hidden fingers accurately).
*   **Long-Term Filtering:** While temporal smoothing currently relies on adaptive low-pass filters, future architectures handling complete visual dropout may require Unscented Kalman Filters (UKF) to probabilistically propagate joint states.
*   **Long-Term:** Replace MediaPipe with transformer-based architectures for true 3D mesh reconstruction (e.g., MANO models), enabling complex autonomous manipulation and imitation learning.

## 27. References

**Current Phase 1 Implementations:**
1. **MediaPipe Hands:** Real-time extraction of 21 3D hand landmarks was achieved utilizing the MediaPipe Hands framework.
   *Zhang, F., Bazarevsky, V., Vakunov, A., Tkachenka, A., Sung, G., Chang, C. L., & Grundmann, M. (2020). MediaPipe Hands: On-device Real-time Hand Tracking. arXiv preprint arXiv:2006.10214.*
2. **Palm-Centered Normalization:** To isolate true finger flexion from out-of-plane abduction, kinematic joint angles were decomposed against a local palm-plane coordinate frame established via the wrist and metacarpophalangeal joints.
   *Dong, Y., & Payandeh, S. (2025). Hand Kinematic Model Construction Based on Tracking Landmarks. Applied Sciences, 15(16), 8921.*
3. **Temporal Smoothing:** High-frequency tracking noise and servo jitter were mitigated using a One Euro (1€) Filter, an adaptive first-order low-pass filter that dynamically adjusts smoothing based on movement velocity.
   *Casiez, G., Roussel, N., & Vogel, D. (2012). 1€ filter: A simple speed-based low-pass filter for noisy input in interactive systems. In Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (pp. 2527-2530).*
4. **Biomechanical Constraints:** To ensure kinematic plausibility and prevent impossible servo commands during visual occlusion, strict range of motion clamps and PIP-DIP mechanical coupling ratios were enforced based on human anatomical limits.
   *Deng, C., Lu, W., Qian, Y., Liu, Y., Ning, M., & Zhan, Z. (2026). Finger Unit Design for Hybrid-Driven Dexterous Hands. Biomimetics, 10, 155.*
5. **Sliding-Window Normalization:** To achieve calibration-free operation across variable camera distances and user anatomies, hand states were continuously scaled using a Sliding-Window Normalization (SWN) technique to output dynamic z-scores.
   *Tanaka, T., Nambu, I., Maruyama, Y., & Wada, Y. (2022). Sliding-window normalization to improve the performance of machine-learning models for real-time motion prediction using electromyography. arXiv preprint arXiv:2205.09301.*
6. **Robustness Data Logging:** System resilience was evaluated using metamorphic testing principles, logging quantitative performance metrics across systematically varied environmental conditions such as illumination and occlusion.
   *Pu, et al. (2023). Robustness Evaluation in Hand Pose Estimation Models using Metamorphic Testing.*

**Phase 2 / Conceptual Future Work:**
7. **Transformer-Based Reconstruction:** Future iterations targeting complex manipulation will transition from skeletal keypoints to MANO-based 3D mesh recovery, utilizing Transformer architectures like HandOccNet or HaMeR to mathematically infer severely occluded joints.
   *Park, J., Oh, Y., Moon, G., Choi, H., & Lee, K. M. (2022). HandOccNet: Occlusion-Robust 3D Hand Mesh Estimation Network. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (pp. 1496-1505).*
8. **Kalman Filtering:** While temporal smoothing currently relies on adaptive low-pass filters, future architectures handling complete visual dropout may require Unscented Kalman Filters to probabilistically propagate joint states.
   *Stenger, B., Mendonça, P. R. S., & Cipolla, R. (2001). Model-Based Hand Tracking Using an Unscented Kalman Filter. In Proceedings of the British Machine Vision Conference (BMVC) (pp. 63-72).*

---

# Additional Project Artifacts

## A. Short README Version
**Hand Perception Module (Phase 1)**
A real-time, low-latency hand tracking pipeline designed for robotic teleoperation. Uses monocular RGB webcams and MediaPipe to track 21 hand landmarks, projects them onto a calculated palm-plane to isolate finger flexion, applies 1€ filtering for stability, and dynamically calibrates outputs to a [0.0, 1.0] range suitable for tendon-driven servos.

## B. Contributor Onboarding Guide
Welcome to the Hand Perception Module! 
1. **Understand the Goal:** We are building the *sensory frontend* for a robot. Latency and stability are more important than millimeter-perfect accuracy.
2. **Phase Boundary:** We are in Phase 1. Do not submit PRs for ROS2 or physical serial controls yet; keep the pipeline focused on generating clean JSON state dictionaries.
3. **Key Files:** Start by reading `main.py` to see the loop. Then read `features.py` to understand how we turn 3D points into usable angles, and `filters.py` to see how we remove jitter.
4. **Testing:** Before committing, run `main.py`, press `t` to start a robustness test, move your hand wildly, press `t` again, and ensure your changes haven't caused latency spikes or jitter regressions.

## C. Module/File Breakdown
*   `main.py`: The orchestrator and main execution loop.
*   `camera.py`: Video capture handling.
*   `hand_tracker.py`: MediaPipe ML inference wrapper.
*   `features.py`: Math-heavy module for normal vectors, projection, and angle calculation.
*   `filters.py`: 1€ filter and deadband logic.
*   `calibration.py`: Sliding-window Z-score normalization.
*   `telemetry.py`: JSONL logging for performance analysis.
*   `tester.py`: In-app robustness testing matrix generation.
*   `visualizer.py`: OpenCV drawing utilities.

## D. Pipeline Data Flow Explanation
1. `(H, W, 3) RGB Image` -> **HandTracker** -> `[(X,Y,Z) * 21]` (Normalized Landmarks)
2. `[(X,Y,Z) * 21]` -> **FeatureExtractor** -> `{ "index": { "raw_curl": 120.5, "angles": {...} } }`
3. `{ raw_curls }` -> **HandStateFilter** -> `{ "index": { "curl": 118.2 } }` (Smoothed)
4. `{ smoothed_curls }` -> **CalibrationManager** -> `{ "index": { "curl": 0.85 } }` (Normalized 0-1)

## E. API / Hand-State Schema Documentation
```json
{
  "timestamp": 1700000000.123,
  "hand_detected": true,
  "confidence": 0.98,
  "handedness": "Right",
  "fingers": {
    "thumb": { "curl": 0.23, "angle": 145.0 },
    "index": { "curl": 0.85, "angle": 45.0 },
    "middle": { "curl": 0.90, "angle": 30.0 },
    "ring": { "curl": 1.00, "angle": 10.0 },
    "pinky": { "curl": 1.00, "angle": 15.0 }
  }
}
```
*Note: `curl` is strictly [0.0, 1.0] where 0.0 is fully open and 1.0 is fully closed.*

## F. Suggested Folder Structure Improvements
Currently, the codebase is flat. Recommended transition for Phase 2:
```text
cv_hand_perception/
├── core/             # main.py, config.yaml
├── io/               # camera.py, visualizer.py
├── perception/       # hand_tracker.py, features.py
├── processing/       # filters.py, calibration.py
├── testing/          # tester.py, aggregate_tests.py
└── logs/             # telemetry and test_reports
```

## G. Suggested Inline Comments and Docstrings
*   `features.py:compute_palm_normal`: Add a docstring explicitly stating that this relies on the assumption that the wrist, index MCP, and pinky MCP remain relatively coplanar, which fails under extreme hand scrunching.
*   `filters.py:OneEuroFilter`: Add comments referencing the original paper's definition of `beta` (speed coefficient) and `min_cutoff` (static stability) to aid tuning.
*   `hand_tracker.py`: Document *why* handedness is flipped (front-facing camera mirror effect) to prevent future developers from "fixing" it.

## H. Phase 1 Citations Integrated
The following components have been fully integrated with their supporting research literature:
*   **Zhang et al. (2020):** MediaPipe 2.5D tracking capabilities and topology mapping.
*   **Dong & Payandeh (2025):** Palm-centered coordinate frame normalization.
*   **Casiez et al. (2012):** 1€ Filter implementation in `filters.py`.
*   **Deng et al. (2026):** Range of motion limits and `DIP = 0.67 * PIP` coupling logic in `features.py`.
*   **Tanaka et al. (2022):** Sliding-Window Normalization (SWN) applied to joint angles in `calibration.py`.
*   **Pu et al. (2023):** Metamorphic testing frameworks adapted for `tester.py`.

## I. Failure Modes and Testing Checklist
**Known Failure Modes:**
1.  **Fist Self-Occlusion:** When the hand makes a tight fist facing the camera, landmarks collapse. *Current Mitigation:* Coupling heuristics. *Unresolved:* Needs better temporal prediction.
2.  **Object Occlusion:** Holding an object breaks the palm-plane assumption. *Current Mitigation:* None.
3.  **High-Speed Motion Blur:** MediaPipe loses the hand. *Current Mitigation:* Filter timeout holds state for 0.3s.

**Testing Checklist (Before Merging PRs):**
*   [ ] Verify resting hand jitter is < 0.02 (normalized).
*   [ ] Verify rapid open/close cycles do not trigger the deadband incorrectly.
*   [ ] Test front-facing and top-down camera angles.
*   [ ] Verify latency remains < 15ms per frame on target hardware.

## J. Research Alignment Analysis
**Systems-Engineering Feedback:**
The current implementation successfully bridges the gap between raw computer vision and robotics control. The decision to use MediaPipe + Heuristics + 1€ Filter is highly aligned with the need for immediate, low-latency, CPU-friendly teleoperation. 

**Bottlenecks & Technical Debt:**
The reliance on MediaPipe's pseudo-3D Z-coordinate is the largest bottleneck. While projecting onto a palm-plane mitigates X/Y perspective distortion, the lack of true metric depth limits the system's ability to handle complex 6DoF hand orientations. Furthermore, the hardcoded ROM clamps and PIP-DIP coupling in `features.py` risk becoming technical debt when attempting to support diverse human operators; these should eventually be replaced by a parameterized kinematic solver.

**Future Path:**
For Phase 1 and early Phase 2 (basic grasping), this architecture is sufficient and scalable. However, for the long-term vision of autonomous manipulation and imitation learning, the heuristic feature extraction must be replaced with a robust mesh-recovery model (e.g., MANO) that inherently understands hand volume and physical constraints, rather than patching 2D points with Python heuristics.

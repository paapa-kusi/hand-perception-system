"""Launch the CV app with the checked-in hand calibration and optional Mega."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FINGER_ORDER = ("thumb", "pointer", "middle", "ring", "pinky", "palm")
POSES = {"peace": "peace", "fist": "fist", "horns": "horns", "okay": "okay"}


def find_mega_port():
    try:
        from serial.tools import list_ports
    except ImportError:
        return None

    matches = [
        item.device
        for item in list_ports.comports()
        if (item.vid, item.pid) == (0x2341, 0x0042)
        or "mega 2560" in (item.description or "").lower()
    ]
    if len(matches) > 1:
        raise RuntimeError("More than one Mega 2560 is connected. Disconnect one and try again.")
    return matches[0] if matches else None


def targets_for_pose(profile, pose):
    actuators = {item["finger"]: item for item in profile["actuators"]}
    targets = []
    for finger, value in profile[pose].items():
        actuator = actuators[finger]
        angle = actuator[value] if isinstance(value, str) else value
        low, high = sorted((actuator["open"], actuator["closed"]))
        if not low <= angle <= high:
            raise ValueError(f"{pose} angle for {finger} is outside its calibrated range.")
        targets.append((actuator["pin"], angle))
    return targets


def main():
    parser = argparse.ArgumentParser(description="Start the hand camera and robot pose preview.")
    parser.add_argument("--port", help="Override Mega port, for example COM3. Detected automatically by default.")
    parser.add_argument("--preview-only", action="store_true", help="Run camera recognition without moving the robot.")
    options = parser.parse_args()

    profile_path = ROOT / "hand-calibration.json"
    with profile_path.open(encoding="utf-8") as source:
        profile = json.load(source)
    configured_port = profile.get("port", "auto")
    port = None if options.preview_only else (
        options.port or (configured_port if configured_port.lower() != "auto" else find_mega_port())
    )
    app_args = [sys.executable, str(ROOT / "cv_hand_perception" / "main.py"), "--opencv"]

    if port:
        app_args.extend(["--port", port])
        for pose in POSES:
            for pin, angle in targets_for_pose(profile, pose):
                app_args.extend([f"--{pose}-target", f"{pin}:{angle}"])
        for pin, angle in targets_for_pose(profile, "open_palm"):
            app_args.extend(["--open-palm-target", f"{pin}:{angle}"])
        print(f"Mega detected on {port}; held poses will move the hand.", flush=True)
    else:
        print("No Mega detected. Running camera preview only. Connect the Mega and restart to move the hand.", flush=True)

    return subprocess.call(app_args, cwd=ROOT)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)


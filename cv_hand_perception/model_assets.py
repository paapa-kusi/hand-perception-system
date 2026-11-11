"""Download the small OpenCV Zoo models on first run and verify their hashes."""

from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen


MODEL_DIR = Path(__file__).resolve().parent.parent / "opencv_zoo"
MODELS = {
    "handpose_estimation_mediapipe_2023feb.onnx": (
        "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/handpose_estimation_mediapipe/handpose_estimation_mediapipe_2023feb.onnx",
        "db0898ae717b76b075d9bf563af315b29562e11f8df5027a1ef07b02bef6d81c",
    ),
    "palm_detection_mediapipe_2023feb.onnx": (
        "https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/palm_detection_mediapipe/palm_detection_mediapipe_2023feb.onnx",
        "78ff51c38496b7fc8b8ebdb6cc8c1abb02fa6c38427c6848254cdaba57fcce7c",
    ),
}


def ensure_models():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (url, expected_hash) in MODELS.items():
        destination = MODEL_DIR / filename
        if destination.is_file() and _file_hash(destination) == expected_hash:
            continue

        temporary = destination.with_suffix(destination.suffix + ".download")
        print(f"Downloading hand tracking model: {filename}", flush=True)
        try:
            with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            actual_hash = _file_hash(temporary)
            if actual_hash != expected_hash:
                raise RuntimeError(f"Checksum mismatch for {filename}; download was rejected.")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return MODEL_DIR


def _file_hash(path):
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


import os
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
REPO = SERVER.parent
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(REPO / "poc" / "emulators" / "arkit"))   # the validated ARKit/LiDAR emulator (POC 1, 23, 24)

# Frames are answered after the brain is done with them, so tests see the results; test_frames_async.py covers the
# production path, which answers 202 first.
os.environ.setdefault("MARCO_FRAMES_ASYNC", "0")

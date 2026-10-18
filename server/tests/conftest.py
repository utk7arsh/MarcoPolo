import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
REPO = SERVER.parent
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(REPO / "poc" / "emulators" / "arkit"))   # the validated ARKit/LiDAR emulator (POC 1, 23, 24)

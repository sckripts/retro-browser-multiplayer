import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "services" / "session-manager" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "services" / "runtime-agent" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "images" / "retro-session"))

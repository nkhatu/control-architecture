from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTROL_PLANE_SERVICE_SRC = PROJECT_ROOT / "apps" / "control-plane-service" / "src"

if str(CONTROL_PLANE_SERVICE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_SERVICE_SRC))

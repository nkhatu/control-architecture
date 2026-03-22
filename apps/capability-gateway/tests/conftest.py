from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CAPABILITY_GATEWAY_SRC = PROJECT_ROOT / "apps" / "capability-gateway" / "src"

if str(CAPABILITY_GATEWAY_SRC) not in sys.path:
    sys.path.insert(0, str(CAPABILITY_GATEWAY_SRC))

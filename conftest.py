from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SHARED_CONTRACTS_SRC = PROJECT_ROOT / "packages" / "shared-contracts" / "src"

if str(SHARED_CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_CONTRACTS_SRC))

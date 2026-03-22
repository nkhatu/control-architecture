from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_SRC = PROJECT_ROOT / "apps" / "orchestrator-api" / "src"
MEMORY_SRC = PROJECT_ROOT / "services" / "memory-service" / "src"

for source_root in (ORCHESTRATOR_SRC, MEMORY_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

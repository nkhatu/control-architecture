from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_WORKER_SRC = PROJECT_ROOT / "services" / "workflow-worker" / "src"
MEMORY_SRC = PROJECT_ROOT / "services" / "memory-service" / "src"
CAPABILITY_GATEWAY_SRC = PROJECT_ROOT / "apps" / "capability-gateway" / "src"

for source_root in (WORKFLOW_WORKER_SRC, MEMORY_SRC, CAPABILITY_GATEWAY_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

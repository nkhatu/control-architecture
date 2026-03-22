from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_WORKER_SRC = PROJECT_ROOT / "services" / "workflow-worker" / "src"
CONTEXT_MEMORY_SRC = PROJECT_ROOT / "services" / "context-memory-service" / "src"
PROVENANCE_SRC = PROJECT_ROOT / "services" / "provenance-service" / "src"
EVENT_CONSUMER_SRC = PROJECT_ROOT / "services" / "event-consumer" / "src"
CAPABILITY_GATEWAY_SRC = PROJECT_ROOT / "apps" / "capability-gateway" / "src"

for source_root in (WORKFLOW_WORKER_SRC, CONTEXT_MEMORY_SRC, PROVENANCE_SRC, EVENT_CONSUMER_SRC, CAPABILITY_GATEWAY_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

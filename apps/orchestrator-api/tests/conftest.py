from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_SRC = PROJECT_ROOT / "apps" / "orchestrator-api" / "src"
CONTEXT_MEMORY_SRC = PROJECT_ROOT / "services" / "context-memory-service" / "src"
PROVENANCE_SRC = PROJECT_ROOT / "services" / "provenance-service" / "src"
CAPABILITY_GATEWAY_SRC = PROJECT_ROOT / "apps" / "capability-gateway" / "src"
WORKFLOW_WORKER_SRC = PROJECT_ROOT / "services" / "workflow-worker" / "src"
POLICY_SERVICE_SRC = PROJECT_ROOT / "apps" / "policy-service" / "src"

for source_root in (
    ORCHESTRATOR_SRC,
    CONTEXT_MEMORY_SRC,
    PROVENANCE_SRC,
    CAPABILITY_GATEWAY_SRC,
    WORKFLOW_WORKER_SRC,
    POLICY_SERVICE_SRC,
):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

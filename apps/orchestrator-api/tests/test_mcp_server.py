from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def wait_for_http(url: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # pragma: no cover - transient startup polling
            last_error = exc
            time.sleep(0.1)

    raise RuntimeError(f"Timed out waiting for {url}") from last_error


def start_http_service(module_name: str, env: dict[str, str], port_env_var: str) -> tuple[subprocess.Popen[str], int]:
    port = find_free_port()
    env = {**os.environ.copy(), **env, port_env_var: str(port)}

    process = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            module_name,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wait_for_http(f"http://127.0.0.1:{port}/health")
    return process, port


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive cleanup
        process.kill()
        process.wait(timeout=5)


async def exercise_mcp_server(tmp_path: Path) -> None:
    context_process, context_port = start_http_service(
        "context_memory_service.main:app",
        {
            "CONTEXT_MEMORY_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'mcp-context-memory.db'}",
            "CONTEXT_MEMORY_AUTO_CREATE_SCHEMA": "true",
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
        },
        "CONTEXT_MEMORY_SERVICE_PORT",
    )
    provenance_process, provenance_port = start_http_service(
        "provenance_service.main:app",
        {
            "PROVENANCE_DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'mcp-provenance.db'}",
            "PROVENANCE_AUTO_CREATE_SCHEMA": "true",
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
        },
        "PROVENANCE_SERVICE_PORT",
    )
    capability_process, capability_port = start_http_service(
        "capability_gateway.main:app",
        {
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
            "CAPABILITY_REGISTRY_PATH": "config/registry/capabilities.yaml",
        },
        "CAPABILITY_GATEWAY_PORT",
    )
    policy_process, policy_port = start_http_service(
        "policy_engine.main:app",
        {
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
        },
        "POLICY_ENGINE_PORT",
    )
    event_consumer_process, event_consumer_port = start_http_service(
        "event_consumer.main:app",
        {
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
            "CONTEXT_MEMORY_SERVICE_BASE_URL": f"http://127.0.0.1:{context_port}",
            "PROVENANCE_SERVICE_BASE_URL": f"http://127.0.0.1:{provenance_port}",
        },
        "EVENT_CONSUMER_PORT",
    )
    workflow_process, workflow_port = start_http_service(
        "workflow_worker.main:app",
        {
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
            "CONTEXT_MEMORY_SERVICE_BASE_URL": f"http://127.0.0.1:{context_port}",
            "PROVENANCE_SERVICE_BASE_URL": f"http://127.0.0.1:{provenance_port}",
            "EVENT_CONSUMER_BASE_URL": f"http://127.0.0.1:{event_consumer_port}",
            "CAPABILITY_GATEWAY_BASE_URL": f"http://127.0.0.1:{capability_port}",
        },
        "WORKFLOW_WORKER_PORT",
    )
    try:
        server_env = os.environ.copy()
        server_env.update(
            {
                "ORCHESTRATOR_MCP_TRANSPORT": "stdio",
                "CONTEXT_MEMORY_SERVICE_BASE_URL": f"http://127.0.0.1:{context_port}",
                "PROVENANCE_SERVICE_BASE_URL": f"http://127.0.0.1:{provenance_port}",
                "EVENT_CONSUMER_BASE_URL": f"http://127.0.0.1:{event_consumer_port}",
                "POLICY_ENGINE_BASE_URL": f"http://127.0.0.1:{policy_port}",
                "WORKFLOW_WORKER_BASE_URL": f"http://127.0.0.1:{workflow_port}",
                "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
                "CAPABILITY_REGISTRY_PATH": "config/registry/capabilities.yaml",
                "AGENT_REGISTRY_PATH": "config/registry/agents.yaml",
            }
        )
        server = StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "orchestrator_api.mcp_server"],
            env=server_env,
            cwd=PROJECT_ROOT,
        )

        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tool_result = await session.list_tools()
                tool_names = {tool.name for tool in tool_result.tools}
                assert "create_domestic_payment_task" in tool_names
                assert "get_domestic_payment_task" in tool_names
                assert "resume_domestic_payment_task" in tool_names

                create_result = await session.call_tool(
                    "create_domestic_payment_task",
                    {
                        "customer_id": "cust_mcp_001",
                        "source_account_id": "acct_mcp_001",
                        "beneficiary_id": "ben_mcp_001",
                        "amount_usd": 2500,
                        "rail": "ach",
                        "requested_execution_date": "2026-03-24",
                        "initiated_by": "user.neil",
                        "trace_id": "tr_mcp_001",
                    },
                )
                assert create_result.isError is False
                structured = create_result.structuredContent
                assert structured is not None
                task_id = structured["task"]["task_id"]
                assert structured["task"]["status"] == "awaiting_approval"

                resume_result = await session.call_tool(
                    "resume_domestic_payment_task",
                    {
                        "task_id": task_id,
                        "approved_by": "user.ops_approver",
                        "release_mode": "execute",
                    },
                )
                assert resume_result.isError is False
                resumed = resume_result.structuredContent
                assert resumed is not None
                assert resumed["task"]["status"] == "settlement_pending"

                resource_result = await session.read_resource("registry://capabilities")
                assert resource_result.contents
                assert "domestic_payment.validate_beneficiary_account" in resource_result.contents[0].text

                task_resource = await session.read_resource(f"task://{task_id}")
                assert task_resource.contents
                assert task_id in task_resource.contents[0].text

                prompt_result = await session.get_prompt("review_domestic_payment_task", {"task_id": task_id})
                assert prompt_result.messages
                assert task_id in prompt_result.messages[0].content.text
    finally:
        stop_process(workflow_process)
        stop_process(event_consumer_process)
        stop_process(policy_process)
        stop_process(capability_process)
        stop_process(provenance_process)
        stop_process(context_process)


def test_mcp_server_supports_tools_resources_and_prompts(tmp_path: Path) -> None:
    asyncio.run(exercise_mcp_server(tmp_path))

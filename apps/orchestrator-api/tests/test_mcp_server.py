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


def start_memory_service(tmp_path: Path) -> tuple[subprocess.Popen[str], int]:
    port = find_free_port()
    database_path = tmp_path / "mcp-memory-service.db"

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{database_path}",
            "AUTO_CREATE_SCHEMA": "true",
            "MEMORY_SERVICE_PORT": str(port),
            "CONTROL_PLANE_CONFIG_PATH": "config/control-plane/default.yaml",
        }
    )

    process = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "memory_service.main:app",
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
    memory_process, memory_port = start_memory_service(tmp_path)
    try:
        server_env = os.environ.copy()
        server_env.update(
            {
                "ORCHESTRATOR_MCP_TRANSPORT": "stdio",
                "MEMORY_SERVICE_BASE_URL": f"http://127.0.0.1:{memory_port}",
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
        stop_process(memory_process)


def test_mcp_server_supports_tools_resources_and_prompts(tmp_path: Path) -> None:
    asyncio.run(exercise_mcp_server(tmp_path))

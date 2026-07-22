"""Payload-limit sweep integration test -- client-only orchestrator.

Runs multiple loopback benchmark cases. For each case:
1) starts a dedicated server subprocess with specific gRPC message limits,
2) sends large payload messages client -> server -> client,
3) records throughput and history-based end-to-end latency,
4) prints a summary table across all parameter pairs.
"""

from __future__ import annotations

import os
import socket
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from grpchook.baseclient import BaseClient, ClientConfig
from grpchook.exceptions import GrpcConnectionError
from grpchook.tools import generate_message
from grpchook import message_pb2
from tests.integration._interface import get_args

MiB = 1024 * 1024
KiB = 1024

STREAM_NAME = "bulk_payload"
EXIT_NAME = "server-exit"
SERVER_STARTUP_WAIT_S = 1.0
SERVER_STOP_WAIT_S = 10.0


@dataclass(frozen=True)
class SweepCase:
    """One benchmark case in the send/receive-limit sweep."""

    max_send_bytes: int
    max_receive_bytes: int
    payload_bytes: int
    messages: int


CASES: list[SweepCase] = [
    SweepCase(max_send_bytes=8 * MiB, max_receive_bytes=8 * MiB,
              payload_bytes=2 * MiB, messages=8),
    SweepCase(max_send_bytes=8 * MiB, max_receive_bytes=32 * MiB,
              payload_bytes=2 * MiB, messages=8),
    SweepCase(max_send_bytes=32 * MiB, max_receive_bytes=8 * MiB,
              payload_bytes=2 * MiB, messages=8),
    SweepCase(max_send_bytes=32 * MiB, max_receive_bytes=32 * MiB,
              payload_bytes=2 * MiB, messages=8),
]


def _build_client_options(
    max_send_bytes: int,
    max_receive_bytes: int,
) -> list[tuple[str, int | bool]]:
    """Return default client options extended with explicit message-size caps."""
    options = list(ClientConfig().grpc_options)
    options.extend([
        ("grpc.max_send_message_length", max_send_bytes),
        ("grpc.max_receive_message_length", max_receive_bytes),
    ])
    return options


def _history_e2e_ms(msg: message_pb2.Message) -> float | None:
    """Compute end-to-end wall-clock latency from first to last history receive timestamp."""
    if not msg.history:
        return None

    first = msg.history[0]
    last = msg.history[-1]
    has_first = first.receiveTimestamp.seconds or first.receiveTimestamp.nanos
    has_last = last.receiveTimestamp.seconds or last.receiveTimestamp.nanos
    if not (has_first and has_last):
        return None

    delta = last.receiveTimestamp.ToDatetime() - first.receiveTimestamp.ToDatetime()
    return delta.total_seconds() * 1000


def _pick_unused_port() -> int:
    """Reserve an ephemeral localhost port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _project_env() -> dict[str, str]:
    """Prepare env so subprocesses can import project packages reliably."""
    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[3]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(project_root) + (os.pathsep + existing if existing else "")
    return env


def _start_server(case: SweepCase, port: int) -> subprocess.Popen:
    """Start per-case server subprocess and fail fast on startup errors."""
    script_path = Path(__file__).resolve().parent / "server_payload_limits_sweep.py"
    integration_root = script_path.parent.parent
    env = _project_env()

    cmd = [
        sys.executable,
        str(script_path),
        "--port",
        str(port),
        "--max-send-message-length",
        str(case.max_send_bytes),
        "--max-receive-message-length",
        str(case.max_receive_bytes),
    ]

    proc = subprocess.Popen(  # pylint: disable=consider-using-with
        cmd,
        cwd=str(integration_root),
        env=env,
    )

    time.sleep(SERVER_STARTUP_WAIT_S)
    if proc.poll() is not None:
        raise RuntimeError(
            "Server failed to start for case "
            f"send={case.max_send_bytes} recv={case.max_receive_bytes}. "
            f"exit={proc.returncode}"
        )

    return proc


def _stop_server(proc: subprocess.Popen):
    """Terminate server process if still alive."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=SERVER_STOP_WAIT_S)
    except subprocess.TimeoutExpired:
        proc.kill()


class SenderClient(BaseClient):
    """Benchmark sender client."""

    def __init__(self, port: int, options: list[tuple[str, int | bool]], name: str):
        cfg = ClientConfig(grpc_options=options)
        super().__init__(
            port,
            name=name,
            provides=[STREAM_NAME, EXIT_NAME],
            requires=[],
            config=cfg,
        )


class ReceiverClient(BaseClient):
    """Benchmark receiver client that validates payload and records timings."""

    def __init__(self,
                 port: int,
                 options: list[tuple[str, int | bool]],
                 name: str,
                 expected_payload: bytes,
                 expected_messages: int):
        self.expected_payload = expected_payload
        self.expected_messages = expected_messages
        self.received = 0
        self.history_e2e_ms: list[float] = []
        self.done = threading.Event()

        cfg = ClientConfig(grpc_options=options)
        super().__init__(
            port,
            name=name,
            provides=[],
            requires=[STREAM_NAME],
            config=cfg,
        )

    def on_receive(self, data: message_pb2.Message) -> bool:
        if data.payload.bytePayload != self.expected_payload:
            raise AssertionError("Payload mismatch at receiver")

        self.received += 1
        e2e_ms = _history_e2e_ms(data)
        if e2e_ms is not None:
            self.history_e2e_ms.append(e2e_ms)

        if self.received >= self.expected_messages:
            self.done.set()
        return True


@dataclass
class CaseResult:
    max_send_mb: int
    max_receive_mb: int
    payload_kb: int
    messages: int
    throughput_mbps: float
    history_p50_ms: float
    history_p95_ms: float


def _run_case(case: SweepCase, timeout_s: float) -> CaseResult:
    """Run one benchmark case and return aggregated metrics."""
    port = _pick_unused_port()
    server_proc = _start_server(case, port)

    options = _build_client_options(case.max_send_bytes, case.max_receive_bytes)
    payload = b"X" * case.payload_bytes

    sender = None
    receiver = None
    spin_thread = None

    try:
        case_name = f"s{case.max_send_bytes // MiB}_r{case.max_receive_bytes // MiB}"
        receiver = ReceiverClient(
            port=port,
            options=options,
            name=f"payload_receiver_{case_name}",
            expected_payload=payload,
            expected_messages=case.messages,
        )
        sender = SenderClient(
            port=port,
            options=options,
            name=f"payload_sender_{case_name}",
        )

        spin_thread = threading.Thread(target=receiver.spin_forever, daemon=True)
        spin_thread.start()

        t0 = time.perf_counter()
        for _ in range(case.messages):
            sender.send_data(generate_message(STREAM_NAME, byte_payload=payload), add_history=True)
        sender.wait_done(additional_sleep=0)

        if not receiver.done.wait(timeout=max(timeout_s, 20.0)):
            raise TimeoutError(
                f"Receiver got {receiver.received}/{case.messages} messages "
                f"for send={case.max_send_bytes} recv={case.max_receive_bytes}"
            )
        t1 = time.perf_counter()

        sender.send_data(generate_message(EXIT_NAME))
        sender.wait_done()

        elapsed_s = t1 - t0
        total_bytes = case.messages * case.payload_bytes
        throughput_mbps = total_bytes / (elapsed_s * MiB)

        if receiver.history_e2e_ms:
            history_p50_ms = statistics.median(receiver.history_e2e_ms)
            history_p95_ms = statistics.quantiles(
                receiver.history_e2e_ms,
                n=20,
                method="inclusive",
            )[18]
        else:
            history_p50_ms = float("nan")
            history_p95_ms = float("nan")

        return CaseResult(
            max_send_mb=case.max_send_bytes // MiB,
            max_receive_mb=case.max_receive_bytes // MiB,
            payload_kb=case.payload_bytes // KiB,
            messages=case.messages,
            throughput_mbps=throughput_mbps,
            history_p50_ms=history_p50_ms,
            history_p95_ms=history_p95_ms,
        )
    finally:
        if sender is not None:
            try:
                sender.disconnect()
            except GrpcConnectionError:
                pass
        if receiver is not None:
            try:
                receiver.disconnect()
            except GrpcConnectionError:
                pass
        if spin_thread is not None:
            spin_thread.join(timeout=5.0)
        _stop_server(server_proc)


def _format_result_table(results: list[CaseResult]) -> str:
    """Render results as fixed-width text table."""
    headers = [
        "send_MB",
        "recv_MB",
        "payload_KB",
        "msgs",
        "throughput_MBps",
        "history_e2e_p50_ms",
        "history_e2e_p95_ms",
    ]

    rows = [
        [
            str(r.max_send_mb),
            str(r.max_receive_mb),
            str(r.payload_kb),
            str(r.messages),
            f"{r.throughput_mbps:.2f}",
            f"{r.history_p50_ms:.3f}",
            f"{r.history_p95_ms:.3f}",
        ]
        for r in results
    ]

    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]

    def _line(cells: list[str]) -> str:
        return " | ".join(cell.ljust(width) for cell, width in zip(cells, widths))

    separator = "-+-".join("-" * width for width in widths)
    lines = [_line(headers), separator]
    lines.extend(_line(row) for row in rows)
    return "\n".join(lines)


def _print_metric_legend() -> None:
    """Print short metric definitions to make summary table self-explanatory."""
    print("Metric definitions:")
    print("- throughput_MBps: payload bytes delivered per second (sender->server->receiver).")
    print("- history_e2e_p50_ms: median end-to-end latency from message history.")
    print("- history_e2e_p95_ms: 95th percentile end-to-end latency from message history.")
    print("- End-to-end latency is computed as first receiveTimestamp to last receiveTimestamp")
    print("  across the history hops on each message.")


if __name__ == "__main__":
    args = get_args("Payload-limit sweep benchmark on loopback")

    results: list[CaseResult] = []
    for index, case in enumerate(CASES, start=1):
        print(
            f"[case {index}/{len(CASES)}] send={case.max_send_bytes // MiB}MB "
            f"recv={case.max_receive_bytes // MiB}MB payload={case.payload_bytes // KiB}KB "
            f"messages={case.messages}"
        )
        results.append(_run_case(case, timeout_s=args.timeout))

    print("\nPayload-limit sweep summary (loopback, relative metrics):")
    _print_metric_legend()
    print(_format_result_table(results))

# Performance Suggestions

Analysis of `grpchook` codebase. Ordered by impact / effort ratio.

---

## 1. File logger runs at `INTERNAL_DEBUG` on every hot-path call ⚠️ HIGH IMPACT

**Root cause:** `get_logger` sets `logger.setLevel(INTERNAL_DEBUG)` (level 5) unconditionally so
the file handler can capture everything. This means every `idebug()` call passes the
logger-level gate and its arguments are formatted + written to disk.

**Hot-path offenders (fire on every message):**

| Location | Call | Frequency |
|---|---|---|
| `BaseServer.DataChannel` while-loop | `idebug("%s: main thread running", peer)` | every 1 s idle **or** every queued message |
| `BaseServer._handle_client_receive` | `idebug("%s: received message: %s", peer, request.metaInfo)` | every inbound message |
| `BaseClient._request_generator` | `idebug("Sending message to server: %s", data)` | every outbound message |
| `BaseClient._request_generator` | `idebug("Sending message with timestamp %s …")` | every outbound message |
| `BaseClient._receive_loop` | `idebug("received data from server: %s", …)` | every inbound message |
| `BaseClient.send_data` | `idebug("Enqueued data %s", …)` | every `send_data()` call |

**Fix:** Change the default file handler level from `INTERNAL_DEBUG` → `INFO` in `get_logger`.
Users who need full tracing opt in explicitly via `log_level=INTERNAL_DEBUG`.
Single-line change in `logger.py`.

---

## 2. Redundant `isinstance` check in `DataRegister.add_data_for_message_name` — LOW-MEDIUM IMPACT

`add_data_for_message_name` calls `isinstance(data, message_pb2.Message)` on every fan-out.
The data always arrives from `BaseServer._handle_client_receive` (typed), and is already
validated at the `send_data()` entry point on the client side. This is dead weight on the
hot routing path.

**Fix:** Remove the `isinstance` guard (or replace with `assert` for debug builds only).

---

## 3. `structPayload` vs `bytePayload` — MEDIUM IMPACT (user-side)

`structPayload` is a protobuf `Struct`, which serializes/deserializes as JSON internally.
`bytePayload` is raw bytes — zero parsing overhead.

For performance-critical paths (high frequency, large payloads), users should serialize
their own data (e.g. `msgpack`, `pickle`, `numpy.tobytes()`) and use `bytePayload`.

**No framework change required** — documentation/guidance only.

---

## 4. `max_workers` default may silently cap concurrent clients — MEDIUM IMPACT

`ServerConfig.max_workers = None` resolves to Python's `min(32, os.cpu_count() + 4)`.
On a typical 8-core machine this is **12 workers**.

Each connected client occupies one `ThreadPoolExecutor` thread for its **entire connection
lifetime** (the `DataChannel` generator holds the thread). The 13th client's RPC will be
queued in the executor and stall until a slot opens (i.e. another client disconnects).
There is no error or warning — the client just hangs at connection time.

**Fix:** Set `max_workers` explicitly in `ServerConfig` to at least the expected peak
concurrent client count. Add a warning log when `max_workers` is None so users are aware
of the default.

---

## 5. gRPC message compression — LOW-MEDIUM IMPACT (config, large payloads only)

gRPC supports `grpc.Compression.Gzip` / `Deflate` at the channel or per-call level.
Wins on large payloads over slow/high-latency links. Costs CPU locally — counter-productive
for small messages or loopback connections.

**Fix:** Add an optional `compression` field to `ServerConfig` / `ClientConfig` and pass it
to `grpc.server(...)` / `stub.DataChannel(...)`. Zero API-breaking change.

---

## Summary Table

| # | Area | Effort | Impact |
|---|---|---|---|
| 1 | File logger level on hot path | Trivial (1 line) | High |
| 2 | Redundant `isinstance` in fan-out | Trivial (remove 4 lines) | Low–Medium |
| 3 | `bytePayload` over `structPayload` | Zero (docs only) | Medium |
| 4 | `max_workers` explicit + warning | Small | Medium |
| 5 | gRPC compression option | Small (config field) | Low–Medium |

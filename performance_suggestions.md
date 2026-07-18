# Performance Suggestions

Analysis of `grpchook` codebase. Ordered by impact / effort ratio.

---

## 1. File logger runs at `INTERNAL_DEBUG` on every hot-path call ⚠️ HIGH IMPACT

**Root cause:** `get_logger` sets `logger.setLevel(INTERNAL_DEBUG)` (level 5) unconditionally so
the file handler can capture everything. This means every `idebug()` call passes the
logger-level gate and its arguments are formatted + written to disk.

**Correction:** the INTERNAL_DEBUG logger level is intentional (see comment in `logger.py`:
"Logger level must be INTERNAL to allow file handler to capture everything"). Hard-changing
the default to `INFO` removes that documented full-tracing capability entirely — it is not a
free 1-line perf win. Prefer making the *file handler's* level configurable instead of the
shared logger level.

**Hot-path offenders (fire on every message):**

| Location | Call | Frequency |
|---|---|---|
| `BaseServer.DataChannel` while-loop | `idebug("%s: main thread running", peer)` | every 1 s idle **or** every queued message |
| `BaseServer._handle_client_receive` | `idebug("%s: received message: %s", peer, request.metaInfo)` | every inbound message |
| `BaseClient._request_generator` | `idebug("Sending message to server: %s", data)` | every outbound message |
| `BaseClient._request_generator` | `idebug("Sending message with timestamp %s …")` | every outbound message |
| `BaseClient._receive_loop` | `idebug("received data from server: %s", …)` | every inbound message |
| `BaseClient.send_data` | `idebug("Enqueued data %s", …)` | every `send_data()` call |

**Fix:** Add a `file_log_level` parameter to `get_logger` (default `INTERNAL_DEBUG`, unchanged
behavior) and let perf-sensitive users pass `file_log_level=logging.INFO` explicitly. Do not
flip the shared default, since it silently disables an existing, documented feature.

---

## 2. `isinstance` check in `DataRegister.add_data_for_message_name` — NEGLIGIBLE IMPACT (revised)

`add_data_for_message_name` calls `isinstance(data, message_pb2.Message)` on every fan-out.

**Correction:** the original impact estimate was overstated. A single `isinstance` check costs
on the order of tens of nanoseconds — irrelevant next to queue locking, `queue.put`, and
protobuf handling already on this path. It is also not purely "dead weight": since
`add_data_for_message_name` is a public `DataRegister` method (not exclusively fed by the
typed `BaseServer._handle_client_receive` path), the check is the only guard against
non-`Message` objects reaching gRPC's `yield` downstream, where a type error would surface
far from its cause.

**Fix:** No change recommended. If profiling later shows this check is measurably hot,
revisit — do not remove it as a blind perf optimization.

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

**Caveat:** compression must be enabled on both ends to take effect — a server-only or
client-only setting is a no-op for that direction. Document this when exposing the option.

---

## Summary Table

| # | Area | Effort | Impact |
|---|---|---|---|
| 1 | File handler log level configurable | Small (new param, no default change) | High |
| 2 | `isinstance` in fan-out | N/A — not recommended | Negligible |
| 3 | `bytePayload` over `structPayload` | Zero (docs only) | Medium |
| 4 | `max_workers` explicit + warning | Small | Medium |
| 5 | gRPC compression option (both ends) | Small (config field) | Low–Medium |

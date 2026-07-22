# Performance Suggestions

Analysis of `grpchook` codebase. Ordered by impact / effort ratio.

---

## 1. File logger runs at `INTERNAL_DEBUG` on every hot-path call --- PARTIALLY ADDRESSED

**Root cause:** `get_logger` sets `logger.setLevel(INTERNAL_DEBUG)` (level 5) unconditionally so
the file handler can capture everything. This means every `idebug()` call passes the
logger-level gate and its arguments are formatted + written to disk.

**Done:** the worst offender --- logging the *entire* `Message` object (including full
payload) --- is fixed. `BaseClient._request_generator` now logs `data.metaInfo` instead of
`data`. All other hot-path `idebug()` calls already logged `metaInfo` only.

**Still open (deliberately skipped):** a `file_log_level` param on `get_logger` to let users
lower the file handler's level below `INTERNAL_DEBUG` was proposed but not implemented ---
decided against changing the shared logger-level default. Revisit only if profiling shows
the file handler itself (not payload size) is the bottleneck.

---

## 2. `isinstance` check in `DataRegister.add_data_for_message_name` --- NO ACTION (info only)

Negligible cost (tens of ns), and the only guard against non-`Message` objects reaching
gRPC's `yield` downstream. Not revisited --- keep as-is unless profiling proves otherwise.

---

## 3. `structPayload` vs `bytePayload` --- NO ACTION (info only, user-side)

`structPayload` (protobuf `Struct`) serializes as JSON internally; `bytePayload` is raw
bytes. For high-frequency/large payloads, users should serialize themselves (`msgpack`,
`pickle`, `numpy.tobytes()`) and use `bytePayload`. Documentation/guidance only --- no
framework change.

---

## Resolved

- **`max_workers` silent cap** --- `ServerConfig.effective_max_workers` property resolves the
  effective thread count; `BaseServer` warns once when connected clients reach that count
  (next client would stall) and logs the effective value at `serve_forever()` startup.
- **gRPC compression** --- `ServerConfig.compression` / `ClientConfig.compression` fields added,
  wired into `grpc.server(...)` / `stub.DataChannel(...)`. Docs + unit/integration tests
  (`tests/integration/compression/`) cover the one-side-only case: no exception, only that
  direction gets compressed.

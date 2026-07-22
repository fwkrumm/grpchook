Project-specific performance evaluation for grpchook.

---

## 1) Asyncio default event loop (Proactor on Windows)

Status in grpchook: Not applicable today.

Reason:
- grpchook server uses sync grpc.server + ThreadPoolExecutor, not grpc.aio.
- Event-loop choice does not control current DataChannel runtime path.

Effort to adopt:
- High.
- Requires grpc.aio migration of server stream loop and queue/lock internals.

---

## 2) Zero-copy protobuf techniques

Status in grpchook: Partly valid in principle, not true end-to-end in current API.

Reason:
- Current stub path serializes/deserializes protobuf Message objects each hop.
- bytePayload helps avoid Struct overhead, but protobuf framing/parse still happens.

Effort to improve:
- Medium for partial gains (favor bytePayload, reduce object churn, benchmark).
- High for true zero-copy end-to-end (transport/serializer redesign).

---

## 3) Large streaming chunks (512 KB - 2 MB)

Status in grpchook: Correct direction, workload-dependent target.

Reason:
- Larger application messages usually improve throughput by amortizing per-message overhead.
- Exact sweet spot depends on payload type, latency, CPU, compression, and concurrency.

Effort to adopt:
- Low: expose payload-size guidance and benchmark profiles.
- Medium: add built-in chunk/reassembly helpers and safer defaults for large messages.

---

## 4) Streaming RPC over unary

Status in grpchook: Correct and already implemented.

Reason:
- Interface uses one bidirectional stream-stream RPC DataChannel.
- No unary request path in framework core.

Effort to adopt:
- None.

---

## Chunk size control: gRPC setting or TCP?

Short answer: both layers matter, but they control different things.

- Application chunk size (what you send per Message): your code controls this.
- gRPC message limits: configurable via grpc.max_send_message_length and grpc.max_receive_message_length.
- HTTP/2 frame sizing and write buffering: mostly gRPC C-core internals/options, not direct "best chunk" control.
- TCP segmentation: handled by OS/network stack; it will split bytes regardless of your app chunk size.

Practical rule:
- Choose app chunk size by benchmark.
- Set gRPC max message limits high enough for chosen chunk size.
- Do not expect TCP layer to pick optimal app-level chunking for you.

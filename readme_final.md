# grpchook

**grpchook** (gRPC + hook) is a Python framework for building asynchronous gRPC bidirectional-streaming services. Subclass `BaseServer` and `BaseClient`, override the hooks you need — the framework handles all gRPC plumbing.

> **Status: Work in Progress.**
> The project is open source and will remain open source.
> Treat with caution. If you depend on it, **pin your version**.

---

## Table of Contents

- [Disclaimer](#disclaimer)
- [When to Use and When Not to Use grpchook](#when-to-use-and-when-not-to-use-grpchook)
- [Requirements](#requirements)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From Source](#from-source)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Regenerating the gRPC Interface](#regenerating-the-grpc-interface)
- [ToDos & Roadmap](#todos-roadmap)
- [Known Issues & Troubleshooting](#known-issues-troubleshooting)
- [Release History](#release-history)

---
<a name="disclaimer"></a>
<a id="disclaimer"></a>

## Disclaimer

Core concept by a human developer. AI was used to assist with unit and integration tests, examples, documentation, and selected code sections. Core logic has been reviewed by a human; the test suite has not been fully audited — there may be AI-introduced oversights. Please report any issues you find.

This software is provided **"as is"**, without warranty of any kind. The developer is not responsible for any damage, data loss, security vulnerabilities, or other issues that may arise from using this software. **You use it at your own risk.** See [LICENSE.txt](LICENSE.txt) for the full BSD 3-Clause terms.


---
<a name="when-to-use-and-when-not-to-use-grpchook"></a>
<a id="when-to-use-and-when-not-to-use-grpchook"></a>
## When to Use and When Not to Use grpchook

### When to Use grpchook
- You need a simple, Python-based gRPC bidirectional streaming server and client.
- When you want a data exchange blueprint for developers or AI agents to build on top of.
- You want a framework that can be extended with custom hooks for specific events.
- You want to distribute clients to many different machines (e.g. voice recorder, voice to text, text to LLM, and vice versa until the final response is replayed)

### When Not to Use grpchook
- When you need very large number of clients; the threading model may introduce overhead.
- When you do not want client-client communication; grpchook is designed for bidirectional streaming via a server.
- You want a framework that supports multiple programming languages out of the box; grpchook is (currently) Python-only.

---
<a name="requirements"></a>
<a id="requirements"></a>

## Requirements

- Python 3.10 or later
- A dedicated virtual environment is **strongly recommended** — gRPC version conflicts with other packages are grpchook.

---
<a name="installation"></a>
<a id="installation"></a>

## Installation

<a name="from-pypi"></a>
<a id="from-pypi"></a>
### From PyPI

```bash
pip install grpchook
```

<a name="from-source"></a>
<a id="from-source"></a>
### From Source

```bash
git clone https://github.com/fwkrumm/grpchook.git
cd grpchook
pip install -e .
```

---
<a name="quick-start"></a>
<a id="quick-start"></a>

## Quick Start

Refer to [HOW_TO.md](grpchook/assets/HOW_TO.md) for the full API reference and code examples.

---
<a name="examples"></a>
<a id="examples"></a>

## Examples

Runnable examples are available in two locations:

- `examples/` — self-contained, scenario-focused examples
- `tests/integration/` — integration test scenarios covering a broad range of use cases

Run them on a machine with adequate resources; some scenarios are resource-intensive.

---
<a name="regenerating-the-grpc-interface"></a>
<a id="regenerating-the-grpc-interface"></a>


## Regenerating the gRPC Interface

If you modify or freshly cloned the repository `grpchook/message.proto`, regenerate the Python bindings with:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. grpchook/message.proto
```

Note that all clients which connect to a server have to use the same proto schema version i.e. the same proto file. The different signals for the clients must be used in substructures:

```proto
message Payload {
    // For client A
    SomeTypeA paylaodClientA = 1;

	// For client B
    SomeTypeB payloadClientB = 2;

    ...
}

```

---
<a name="todos-roadmap"></a>
<a id="todos-roadmap"></a>

## ToDos & Roadmap

### General
- TBD

### Performance & Stability
- Evaluate replacing the threading model with `asyncio` if the performance gain justifies the API tradeoff.
- Verify behavior when connections are interrupted mid-stream; ensure no ghost threads or queue deadlocks occur.

### Planned Features
- Multi-language client example (e.g., C++ or Rust).
- SSL/TLS usage example.


---
<a name="known-issues-troubleshooting"></a>
<a id="known-issues-troubleshooting"></a>

## Known Issues & Troubleshooting

TBD

---
<a name="release-history"></a>
<a id="release-history"></a>
## Release History


| Version / Git Tag on Master | Description |
|----------------------------|-------------|
| 0.0.1                      | Initial public release. |

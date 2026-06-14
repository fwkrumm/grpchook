# grpchook

**grpchook** (gRPC + hook) is a Python framework for building asynchronous gRPC bidirectional-streaming services. Subclass `BaseServer` and `BaseClient`, override the hooks you need — the framework handles all gRPC plumbing.

> **Status: Work in Progress.**
> The project is open source and will remain open source.
> Treat with caution. If you depend on it, **pin your version**.

---

## Table of Contents

- [Disclaimer](#disclaimer)
- [Requirements](#requirements)
- [Installation](#installation)
  - [From PyPI](#from-pypi)
  - [From Source](#from-source)
- [Quick Start](#quick-start)
- [Examples](#examples)
- [Regenerating the gRPC Interface](#regenerating-the-grpc-interface)
- [Known Issues & Roadmap](#known-issues--roadmap)
- [Release History](#release-history)

---

## Disclaimer

Core concept by a human developer. AI was used to assist with unit and integration tests, examples, documentation, and selected code sections. Core logic has been reviewed by a human; the test suite has not been fully audited — there may be AI-introduced oversights. Please report any issues you find.

This software is provided **"as is"**, without warranty of any kind. The developer is not responsible for any damage, data loss, security vulnerabilities, or other issues that may arise from using this software. **You use it at your own risk.** See [LICENSE.txt](LICENSE.txt) for the full BSD 3-Clause terms.

---

## Requirements

- Python 3.10 or later
- A dedicated virtual environment is **strongly recommended** — gRPC version conflicts with other packages are grpchook.

---

## Installation

### From PyPI

```bash
pip install grpchook
```

### From Source

```bash
git clone https://github.com/fwkrumm/grpchook.git
cd grpchook
pip install -e .
```

---

## Quick Start

Refer to [HOW_TO.md](grpchook/assets/HOW_TO.md) for the full API reference and code examples.

---

## Examples

Runnable examples are available in two locations:

- `examples/` — self-contained, scenario-focused examples
- `tests/integration/` — integration test scenarios covering a broad range of use cases

Run them on a machine with adequate resources; some scenarios are resource-intensive.

---

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

## Known Issues & Roadmap

### Structure
- Project structure needs consolidation — all modules will be moved under the `grpchook` package.
- The documentation is split across multiple how-to files; these will be merged into one.

### Performance & Stability
- Evaluate replacing the threading model with `asyncio` if the performance gain justifies the API tradeoff.
- Verify behavior when connections are interrupted mid-stream; ensure no ghost threads or queue deadlocks occur.

### Planned Features
- Multi-language client example (e.g., C++ or Rust).
- SSL/TLS usage example.

---

## Release History

### 0.0.1
- Initial public release.
- `BaseServer` and `BaseClient` with hook-based subclassing.
- Message routing via `provides`/`requires` and `DataRegister`.
- Schema version check via SHA-256 proto fingerprint.
- High-precision periodic timer (`timedevent`).
- Custom interface support (runtime `.proto` compile and load).
- Integration test suite and usage examples.

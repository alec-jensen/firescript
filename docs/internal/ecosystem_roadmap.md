# firescript Ecosystem Roadmap

This document defines the planned tooling and ecosystem modules around firescript.

It focuses on:
- Build and package workflows
- Standard library growth
- First-party installable packages

It does not define language syntax or compiler internals.

## Ecosystem Architecture

The ecosystem is organized into two layers:
- Standard library modules under `@firescript/std` for stable, portable APIs
- Installable packages for platform-specific or fast-evolving functionality

This split keeps the standard library small and dependable while allowing faster iteration for external integrations.

## kiln

`kiln` is the firescript build system and package manager.

### Responsibilities
- Project initialization and scaffolding: `kiln init`
- Dependency and lockfile management: `kiln add`, `kiln update`, `kiln sync` (after `std.net`)
- Build and execution workflows: `kiln build`, `kiln run`, `kiln test`
- Publishing workflows: `kiln publish`

## Planned Libraries and Packages

### 1. math.linalg (standard library)
Namespace: `@firescript/std.math.linalg`

Scope:
- Vectors and matrices
- Core linear algebra operations
- Common decompositions needed by graphics and simulation workloads

### 2. io.input (standard library)
Namespace: `@firescript/std.io.input`

Scope:
- Keyboard, mouse, and gamepad event handling
- Input state polling APIs
- Event stream interfaces for app and game loops

### 3. cli.args (standard library)
Namespace: `@firescript/std.cli.args`

Scope:
- Command-line argument tokenization and parsing
- Positional arguments, flags, and typed option values
- Validation and help/usage text generation

### 4. net (standard library)
Namespace: `@firescript/std.net`

Scope:
- TCP and UDP socket primitives
- Client/server connection lifecycle APIs
- Address parsing and endpoint helpers

### 5. window (installable package)
Namespace: `@firescript/window`

Scope:
- Window creation and lifecycle
- Display mode, resizing, and window event management
- Cross-platform runtime integration

### 6. graphics (installable package)
Namespace: `@firescript/graphics`

Scope:
- Graphics API bindings
- Buffers, textures, shaders, and pipeline objects
- Render pass and command submission primitives

## Current Baseline (April 2026)

### Confirmed working today
- Compiler pipeline and native codegen run via `python firescript/main.py <source-file>`
- Import parsing and module resolution for local modules
- Standard library import path resolution for `@firescript/std...`
- Existing std modules for `io`, `math`, `constraints`, and `types`
- Broad test coverage for language features, imports, std usage, and semantic errors

### Confirmed missing today
- No `kiln` implementation exists in the repository
- External package imports (`@user/package`) are reserved but not supported
- No `@firescript/std.math.linalg` module exists yet
- `std.io` currently provides printing utilities, not input APIs
- No `@firescript/std.cli.args` module exists yet
- No runtime/std API currently exposes raw command-line arguments (`argv`) to firescript code
- No `@firescript/std.net` module exists yet
- No `@firescript/window` package exists yet
- No `@firescript/graphics` package exists yet
- No ecosystem-specific test suites for kiln, linalg, io.input, cli.args, std.net, window, or graphics

## Milestone Plan With Required Work

### Milestone 1: std.cli.args
Target outcome:
- `@firescript/std.cli.args` provides a stable parser for command-line applications.

Work required:
- Add a runtime-backed std API to read raw process arguments (`argv`) from firescript.
- Define argument value representation and ordering guarantees.
- Define API for parser configuration (positional args, flags, options, defaults).
- Implement tokenizer/parser for argv-style inputs.
- Add typed conversion helpers with clear diagnostics.
- Add help and usage text formatting APIs.

Dependencies and blockers:
- Requires runtime/compiler plumbing to expose process args into firescript.
- No external package or network dependency required.

Tests and validation:
- Add tests validating raw argv access and ordering.
- Add golden tests for common argument patterns.
- Add invalid tests for missing values, unknown flags, and type conversion failures.
- Add matching expected output/error files.

### Milestone 2: kiln foundations
Target outcome:
- A project can be initialized and built through kiln, without network-based package installation.

Work required:
- Define package manifest format and lockfile format.
- Implement local dependency resolution (path/workspace dependencies only).
- Implement deterministic lockfile generation for local dependencies.
- Implement `kiln build` and `kiln run` by invoking existing compiler workflows.
- Integrate `std.cli.args` as the command surface for kiln CLI parsing.
- Implement install/cache layout for reproducible restores.
- Add clear diagnostics for invalid manifests and version conflicts.

Dependencies and blockers:
- Depends on `std.cli.args` for CLI parsing ergonomics and consistency.
- Network-based package installation is blocked until `std.net` exists.
- Registry support also depends on enabling external imports in compiler/import resolution.

Tests and validation:
- Add end-to-end CLI tests for `init`, local `add`, local `sync`, `build`, `run`.
- Add lockfile determinism tests.
- Add negative tests for invalid manifest and conflict handling.

### Milestone 3: std.math.linalg
Target outcome:
- `@firescript/std.math.linalg` exists with stable core vector/matrix functionality.

Work required:
- Add `firescript/std/math/linalg` module structure.
- Implement core operations: vector/matrix construction, dot product, matrix multiply, transpose.
- Define dimension-mismatch behavior and diagnostics.
- Document numeric behavior and precision expectations.

Dependencies and blockers:
- No new package manager functionality required.
- Can be implemented with existing language/compiler features.

Tests and validation:
- Add positive golden tests for vector/matrix operations.
- Add invalid tests for dimension mismatch and invalid construction.
- Add matching expected output/error files.

### Milestone 4: std.io input APIs
Target outcome:
- `@firescript/std.io.input` provides baseline keyboard/mouse input APIs, then gamepad support.

Work required:
- Design input API surface for polling and event-driven patterns.
- Add runtime-level input abstraction for supported platforms.
- Implement input state model (pressed/released/down, cursor position, wheel).
- Define behavior for focus loss, key repeat, and event ordering.

Dependencies and blockers:
- Requires runtime and std implementation work beyond current `print/println` support.
- Must keep low-level directives constrained to std internals.

Tests and validation:
- Add contract tests for state transitions.
- Add integration tests with simulated input events where available.
- Add platform smoke tests with explicit unsupported-platform handling.

### Milestone 5: std.net
Target outcome:
- `@firescript/std.net` provides baseline networking primitives for socket-based applications.

Work required:
- Define API for socket creation, bind/listen/accept, connect, send/receive, and close.
- Implement address and endpoint abstractions for IPv4/IPv6 where supported.
- Define blocking/non-blocking behavior and timeout semantics.
- Implement consistent networking error model and diagnostics.

Dependencies and blockers:
- Requires runtime support for cross-platform socket operations.
- Must define platform-compatibility policy for unsupported features.

Unlocks:
- Enables network-based package installation and registry sync flows in kiln.

Tests and validation:
- Add integration tests for loopback TCP client/server communication.
- Add tests for UDP send/receive behavior.
- Add failure-path tests for connection errors, timeouts, and invalid endpoints.

### Milestone 6: @firescript/window v0
Target outcome:
- Installable window package opens a window and processes lifecycle/events on one backend.

Work required:
- Implement external package import path from source to compile.
- Define package metadata needed for platform-specific artifacts.
- Implement window lifecycle API (create, poll events, resize, close).
- Integrate package build/test flows with kiln.

Dependencies and blockers:
- Requires external package import support (currently not supported).
- Requires packaging/distribution conventions from kiln milestone.

Tests and validation:
- Add integration tests importing and using `@firescript/window`.
- Add window lifecycle smoke tests.
- Add failure tests for backend init and unsupported platforms.

### Milestone 7: @firescript/graphics v0
Target outcome:
- Installable graphics package renders a minimal frame through one backend.

Work required:
- Define graphics API surface (device, buffer, texture, shader, pipeline, pass).
- Implement resource lifetime behavior aligned with firescript ownership semantics.
- Implement one backend and backend abstraction boundary.
- Provide a minimal sample pipeline (clear + draw triangle).

Dependencies and blockers:
- Depends on external package support and kiln package workflows.
- Depends on windowing/surface integration.

Tests and validation:
- Add compile-time API usage tests.
- Add runtime smoke tests for device init and frame submission.
- Add invalid tests for resource/pipeline misuse.

## Status

Planning in progress. Core language/compiler/test infrastructure is active, while ecosystem tooling and libraries in this roadmap are mostly not implemented yet.
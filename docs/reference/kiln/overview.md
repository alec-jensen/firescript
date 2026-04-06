# kiln Package Manager

kiln is the official package manager, build system, and task runner for the Firescript programming language. Its design is heavily inspired by tools like Cargo (Rust) and NPM (Node.js), providing a standardized, zero-configuration way to manage dependencies, compile your code, and run tests.

Instead of invoking the `firescript` compiler manually with dozens of complicated flags, `kiln` orchestrates the entire process.

---

## 1. Quick Start and CLI Commands

kiln provides a simple, verb-based Command Line Interface (CLI):

### Creating a New Project

```sh
# Create a new executable project
kiln new my_app

# Create a new library project
kiln new my_lib --lib
```

This generates the standard project layout and a base `kiln.toml` manifest file.

### Building and Running

```sh
# Compile the project and output the binary to build/
kiln build

# Compile the project with optimizations (Release mode)
kiln build --release

# Compile and immediately run the executable
kiln run
# Pass arguments to the executable:
kiln run -- --my-arg value

# Type-check the project without emitting a binary (fast)
kiln check
```

### Testing and Maintenance

```sh
# Run all tests in the tests/ directory
kiln test

# Clean all generated artifacts from the build/ directory
kiln clean
```

---

## 2. Configuration (`kiln.toml`)

The `kiln.toml` file defines your project's metadata, dependencies, and build profiles. It uses [TOML](https://toml.io/) and acts as the source of truth for the package manager, located at the root of your project.

```toml
[package]
name = "my_project"
version = "0.1.0"
description = "A sample Firescript executable project"
authors = ["Jane Doe <jane@example.com>"]

# The compiler this package is built for (defaults to "firescript")
compiler = "firescript"

# Entry point of the package (defaults to "src/main.fire")
entry = "src/main.fire"

# Path to the license file
license-file = "LICENSE"
```

### Dependencies

The `[dependencies]` section specifies packages and libraries your project requires. kiln supports semantic versioning (`semver`) for package resolution as well as local/remote resolution.

```toml
[dependencies]
# Pull a specific version from the default package registry
http = "1.2.0"

# Pull a dependency directly from a local path relative to kiln.toml
utils = { path = "../utils" }

# Pull a dependency directly from a Git repository
json = { git = "https://github.com/example/json.fire", branch = "main" }
```

### Development Dependencies

The `[dev-dependencies]` section lists packages only required for testing or local development. These dependencies **will not** be bundled or forwarded when another project depends on your package.

```toml
[dev-dependencies]
testing_tools = "0.5.0"
```

### Build Profiles

kiln allows you to configure default compiler arguments for different environments (`[profile.dev]` and `[profile.release]`). If omitted, `kiln` falls back to sane defaults.

```toml
[profile.dev]
# These flags map directly to internal compiler arguments during local runs
emit_deps = true 
check = false
link_args = []

[profile.release]
# Useful for overriding release behavior, such as stripping symbols
emit_deps = false
link_args = ["-Wl,--strip-all"]
```

---

## 3. The Lockfile (`kiln.lock`)

When kiln resolves dependencies, it calculates hashes and exact semantic versions, writing them to an auto-generated `kiln.lock` file.

* **Reproducibility:** This lockfile ensures that any user cloning your repository will build against the exact same dependency tree you did.
* **Do not edit manually:** This file should only be managed by `kiln`.
* **Version control:** It should typically be committed to version control for executable packages, but is often ignored for library packages (to test against the latest compatible upstream versions).

---

## 4. Expected Project Layout

kiln enforces standard conventions for directory layout to minimize the need for manual configuration. As long as you follow this layout, `kiln` won't require overriding paths in `kiln.toml`.

```text
my_project/
â”œâ”€â”€ kiln.toml          # The package manifest
â”œâ”€â”€ kiln.lock          # Auto-generated lockfile (after running `kiln build`)
â”œâ”€â”€ src/               # Main source code directory
â”‚   â”œâ”€â”€ main.fire      # Default entry point for executables
â”‚   â””â”€â”€ lib.fire       # Default entry point for libraries
â”œâ”€â”€ tests/             # Integration and unit tests
â”‚   â””â”€â”€ my_test.fire
â””â”€â”€ build/             # Auto-generated build output directory (gitignored)
```

---

## 5. Under the Hood: Compiler Discovery

Because kiln orchestrates the `firescript` compiler to retrieve artifacts and dependencies, it needs to know where the compiler lives. kiln resolves the compiler using a fallback chain:

1. **Environment Variable:** `FIRESCRIPT_COMPILER` (e.g., `FIRESCRIPT_COMPILER="python /path/to/main.py"`).
2. **Local Dev Fallback:** If `flights/main.py` or `.venv` exists adjacent to kiln, it hooks directly into the local repository (useful for bootstrapped language development!).
3. **PATH Fallback:** Finally, it assumes the compiler was installed globally and invokes `firescript` from the `PATH`.

When kiln executes the compiler, it communicates via JSON diagnostics, making use of the `--message-format=json`, `--emit`, and `--emit-deps` CLI flags internally.

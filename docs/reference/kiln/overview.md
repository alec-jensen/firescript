# kiln Package Manager

> Status: [IN DEVELOPMENT]. kiln exists today as a bootstrap prototype written in firescript at `firescript/tools/kiln/` (CLI skeleton with help text). The commands and behavior described on this page are the design target — most of it is [PLANNED], with the core commands (`new`/`init`, `build`, `run`, `check`, `test`, `clean`) scheduled for the 0.10.0 release and registry features (`publish`, `add`, `sync`, `update`) for 0.11.0. The manifest format is [FCL](../fcl/overview.md) (`kiln.fcl`), not TOML.

kiln is the official package manager, build system, and task runner for the firescript programming language. Its design is heavily inspired by tools like Cargo (Rust) and NPM (Node.js), providing a standardized, zero-configuration way to manage dependencies, compile your code, and run tests.

Instead of invoking the `firescript` compiler manually with dozens of complicated flags, `kiln` orchestrates the entire process.

---

## 1. Quick Start and CLI Commands [PLANNED]

kiln provides a simple, verb-based Command Line Interface (CLI):

### Creating a New Project

```sh
# Create a new executable project
kiln new my_app

# Create a new library project
kiln new my_lib --lib
```

This generates the standard project layout and a base `kiln.fcl` manifest file.

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

## 2. Configuration (`kiln.fcl`) [PLANNED]

The `kiln.fcl` file defines your project's metadata, dependencies, and build profiles. It is written in [FCL (firescript config language)](../fcl/overview.md) and acts as the source of truth for the package manager, located at the root of your project.

See [kiln Manifest](manifest.md) for the manifest format details.

### Dependencies

The dependencies section specifies packages and libraries your project requires. kiln will support semantic versioning (`semver`) for package resolution as well as local/remote resolution — pulling a specific version from the default package registry, from a local path relative to `kiln.fcl`, or directly from a Git repository.

### Development Dependencies

Dev-dependencies list packages only required for testing or local development. These dependencies **will not** be bundled or forwarded when another project depends on your package.

### Build Profiles

kiln will allow configuring default compiler arguments for different environments (dev and release profiles). If omitted, `kiln` falls back to sane defaults.

---

## 3. The Lockfile (`kiln.lock`) [PLANNED]

When kiln resolves dependencies, it calculates hashes and exact semantic versions, writing them to an auto-generated `kiln.lock` file.

* **Reproducibility:** This lockfile ensures that any user cloning your repository will build against the exact same dependency tree you did.
* **Do not edit manually:** This file should only be managed by `kiln`.
* **Version control:** It should typically be committed to version control for executable packages, but is often ignored for library packages (to test against the latest compatible upstream versions).

---

## 4. Expected Project Layout [PLANNED]

kiln enforces standard conventions for directory layout to minimize the need for manual configuration. As long as you follow this layout, `kiln` won't require overriding paths in `kiln.fcl`.

```text
my_project/
├── kiln.fcl           # The package manifest
├── kiln.lock          # Auto-generated lockfile (after running `kiln build`)
├── src/               # Main source code directory
│   ├── main.fire      # Default entry point for executables
│   └── lib.fire       # Default entry point for libraries
├── tests/             # Integration and unit tests
│   └── my_test.fire
└── build/             # Auto-generated build output directory (gitignored)
```

---

## 5. Under the Hood: Compiler Discovery [PLANNED]

Because kiln orchestrates the `firescript` compiler to retrieve artifacts and dependencies, it needs to know where the compiler lives. kiln will resolve the compiler using a fallback chain:

1. **Environment Variable:** `FIRESCRIPT_COMPILER` (e.g., `FIRESCRIPT_COMPILER="python /path/to/main.py"`).
2. **Local Dev Fallback:** If `firescript/main.py` or `.venv` exists adjacent to kiln, it hooks directly into the local repository (useful for bootstrapped language development!).
3. **PATH Fallback:** Finally, it assumes the compiler was installed globally and invokes `firescript` from the `PATH`.

When kiln executes the compiler, it communicates via JSON diagnostics, making use of the `--message-format=json`, `--emit`, and `--emit-deps` CLI flags internally.

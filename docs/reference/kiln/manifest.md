# kiln Manifest and Configuration Format

The Firescript package manager, `kiln`, uses TOML (Tom's Obvious, Minimal Language) for its configuration. The primary file is `kiln.toml`, which must be located at the root of a kiln-managed project alongside the source code.

## Package Manifest (`kiln.toml`)

The `kiln.toml` file defines your project's metadata, dependencies, and build profiles. It acts as the source of truth for the package manager.

```toml
[package]
name = "my_project"
version = "0.1.0"
description = "A sample Firescript executable project"
authors = ["Jane Doe <jane@example.com>"]

# The compiler this package is built for (defaults to "firescript")
compiler = "firescript"

# Entry point of the package. 
# Defaults to "src/main.fire" for binaries or "src/lib.fire" for libraries.
entry = "src/main.fire"

# Path to the license file
license-file = "LICENSE"
```

### Dependencies

The `[dependencies]` section specifies packages and libraries your project requires to build and run. kiln supports semantic versioning (`semver`) for package resolution.

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

## Lockfile (`kiln.lock`)

When kiln resolves dependencies, it calculates hashes and exact semantic versions, writing them to an auto-generated `kiln.lock` file.

* **Reproducibility:** This lockfile ensures that any user cloning your repository will build against the exact same dependency tree you did.
* **Do not edit manually:** This file should only be managed by `kiln`.
* **Version control:** It should typically be committed to version control for executable packages (bins).

## Expected Project Layout

kiln enforces standard conventions for directory layout to minimize the need for manual configuration.

```text
my_project/
├── kiln.toml          # The package manifest
├── kiln.lock          # Auto-generated lockfile (after running `kiln build`)
├── src/               # Main source code directory
│   ├── main.fire      # Default entry point for executables
│   └── lib.fire       # Default entry point for libraries
├── tests/             # Integration and unit tests
│   └── my_test.fire
└── build/             # Auto-generated build output directory (gitignored)
```

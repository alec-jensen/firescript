# kiln Manifest and Configuration Format

> Status: [PLANNED]. The kiln manifest format is [FCL (firescript config language)](../fcl/overview.md), which is itself in development. The exact manifest schema below is illustrative design direction and will be finalized alongside kiln in the 0.10.0 release. (An earlier design used TOML; that has been superseded by FCL.)

The firescript package manager, `kiln`, uses FCL for its configuration. The primary file is `kiln.fcl`, which must be located at the root of a kiln-managed project alongside the source code.

## Package Manifest (`kiln.fcl`)

The `kiln.fcl` file defines your project's metadata, dependencies, and build profiles. It acts as the source of truth for the package manager.

```fcl
// Illustrative future schema
class Package {
    string name = "my_project"
    string version = "0.1.0"
    string description = "A sample firescript executable project"
    [string] authors = ["Jane Doe <jane@example.com>"]

    // The compiler this package is built for (defaults to "firescript")
    string compiler = "firescript"

    // Entry point of the package.
    // Defaults to "src/main.fire" for binaries or "src/lib.fire" for libraries.
    string entry = "src/main.fire"

    // Path to the license file
    string licenseFile = "LICENSE"
}
```

### Dependencies

The dependencies section will specify packages and libraries your project requires to build and run. kiln will support semantic versioning (`semver`) for package resolution, plus local-path and Git dependencies:

- A specific version from the default package registry (e.g., `http = "1.2.0"`)
- A local path relative to `kiln.fcl`
- A Git repository URL with a branch or tag

### Development Dependencies

Dev-dependencies list packages only required for testing or local development. These dependencies **will not** be bundled or forwarded when another project depends on your package.

### Build Profiles

kiln will allow configuring default compiler arguments for different environments (dev and release profiles). If omitted, `kiln` falls back to sane defaults.

## Lockfile (`kiln.lock`)

When kiln resolves dependencies, it calculates hashes and exact semantic versions, writing them to an auto-generated `kiln.lock` file.

* **Reproducibility:** This lockfile ensures that any user cloning your repository will build against the exact same dependency tree you did.
* **Do not edit manually:** This file should only be managed by `kiln`.
* **Version control:** It should typically be committed to version control for executable packages (bins).

## Expected Project Layout

kiln enforces standard conventions for directory layout to minimize the need for manual configuration.

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

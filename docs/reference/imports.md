# Imports

> Status: Modules and import resolution are planned but not yet implemented. The syntax below is reserved and may evolve as the compiler gains module support.

firescript uses an explicit, Java-inspired import system for organizing code across files and (in the future) external packages. All imports must specify full paths; there is no implicit or relative import behavior.

## Import Syntax

### Importing local modules

- Import an entire module:

```firescript
import src.utils.utils
```

- Import a specific symbol from a module:

```firescript
import src.utils.utils.helper
```

- Import multiple symbols from a module:

```firescript
import src.utils.utils.{helper, CONSTANT}
```

- Import all symbols from a module (allowed, but discouraged for explicitness):

```firescript
import src.utils.utils.*
```

- Aliasing imports (optional):

```firescript
import src.utils.utils.helper as help
import src.utils.utils as Utils
```

### Importing external packages (reserved)

These forms are reserved for future package management and standard library support:

```firescript
import @user/package
import @firescript/std
```

## Paths and Resolution

- Import paths are absolute from the project root. For example, `src.utils.utils` maps to `{project-root}/src/utils/utils.fire`.
- Relative imports (e.g., `import ../utils`) are not permitted.
- There are no default or magic imports—every symbol must be explicitly imported.
- The `.fire` extension is omitted in import statements but always resolves to a file with that extension.
- A configurable import root may be supported in the future; the default is the project root.

## Examples

Given the structure:

```
src/
	main.fire
	utils/
		utils.fire
	enums/
		colors.fire
```

From `colors.fire`, to import a function `helper` from `utils.fire`:

```firescript
import src.utils.utils.helper
```

To import the entire module:

```firescript
import src.utils.utils
```

To import multiple symbols:

```firescript
import src.utils.utils.{helper, CONSTANT}
```

## Wildcards, Aliasing, and Explicitness

- Wildcards via `*` are allowed but discouraged; prefer explicit symbol lists.
- Aliasing is available for both modules and symbols to improve clarity and resolve naming conflicts.
- Explicitness is required—no implicit re-exports or default imports.

## Reserved & Future Features

- `import @user/package` is reserved for future package management.
- `import @firescript/std` is reserved for standard library modules.

## Best Practices

1. Prefer explicit symbol imports over wildcards.
2. Avoid broad module imports unless you intentionally need many symbols.
3. Use aliasing when names conflict or when a shorter local name improves readability.

## Not Supported

- Relative imports
- Implicit “import everything” behavior
- Omitting paths or symbols

## Syntax Summary

| Syntax                                | Meaning                                   |
|---------------------------------------|-------------------------------------------|
| `import src.utils.utils`              | Import entire module                      |
| `import src.utils.utils.helper`       | Import a specific symbol                  |
| `import src.utils.utils.{a, b}`       | Import multiple symbols                   |
| `import src.utils.utils.*`            | Import all symbols (discouraged)          |
| `import src.utils.utils.helper as h`  | Alias an imported symbol                  |
| `import @user/package`                | External package (future)                 |

## Implementation Notes

- Import statements are only valid at the top level of a source file.
- The compiler will resolve imports from the project root and report missing files or symbols.
- Cyclic imports should be detected and reported as errors.

## Implementation Status

- ❌ Modules and import resolution are planned but not implemented in the current compiler.
- ✅ Syntax is reserved and documented here for future implementation.


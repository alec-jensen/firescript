# Imports

firescript uses an explicit, Java-inspired import system for organizing code across files and (in the future) external packages. All imports must specify full paths; there is no implicit or relative import behavior. A module only exposes symbols that it explicitly exports.

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

Only exported symbols are eligible for import, including wildcard imports. Module-private top-level declarations remain visible only inside the defining file.

- Aliasing a symbol import ([IMPLEMENTED]): call sites using the alias resolve to the imported symbol.

```firescript
import src.utils.utils.helper as help
```

- Aliasing a whole-module import ([PLANNED] — parsed, but qualified access through the alias is not yet implemented):

```firescript
import src.utils.utils as Utils
```

### Importing standard library modules and external packages

Standard library imports under the `@firescript/std` namespace are implemented. The `@user/package` form is reserved for future package management:

```firescript
import @firescript/std.io.println;   // implemented
import @user/package                 // reserved for future package management
```

These imports can be used the same as local imports, like so:

```firescript
import @firescript/std.math

import @firescript/std.math.sqrt

import @firescript/std.{math, io}

import @firescript/std.math.*

import @firescript/std.math.sqrt as squareRoot
```

## Paths and Resolution

The project root is the base for all import paths. It is the folder containing the entry point of the program (e.g., `src/main.fire`). The compiler resolves import paths from this root.

- Import paths are absolute from the project root. For example, `src.utils.utils` maps to `{project-root}/src/utils/utils.fire`.
- Relative imports (e.g., `import ../utils`) are not permitted.
- There are no default or magic imports—every symbol must be explicitly imported.
- Files do not automatically expose their top-level declarations; export them first if they should be imported elsewhere.
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
| `import src.utils.utils.helper as h`  | Alias an imported symbol (planned)        |
| `import @firescript/std.io.println;`  | Standard library import                   |
| `import @user/package`                | External package (future)                 |

## Implementation Notes

- Import statements are only valid at the top level of a source file.
- The compiler will resolve imports from the project root and report missing files or symbols.
- Cyclic imports should be detected and reported as errors.

## Implementation Status

- [IMPLEMENTED] Import syntax parsing
- [IMPLEMENTED] Module resolution and dependency loading
- [IMPLEMENTED] Multi-module compilation with merged AST
- [IMPLEMENTED] Wildcard imports (`import module.*`)
- [IMPLEMENTED] Symbol imports (`import module.{a, b}`)
- [IMPLEMENTED] Cyclic import detection
- [IMPLEMENTED] Standard library imports (`import @firescript/std...`)
- [IMPLEMENTED] Symbol import aliases (`import module.symbol as alias`)
- [PLANNED] Module aliases and qualified access (e.g., `import module as M`, `M.helper()`)
- [PLANNED] External packages (`@user/package`)

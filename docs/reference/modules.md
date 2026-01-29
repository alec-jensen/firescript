# Modules

A **module** is a unit of firescript code that you can import. Modules are similar to Python modules and can be:

- A **single source file**, or
- A **directory** that contains firescript source files.

A **package** is something you can install from the package manager. Packages are modules, but not all modules are packages.

A **library** is a package included with the Firescript installation.

## Directory Modules and init.fire

If a directory contains an `init.fire` file, that file defines the module for the directory name.

Example layout:

```
math/
  init.fire
  trig.fire
```

- The contents of `math/init.fire` are imported with:

```firescript
import math
```

- The contents of `math/trig.fire` are imported with:

```firescript
import math.trig
```

## Nested Modules

Modules can be nested by creating subdirectories with their own source files:

```
math/
  init.fire
  trig.fire
  geometry/
    init.fire
    angles.fire
```

Examples:

```firescript
import math
import math.trig
import math.geometry
import math.geometry.angles
```

## Definitions

- **Module**: A single `.fire` file, or a directory containing `.fire` files.
- **Package**: An installable module from the package manager.
- **Rule**: All packages are modules, but not all modules are packages.

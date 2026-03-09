# Project Structure

## File Names

firescript source files use the `.fire` extension.

File and directory names become the dotted module path used in `import` statements, so they must be valid identifiers: start with a letter (`a`–`z`, `A`–`Z`) or underscore, and contain only letters, digits, and underscores thereafter. Hyphens, spaces, dots, and other special characters are not supported.

Dots are the module path separator — `import http.utils` resolves to the file `http/utils.fire`. A file literally named `http.utils.fire` cannot be referenced by any import statement.

| Valid | Invalid |
|---|---|
| `math.fire` | `my-math.fire` |
| `http_client.fire` | `http client.fire` |
| `utils2.fire` | `2utils.fire` |
| | `http.utils.fire` (dot in stem) |

## init.fire

say you have the following project structure:

```
my_project/
├── src/
│   ├── main.fire
│   └── math
│       └── constants.fire
```

and you wanted to have functions directly available on `math`. You would create an `init.fire` file in the `math` directory:

```my_project/
├── src/
│   ├── main.fire
│   └── math
│       ├── init.fire
│       └── constants.fire
```

The `init.fire` file could look like this:

```firescript
// math/init.fire
int32 add(int32 a, int32 b) {
    return a + b;
}
```

Now, in your `main.fire`, you can import the `math` module and use the `add` function directly:

```firescript// main.fire
import math.add;

int32 result = add(5, 10);
```
# Types & Variables

**Note:** The generic placeholder `T` and declarations without an initializer are not supported by the compiler. Built-in Copyable types (`intN`, `floatN`, `bool`, `char`) are stack-allocated. Owned types (`string`, arrays, user-defined classes) are heap-allocated with move semantics.

## Types

Types are defined in the [Type System](type_system.md) documentation.

## Naming Rules

All names in firescript — variables, function parameters, functions, and constraints — follow the same rule:

- Must begin with a letter (`a`–`z`, `A`–`Z`) or an underscore (`_`).
- After the first character, any combination of letters, digits (`0`–`9`), and underscores is allowed.
- Case-sensitive: `score`, `Score`, and `SCORE` are three distinct names.
- Length is not restricted.
- Must not be a reserved keyword or type name (see table below).

In regex form: `[a-zA-Z_][a-zA-Z0-9_]*`

### Valid examples

```firescript
x: int32 = 0;
_private: int32 = 1;
camelCase: int32 = 2;
SCREAMING_SNAKE: int32 = 3;
value42: int32 = 4;
__double_under: int32 = 5;
```

### Invalid examples

```firescript
42value: int32 = 0;   // cannot start with a digit
my-var: int32 = 0;    // hyphens are not allowed
my var: int32 = 0;    // spaces are not allowed
return: int32 = 0;    // reserved keyword
int32: int32 = 0;     // reserved type name
```

### Reserved keywords and type names

The following words are reserved and cannot be used as identifiers:

| Category | Words |
|---|---|
| Control flow | `if` `elif` `else` `while` `for` `in` `break` `continue` `return` `ternary` `yield` |
| Declarations | `class` `constraint` `directive` `generator` |
| Modifiers | `const` `copyable` `static` `mut` `owned` |
| Other keywords | `import` `export` `from` `as` `new` |
| Primitive types | `int8` `int16` `int32` `int64` `uint8` `uint16` `uint32` `uint64` `float32` `float64` `float128` `bool` `string` `void` |
| Literals | `true` `false` `null` |

The `char` type name is also reserved in type positions.

## Declaration and Initialization

Variables in firescript must be declared with an explicit type and initialized in the same statement:

```firescript
age: int8 = 30;
name: string = "Alice";
isRegistered: bool = false;
```

### Type Inference

firescript does not support automatic type inference:

```firescript
var score = 95;  // Not supported - must specify the type explicitly
score: int8 = 95;  // Supported
```

### Constants

Use the `const` keyword to declare immutable variables:

```firescript
const MAX_USERS: int8 = 100;
const APP_VERSION: string = "1.0.0";
```

Constants must be initialized when declared and cannot be reassigned later:

```firescript
const PI: float32 = 3.14;
PI = 3.14159;  // Error: cannot reassign a constant
```

## Nullability [IMPLEMENTED]

By default, variables cannot be assigned `null`. A trailing `?` after the variable name explicitly allows it to hold `null`:

```firescript
username: string? = null;  // Valid
password: string = null;   // Invalid - non-nullable type cannot hold null
```

Attempting to use a nullable variable without checking for null may result in runtime errors:

```firescript
import @firescript/std.io.print;

message: string? = null;

// Safe access pattern
if (message != null) {
    print(message);
}
```

## Implementation Status

Variable declaration and initialization is fully supported for all primitive types and user-defined classes (including generic classes from the standard library such as `Tuple<T, U>`). Constants and nullability are supported.
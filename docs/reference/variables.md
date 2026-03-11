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
int32 x = 0;
int32 _private = 1;
int32 camelCase = 2;
int32 SCREAMING_SNAKE = 3;
int32 value42 = 4;
int32 __double_under = 5;
```

### Invalid examples

```firescript
int32 42value = 0;   // cannot start with a digit
int32 my-var = 0;    // hyphens are not allowed
int32 my var = 0;    // spaces are not allowed
int32 return = 0;    // reserved keyword
int32 int32 = 0;     // reserved type name
```

### Reserved keywords and type names

The following words are reserved and cannot be used as identifiers:

| Category | Words |
|---|---|
| Control flow | `if` `elif` `else` `while` `for` `in` `break` `continue` `return` `ternary` |
| Declarations | `class` `constraint` `directive` `generator` |
| Modifiers | `const` `nullable` `copyable` `static` |
| Other keywords | `import` `from` `as` `new` |
| Primitive types | `int8` `int16` `int32` `int64` `uint8` `uint16` `uint32` `uint64` `float32` `float64` `float128` `bool` `string` `void` |
| Literals | `true` `false` `null` |

## Declaration and Initialization

Variables in firescript must be declared with an explicit type and initialized in the same statement:

```firescript
int8 age = 30;
string name = "Alice";
bool isRegistered = false;
```

### Type Inference

firescript does not support automatic type inference:

```firescript
var score = 95;  // Not supported - must specify the type explicitly
int8 score = 95;  // Supported
```

### Constants

Use the `const` keyword to declare immutable variables:

```firescript
const int8 MAX_USERS = 100;
const string APP_VERSION = "1.0.0";
```

Constants must be initialized when declared and cannot be reassigned later:

```firescript
const float32 PI = 3.14;
PI = 3.14159;  // Error: cannot reassign a constant
```

## Nullability

By default, variables cannot be assigned `null`. The `nullable` keyword explicitly allows a variable to hold `null`:

```firescript
nullable string username = null;  // Valid
string password = null;           // Invalid - non-nullable type cannot hold null
```

Attempting to use a nullable variable without checking for null may result in runtime errors:

```firescript
import @firescript/std.io.{print};\n\nnullable string message = null;

// Safe access pattern
if (message != null) {
    print(message);
}
```

## Implementation Status

Variable declaration and initialization is fully supported for all primitive types and user-defined classes (including generic classes from the standard library such as `Tuple<T, U>`). Constants and nullability are supported.
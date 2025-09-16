# Types & Variables

**Note:** Tuple types, the generic placeholder `T`, and declarations without an initializer are not supported by the compiler. Only built-in TC types (`int`, `float`, `double`, `bool`, `string`, `char`) are fully implemented.

## Types

Types are defined in the [Type System](type_system.md) documentation.

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
nullable string message = null;

// Safe access pattern
if (message != null) {
    print(message);
}
```

## Implementation Status

Variable declaration and initialization is fully supported for some built-in TC types. User-defined types and tuples are planned for future versions. Constants and nullability are also planned features.
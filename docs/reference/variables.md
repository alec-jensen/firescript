# Types & Variables

**Note:** Tuple types, the generic placeholder `T`, and declarations without an initializer are not supported by the compiler. Only built-in primitive types (`int`, `float`, `double`, `bool`, `string`, `char`) are fully implemented.

## Primitive Types

firescript supports several built-in primitive types. For detailed information about the type system, see the [Type System](type_system.md) documentation.

### Numeric Types

- `int`: Integer numbers (64-bit signed)

```firescript
int count = 42;
int largeNumber = 9223372036854775807;  // 64-bit integer
```

- `float`: Single-precision floating-point numbers

```firescript
float price = 19.99;
float smallValue = 0.000001;
```

- `double`: Double-precision floating-point numbers

```firescript
double pi = 3.14159265359;
double scientificNotation = 6.022e23;  // Scientific notation
```

### Boolean Type

- `bool`: Boolean values (`true` or `false`)

```firescript
bool isActive = true;
bool hasPermission = false;
```

### Text Types

- `string`: Text strings, enclosed in double quotes

```firescript
string greeting = "Hello, world!";
string emptyString = "";
string multiline = "This is a
multi-line string";
```

- `char`: Single characters, represented as strings internally

```firescript
char letter = "A";
char symbol = "*";
```

## Declaration and Initialization

Variables in firescript must be declared with an explicit type and initialized in the same statement:

```firescript
int age = 30;
string name = "Alice";
bool isRegistered = false;
```

### Type Inference

firescript does not support automatic type inference:

```firescript
var score = 95;  // Not supported - must specify the type explicitly
int score = 95;  // Supported
```

### Constants

Use the `const` keyword to declare immutable variables:

```firescript
const int MAX_USERS = 100;
const string APP_VERSION = "1.0.0";
```

Constants must be initialized when declared and cannot be reassigned later:

```firescript
const float PI = 3.14;
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

All primitive types are fully supported in the current compiler. The following features are not yet implemented:

- Tuple operations (creation, access, manipulation)
- Generic type placeholders and type parameters
- Type inference
- Declaration without initialization

For more detailed information about the type system, including type conversions, type compatibility, and advanced type features, please refer to the [Type System](type_system.md) documentation.

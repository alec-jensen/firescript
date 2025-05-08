# Types & Variables

**Note:** Tuple types, the generic placeholder `T`, and declarations without an initializer are not supported by the compiler. Only built-in primitive types (`int`, `float`, `double`, `bool`, `string`, `char`) are fully implemented.

## Primitive Types

firescript supports the following built-in primitive types:

### Numeric Types

- `int`: Integer numbers with arbitrary precision

  ```firescript
  int count = 42
  int largeNumber = 9223372036854775807  // 64-bit integer
  ```

- `float`: Single-precision floating-point numbers (32-bit)

  ```firescript
  float price = 19.99
  float smallValue = 0.000001
  ```

- `double`: Double-precision floating-point numbers (64-bit)

  ```firescript
  double pi = 3.14159265359
  double scientificNotation = 6.022e23  // Scientific notation
  ```

### Boolean Type

- `bool`: Boolean values (`true` or `false`)

  ```firescript
  bool isActive = true
  bool hasPermission = false
  ```

### Text Types

- `string`: Text strings, enclosed in double quotes

  ```firescript
  string greeting = "Hello, world!"
  string emptyString = ""
  string multiline = "This is a
  multi-line string"
  ```

- `char`: Single characters, represented as strings internally

  ```firescript
  char letter = "A"
  char symbol = "*"
  ```

### Complex Types (Not Yet Fully Implemented)

- `tuple<T1, T2, …>`: Heterogeneous collection of values

  ```firescript
  tuple<int, string> person = (30, "John")
  ```

- Generic placeholder: `T`

  ```firescript
  // Example syntax when implemented
  T getValue<T>(T defaultValue) {
      return defaultValue
  }
  ```

## Declaration and Initialization

Variables in firescript must be declared with an explicit type and initialized in the same statement:

```firescript
int age = 30
string name = "Alice"
bool isRegistered = false
```

### Type Inference

firescript does not currently support automatic type inference:

```firescript
var score = 95  // Not supported - must specify the type explicitly
int score = 95  // Supported
```

### Constants

Use the `const` keyword to declare immutable variables:

```firescript
const int MAX_USERS = 100
const string APP_VERSION = "1.0.0"
```

Constants must be initialized when declared and cannot be reassigned later:

```firescript
const float PI = 3.14
PI = 3.14159  // Error: cannot reassign a constant
```

## Nullability

By default, variables cannot be assigned `null`. The `nullable` keyword explicitly allows a variable to hold `null`:

```firescript
nullable string username = null  // Valid
string password = null           // Invalid - non-nullable type cannot hold null
```

Attempting to use a nullable variable without checking for null may result in runtime errors:

```firescript
nullable string message = null

// Safe access pattern
if (message != null) {
    print(message)
}
```

## Type Conversion

firescript provides built-in functions for type conversion:

```firescript
int number = 42
string numberAsString = toString(number)  // "42"

string value = "123"
int parsed = toInt(value)                 // 123
float floatValue = toFloat(value)         // 123.0
double doubleValue = toDouble(value)      // 123.0
bool boolValue = toBool("true")           // true
```

## Type Checking

The `typeof()` built-in function returns the type of a value as a string:

```firescript
string type = typeof(42)         // "int"
print(typeof(true))              // Prints: "bool"
print(typeof("hello"))           // Prints: "string"
```

## Example: Working with Different Types

```firescript
// Integer arithmetic
int a = 10
int b = 3
int sum = a + b          // 13
int difference = a - b   // 7
int product = a * b      // 30
int quotient = a / b     // 3 (integer division)
int remainder = a % b    // 1

// Floating point arithmetic
float x = 10.5
float y = 2.5
float result = x / y     // 4.2

// String operations
string firstName = "John"
string lastName = "Doe"
string fullName = firstName + " " + lastName  // "John Doe"

// Boolean logic
bool hasAccount = true
bool isAdmin = false
bool hasAccess = hasAccount && isAdmin  // false (logical AND)
bool canLogin = hasAccount || isAdmin   // true (logical OR)
bool isLocked = !hasAccount             // false (logical NOT)
```

## Implementation Status

All primitive types are fully supported in the current compiler. The following features are not yet implemented:

- Tuple operations (creation, access, manipulation)
- Generic type placeholders and type parameters
- Type inference
- Declaration without initialization

# Type System in firescript

> firescript employs a static type system to enhance code reliability and catch errors early during the compilation phase. This means that the type of every variable and expression is checked before the code is run.

## Built-in Types

firescript provides several fundamental data types. These are all Copyable types:

* Numeric Types:
  * **`int8`**: 8-bit signed integer
  * **`int16`**: 16-bit signed integer
  * **`int32`**: 32-bit signed integer
  * **`int64`**: 64-bit signed integer
  * **`uint8`**: 8-bit unsigned integer
  * **`uint16`**: 16-bit unsigned integer
  * **`uint32`**: 32-bit unsigned integer
  * **`uint64`**: 64-bit unsigned integer
  * **`float32`**: 32-bit floating point number
  * **`float64`**: 64-bit floating point number
  * **`float128`**: 128-bit floating point number
* **`bool`**: Represents boolean values, either `true` or `false`. Example: `bool isActive = true;`
* **`string`**: Represents sequences of characters. Example: `string message = "Hello, World!";`
* **`char`**: Represents a single character. (Note: Currently handled similarly to strings in some contexts, formal `char` type might be refined). Example: `char initial = "A";`
* **`void`**: Represents the absence of a type, primarily used as the return type for functions that do not return a value.

## Type Semantics

### Integer Type (`intN` and `uintN`)

The `intN` types in firescript represent N-bit signed integers, while the `uintN` types represent N-bit unsigned integers.

```firescript
int8 small = 42;
int64 large = 9223372036854775807;  // Large integers are supported
int64 calculation = (small + large) * 2;  // Arithmetic operations
```

Integers support the following operations:

* Arithmetic: `+`, `-`, `*`, `/`, `%` (modulo), `**` (power)
* Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
* Bit manipulation (planned but not yet implemented): `&`, `|`, `^`, `~`, `<<`, `>>`

#### Integer Literals

Integer literals can be made more readable using underscores:

```firescript
int32 million = 1_000_000;  // One million
int64 bigNumber = 9_223_372_036_854_775_807;  // Large integer
```

Integer literals can be specified in decimal, hexadecimal, binary, or octal formats:

```firescript
int8 decimal = 42;        // Decimal
int8 hex = 0x2A;          // Hexadecimal
int8 binary = 0b00101010; // Binary
int8 octal = 0o52;        // Octal
```

Integer literals by default will be inferred as `int32` unless specified otherwise.
To specify a different integer type, you can use a suffix:

```firescript
int8 small = 42i8;
int16 medium = 30000i16;
int64 large = 9223372036854775807i64;
uint8 usmall = 255u8;
uint16 umedium = 60000u16;
uint64 ularge = 18446744073709551615u64;
```

You can define a base and a suffix together:

```firescript
int8 hexSmall = 0x2Ai8;
uint16 binMedium = 0b111010100110u16;
```

#### Integer Overflow and Underflow Behavior

For all fixed-size integer types (`intN` and `uintN`), arithmetic operations that exceed the representable range will throw an error at runtime. This is to prevent silent overflow/underflow issues.

```firescript
int8 max = 127i8;
int8 overflow = max + 1i8;  // Runtime error: Integer overflow
```

Overflows that can be detected at compile-time (e.g., constant expressions) will result in a compile-time error.

```firescript
int8 compileTimeOverflow = 128i8;  // Compile-time error: Integer overflow
```

### Floating Point Types (`floatN`)

The `floatN` types represent N-bit floating point numbers.

```firescript
float32 simpleDecimal = 3.14;
float64 highPrecision = 3.141592653589793;
```

Floating point numbers support:

* Arithmetic: `+`, `-`, `*`, `/`, `**` (power)
* Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`

#### Floating Point Literals

Floating point literals can be specified in decimal or scientific notation:

```firescript
float32 decimal = 3.14f32;        // Decimal
float64 scientific = 2.71828e0f64; // Scientific notation
```

Floating point literals by default will be inferred as `float32` unless specified otherwise.
To specify a different floating point type, you can use a suffix:

```firescript
float32 f32Value = 3.14f32;
float64 f64Value = 3.14f64;
float128 f128Value = 3.14f128;
```

#### Special Floating Point Values

Floating point types support special values such as `NaN` (Not a Number), `Infinity`, and `-Infinity`:

```firescript
float32 notANumber = 0.0f32 / 0.0f32;  // NaN
float64 positiveInfinity = 1.0f64 / 0.0f64;  // Infinity
float64 negativeInfinity = -1.0f64 / 0.0f64; // -Infinity
```

#### Floating Point Overflow and Underflow Behavior

Floating point operations that exceed the representable range will result in `Infinity` or `-Infinity`, while operations resulting in values too close to zero will result in `0.0`. Operations resulting in undefined values will yield `NaN`.

```firescript
float32 large = 3.4e38f32 * 10.0f32;  // Results in Infinity
float32 small = 1.0e-38f32 / 10.0f32; // Results in 0.0
float32 undefined = 0.0f32 / 0.0f32;      // Results in NaN
```

### Boolean Type (`bool`)

The `bool` type has only two possible values: `true` and `false`. It's commonly used in conditional expressions.

```firescript
bool userLoggedIn = true;
bool hasPermission = false;

// Boolean operations
bool canAccess = userLoggedIn && hasPermission;  // Logical AND
bool needsAttention = !userLoggedIn || !hasPermission;  // Logical OR and NOT
```

Boolean values support:

* Logical operations: `&&` (AND), `||` (OR), `!` (NOT)
* Comparison: `==`, `!=`

### String Type (`string`)

The `string` type represents sequences of characters. Strings in firescript are immutable.

```firescript
string greeting = "Hello";
string name = "World";
string message = greeting + ", " + name + "!";  // String concatenation with +

// Multi-line strings
string paragraph = "This is a
multi-line
string";
```

Strings support:

* Concatenation: `+`
* Comparison: `==`, `!=`

### Character Type (`char`)

The `char` type represents a single character and is currently implemented as a string with length 1.

```firescript
char letter = "A";
char digit = "7";
char newline = "\n";  // Special character
```

### Arrays

Arrays are fixed-size ordered collections of elements of the same type.

#### Declaration and Initialization

```firescript
// With initial values
int8[5] numbers = [1, 2, 3, 4, 5];
string[3] fruits = ["apple", "banana", "cherry"];
```

#### Array Operations

```firescript
int8[3] scores = [85, 92, 78];

// Accessing elements (zero-based indexing)
int8 firstScore = scores[0];  // 85

// Modifying elements
scores[1] = 95;  // Array becomes [85, 95, 78]

// Array properties
int8 count = scores.length;  // 3
```

## Nullability

By default, variables cannot hold the value `null`. To allow a variable to be assigned `null`, you must explicitly declare it as `nullable`.

### Declaring Nullable Variables

```firescript
nullable string username = null;  // Allowed
string title = "Default";

// title = null;  // Error: Cannot assign null to non-nullable type 'string'

username = "John";  // Can be assigned a non-null value later
```

### Working with Nullable Values

When working with nullable variables, it's important to check for null before using them:

```firescript
nullable string data = null;

// Safe pattern
if (data != null) {
    print(data);
}

// Could cause a runtime error if not checked
print(data);  // Might try to print null
```

## Type Compatibility and Conversions

firescript has strict typing rules but provides explicit conversion functions for common type conversions.

### Built-in Type Conversion Functions

```firescript
// String to numeric conversions
string numStr = "42";
int8 num = toInt(numStr);           // 42
float32 floatVal = toFloat("3.14");  // 3.14
float64 doubleVal = toDouble("2.71828");  // 2.71828

// Numeric to string conversions
string strFromInt = toString(42);      // "42"
string strFromFloat = toString(3.14);  // "3.14"

// Boolean conversions
bool boolValue = toBool("true");  // true
string strFromBool = toString(false);  // "false"

// Character conversion
char first = toChar("Hello");  // "H" - first character of string
```

### Implicit Type Conversions

firescript generally does not perform implicit type conversions, with some exceptions:

1. In binary numeric operations (`+`, `-`, `*`, `/`, etc.) between different numeric types:
   * If one operand is `floatN`, the result is `floatN`
   * If one operand is `floatN` and the other is `intN`, the result is `floatN`

```firescript
int8 intVal = 5;
float32 floatVal = 2.5;
float32 doubleVal = 3.14;

float32 result1 = intVal + floatVal;    // Result is 7.5f32
float32 result2 = floatVal * doubleVal;  // Result is 7.85f32
```

2. String concatenation with `+` will convert non-string values to strings:

```firescript
string message = "Count: " + 42;  // "Count: 42"
string status = "Active: " + true;  // "Active: true"
```

## Type Checking and Enforcement

The firescript parser includes a type-checking phase that runs after the initial syntax parsing.

### Static Type Checking

1. **Variable Declarations**: When you declare a variable (`int8 x = 5;`), the type checker verifies that the type of the initializer (`5`, which is `int8`) matches the declared type (`int8`).

2. **Assignments**: When assigning a value to an existing variable (`x = 10;`), the checker ensures the assigned value's type is compatible with the variable's declared type.

3. **Expressions**: Operators (`+`, `-`, `*`, `/`, `==`, `>`, etc.) are checked to ensure they are used with compatible operand types. For example, arithmetic operators generally require numeric types (`intN`, `floatN`), while `+` can also be used for string concatenation. The result type of an expression is also determined (e.g., `1 + 2.0` results in a `float32`).

4. **Function Calls**: Arguments passed to functions are checked against the expected parameter types. The return value type is also enforced.

5. **Method Calls**: Similar to functions, arguments and the object the method is called on are type-checked.

6. **Array Operations**: Indexing requires an integer, and assigning elements requires matching the array's element type.

### Type Errors

Type errors found during the checking phase will prevent the code from compiling further, providing early feedback on potential issues:

```firescript
string name = "John";
int8 age = 30;

age = "thirty";  // Type error: Cannot assign string to int
name = 25;       // Type error: Cannot assign int to string
bool result = age + name;  // Type error: Cannot add int and string
                           // Also cannot assign result to bool
```

## Type Introspection

The `typeof` built-in function returns a string representing the type of a value:

```firescript
// Future syntax
string type1 = typeof(42);        // "int8"
string type2 = typeof(3.14);      // "float32"
string type3 = typeof("hello");   // "string"
string type4 = typeof(true);      // "bool"
string type5 = typeof([1, 2, 3]); // "int8[]"
```

## Standard Library Types (Planned)

The following standard library types are planned but not yet implemented:
* **`BigInt`**: Arbitrary-precision integers for calculations requiring more than 64 bits.
* **`Decimal`**: Fixed-point, arbitrary-precision decimal type for precise calculations.
* **`list<T>`**: A dynamic array type that can grow and shrink, unlike fixed-size arrays.

## Advanced Type Features (Planned)

The following advanced type features are planned but not yet implemented:

### Tuples

Tuples will allow grouping of values with different types. They will be immutable and can be accessed by index:

```firescript
// Future syntax
tuple<int8, string> person = (30, "John");
int8 age = person[0];  // 30
string name = person[1];  // "John"
```

### Generics

Generic types will allow for more flexible and reusable code:

```firescript
// Future syntax
T max<T>(T a, T b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}

int largerInt = max<int>(5, 10);  // 10
string largerString = max<string>("apple", "banana");  // "banana"
```

### User-Defined Types (Classes)

Classes will enable user-defined types with methods and properties:

```firescript
// Future syntax
class Point {
    float32 x;
    float32 y;

    Point(this, float32 x, float32 y) {
        this.x = x;
        this.y = y;
    }

    float32 distanceTo(this, Point other) {
        float32 dx = this.x - other.x;
        float32 dy = this.y - other.y;
        return toFloat((dx * dx + dy * dy) ** 0.5);
    }
}
```

## Implementation Status

The current firescript compiler supports:

* ✅ Some Copyable types: `bool`, `string`, `char`
* ✅ Nullable type modifiers
* ✅ Arrays of Copyable types
* ✅ Static type checking for expressions and assignments
* ✅ Type conversion functions

Not yet implemented:

* ❌ All integer types (`int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`)
* ❌ All floating point types (`float32`, `float64`, `float128`)
* ❌ Type introspection with `typeof`
* ❌ Tuples
* ❌ Generics
* ❌ User-defined types (classes)
* ❌ Interface types
* ❌ Function types

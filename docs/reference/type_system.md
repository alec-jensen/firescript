# Type System in firescript

> firescript employs a static type system to enhance code reliability and catch errors early during the compilation phase. This means that the type of every variable and expression is checked before the code is run.

## Built-in Types

firescript provides several fundamental data types categorized by their memory semantics:

### Copyable Types (Stack-Allocated)

These are fixed-size scalars stored on the stack and copied by value:

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
  * **`float128`**: 128-bit floating point number. [IMPLEMENTED] — true 16-byte IEEE 754 binary128 (quad-precision), implemented as a self-hosted soft-float runtime. Arithmetic, comparisons, and conversions are correctly rounded (round-to-nearest-even), with full support for subnormals, signed zero, infinity, and NaN.
* **`bool`**: Represents boolean values, either `true` or `false`. Example: `isActive: bool = true;`
* **`char`**: Represents a single character, stored on the stack. Initialized with a character literal or a single-character string literal. Examples: `initial: char = 'A';`, `digit: char = "7";`

### Owned Types (Heap-Allocated)

These values are stored on the heap with pointers on the stack and use move semantics:

* **`string`**: Represents sequences of characters. Example: `message: string = "Hello, World!";`
* **Arrays**: Collections of elements (see [Arrays](arrays.md))
* **User-defined classes**: Custom objects (see [Classes & Inheritance](classes.md))

### Special Types

* **`void`**: Represents the absence of a type, primarily used as the return type for functions that do not return a value.

## Type Semantics

### Explicit Casts (`as`)

firescript requires **explicit** conversions. There are no implicit casts between types.

Use Rust-style casts:

```firescript
myInt: int8 = (59i16 as int8);
u: uint8 = (255i16 as uint8);
f: float64 = (42i32 as float64);

// String to numeric conversions
num: int32 = ("42" as int32);
pi: float64 = ("3.14159" as float64);
bigNum: int64 = ("9223372036854775807" as int64);
```

Notes:

* `as` is a postfix operator: `expr as type`.
* For readability, parentheses are recommended when mixing with other operators.
* `as` is supported for:
  - Numeric-to-numeric casts (with possible loss of precision or overflow)
  - String-to-numeric casts (parsed by the firescript runtime)
  - Built-in type conversions to `string` (numeric types, `bool`, `char`)

### Integer Type (`intN` and `uintN`)

The `intN` types in firescript represent N-bit signed integers, while the `uintN` types represent N-bit unsigned integers.

```firescript
small: int8 = 42;
large: int64 = 9223372036854775807;  // Large integers are supported
calculation: int64 = ((small as int64) + large) * 2i64;  // Arithmetic operations
```

Integers support the following operations:

* Arithmetic: `+`, `-`, `*`, `/`, `%` (modulo), `**` (power)
* Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
* Bit manipulation (planned but not yet implemented): `&`, `|`, `^`, `~`, `<<`, `>>`

#### Integer Literals

Integer literals can be made more readable using underscores:

```firescript
million: int32 = 1_000_000;  // One million
bigNumber: int64 = 9_223_372_036_854_775_807;  // Large integer
```

Integer literals can be specified in decimal, hexadecimal, binary, or octal formats:

```firescript
decimal: int8 = 42;        // Decimal
hex: int8 = 0x2A;          // Hexadecimal
binary: int8 = 0b00101010; // Binary
octal: int8 = 0o52;        // Octal
```

**Type Inference for Literals:**

When you assign a literal to a variable with an explicit type, the literal automatically takes on that type:

```firescript
small: int8 = 42;          // Literal 42 inferred as int8
medium: uint16 = 30000;    // Literal 30000 inferred as uint16
large: int64 = 9223372036854775807;  // Literal inferred as int64
pi: float32 = 3.14;        // Literal 3.14 inferred as float32
e: float64 = 2.71828;      // Literal 2.71828 inferred as float64
```

If the literal is too large or too small for the target type, you'll get a compile-time error:

```firescript
// int8 overflow = 200;   // ❌ Compile error: 200 exceeds int8 range (-128 to 127)
// uint8 negative = -1;   // ❌ Compile error: -1 invalid for unsigned type
```

**Explicit Type Suffixes:**

You can also explicitly specify the type using a suffix, which is useful in contexts where the type cannot be inferred (like in expressions):

```firescript
small: int8 = 42i8;
medium: int16 = 30000i16;
large: int64 = 9223372036854775807i64;
usmall: uint8 = 255u8;
umedium: uint16 = 60000u16;
ularge: uint64 = 18446744073709551615u64;
```

You can define a base and a suffix together:

```firescript
hexSmall: int8 = 0x2Ai8;
binMedium: uint16 = 0b111010100110u16;
```

#### Integer Overflow and Underflow Behavior

For all fixed-size integer types (`intN` and `uintN`), arithmetic operations that exceed the representable range will throw an error at runtime. This is to prevent silent overflow/underflow issues.

```firescript
max: int8 = 127i8;
overflow: int8 = max + 1i8;  // Runtime error: Integer overflow
```

Overflows that can be detected at compile-time (e.g., constant expressions) will result in a compile-time error.

```firescript
compileTimeOverflow: int8 = 128i8;  // Compile-time error: Integer overflow
```

### Floating Point Types (`floatN`)

The `floatN` types represent N-bit floating point numbers.

```firescript
simpleDecimal: float32 = 3.14;
highPrecision: float64 = 3.141592653589793;
```

Floating point numbers support:

* Arithmetic: `+`, `-`, `*`, `/`, `**` (power)
* Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`

#### Floating Point Literals

Floating point literals can be specified in decimal or scientific notation.

**Type Inference for Literals:**

When you assign a floating-point literal to a variable with an explicit type, the literal automatically takes on that type:

```firescript
pi: float32 = 3.14159;              // Literal inferred as float32
e: float64 = 2.71828;               // Literal inferred as float64
phi: float128 = 1.618033988749;     // Literal inferred as float128
scientific: float64 = 6.022e23;     // Scientific notation, inferred as float64
```

**Explicit Type Suffixes:**

You can also explicitly specify the type using a suffix:

```firescript
f32Value: float32 = 3.14f32;
f64Value: float64 = 3.14f64;
f128Value: float128 = 3.14f128;
```

#### Special Floating Point Values

*Floating point operations follow IEEE 754 semantics.*

Floating point types support special values such as `NaN` (Not a Number), `Infinity`, and `-Infinity`:

```firescript
notANumber: float32 = 0.0f32 / 0.0f32;  // NaN
positiveInfinity: float64 = 1.0f64 / 0.0f64;  // Infinity
negativeInfinity: float64 = -1.0f64 / 0.0f64; // -Infinity
```

#### Floating Point Overflow and Underflow Behavior

Floating point operations that exceed the representable range will result in `Infinity` or `-Infinity`, while operations resulting in values too close to zero will result in `0.0`. Operations resulting in undefined values will yield `NaN`.

```firescript
large: float32 = 3.4e38f32 * 10.0f32;  // Results in Infinity
small: float32 = 1.0e-38f32 / 10.0f32; // Results in 0.0
undefined: float32 = 0.0f32 / 0.0f32;      // Results in NaN
```

### Boolean Type (`bool`)

The `bool` type has only two possible values: `true` and `false`. It's commonly used in conditional expressions.

```firescript
userLoggedIn: bool = true;
hasPermission: bool = false;

// Boolean operations
canAccess: bool = userLoggedIn && hasPermission;  // Logical AND
needsAttention: bool = !userLoggedIn || !hasPermission;  // Logical OR and NOT
```

Boolean values support:

* Logical operations: `&&` (AND), `||` (OR), `!` (NOT)
* Comparison: `==`, `!=`

### String Type (`string`)

The `string` type represents sequences of characters. Strings in firescript are immutable.

```firescript
greeting: string = "Hello";
name: string = "World";
message: string = greeting + ", " + name + "!";  // String concatenation with +

// Multi-line strings
paragraph: string = "This is a
multi-line
string";
```

Strings support:

* Concatenation: `+`
* Comparison: `==`, `!=`

### Character Type (`char`)

The `char` type represents a single character. Unlike strings, `char` is a copyable type and is stored on the stack. It can be initialized with a single character string literal.

```firescript
letter: char = "A";
digit: char = "7";
newline: char = "\n";  // Special character
```

### Arrays

Arrays are fixed-size ordered collections of elements of the same type.

#### Declaration and Initialization

```firescript
// With initial values
numbers: int8[5] = [1, 2, 3, 4, 5];
fruits: string[3] = ["apple", "banana", "cherry"];
```

#### Array Operations

```firescript
scores: int8[3] = [85, 92, 78];

// Accessing elements (zero-based indexing)
firstScore: int8 = scores[0];  // 85

// Modifying elements
scores[1] = 95;  // Array becomes [85, 95, 78]

// Array properties
count: int32 = scores.length();  // 3
```

## Nullability [IMPLEMENTED]

By default, variables cannot hold the value `null`. To allow a variable to be assigned `null`, mark it nullable with a trailing `?` after its name.

### Declaring Nullable Variables

```firescript
username: string? = null;  // Allowed
title: string = "Default";

// title = null;  // Error: Cannot assign null to non-nullable type 'string'

username = "John";  // Can be assigned a non-null value later
```

### Working with Nullable Values

When working with nullable variables, it's important to check for null before using them:

```firescript
import @firescript/std.io.print;

data: string? = null;

// Safe pattern
if (data != null) {
    print(data);
}

// Could cause a runtime error if not checked
print(data);  // Might try to print null
```

## Type Compatibility and Conversions

firescript has strict typing rules and requires explicit type conversions using casting syntax.

### Explicit Type Casting

To convert between types, use postfix casting with `as`.

firescript uses Rust-style postfix casting; Java/C-style casts are not supported.

```firescript
// Numeric conversions
intVal: int32 = 42;
floatVal: float64 = intVal as float64;     // 42.0

pi: float32 = 3.14f32;
truncated: int32 = pi as int32;            // 3 (truncates decimal)

// Between numeric types
small: int8 = 100i8;
large: int64 = small as int64;             // 100i64

unsigned: uint32 = 42u32;
signed: int32 = unsigned as int32;         // 42i32

// String conversions
numStr: string = "42";
parsed: int32 = numStr as int32;           // 42
parsedFloat: float64 = "3.14" as float64;  // 3.14

// To string
str1: string = 42 as string;               // "42"
str2: string = 3.14f32 as string;          // "3.14"
str3: string = true as string;             // "true"
letter: char = 'A';
str4: string = letter as string;           // "A"
```

**Casting Rules:**

1. **Numeric to numeric**: Always allowed, may lose precision or truncate
2. **String to numeric**: Parses the string
3. **Numeric to string**: Converts to string representation
4. **Boolean to string**: "true" or "false"
5. **Char to string**: One-character string

**Invalid Casts:**

Casts to non-numeric targets other than `string` are not allowed and will result in compile-time errors:

```firescript
// int32 x = [1, 2, 3] as int32;  // ❌ Error: Cannot cast array to int32
// bool b = 1 as bool;             // ❌ Error: cannot cast to bool
// char c = "Hello" as char;       // ❌ Error: cannot cast to char
```

### Mixed-Type Arithmetic

firescript does **not** perform implicit type conversions in arithmetic operations. When performing operations between different types or precisions, you must explicitly cast to the desired result type.

```firescript
a: int32 = 10;
b: int64 = 20i64;

// int32 result = a + b;  // ❌ Error: Cannot mix int32 and int64

// Must explicitly cast to desired type
result1: int32 = a + (b as int32);  // Cast b to int32 first
result2: int64 = (a as int64) + b;  // Cast a to int64 first

// Mixed integer and float
intVal: int32 = 5;
floatVal: float32 = 2.5f32;

// float32 mixed = intVal + floatVal;  // ❌ Error: Cannot mix int32 and float32

result3: float32 = (intVal as float32) + floatVal;  // Cast int to float
result4: int32 = (floatVal as int32) + intVal;      // Cast float to int (truncates)

// Different float precisions
f32: float32 = 3.14f32;
f64: float64 = 2.71f64;

// float64 sum = f32 + f64;  // ❌ Error: Cannot mix float32 and float64

result5: float64 = (f32 as float64) + f64;  // Cast to float64
result6: float32 = f32 + (f64 as float32);  // Cast to float32
```

**Design Rationale:**

This explicit approach prevents silent precision loss and makes data type conversions visible in the code, aligning with firescript's philosophy of explicitness and safety.

### String Concatenation

String concatenation with `+` requires both operands to be strings. There is no implicit conversion — cast non-string values explicitly:

```firescript
message: string = "Count: " + (42 as string);              // "Count: 42"
status: string = "Active: " + (true as string);            // "Active: true"
pi: string = "Pi is approximately " + (3.14f32 as string); // "Pi is approximately 3.14"

// string bad = "Count: " + 42;  // ❌ Error: cannot concatenate string and int32
```

## Type Checking and Enforcement

The firescript parser includes a type-checking phase that runs after the initial syntax parsing.

### Static Type Checking

1. **Variable Declarations**: When you declare a variable (`x: int8 = 5i8;`), the type checker verifies that the type of the initializer (`5i8`, which is `int8`) matches the declared type (`int8`).

2. **Assignments**: When assigning a value to an existing variable (`x = 10i8;`), the checker ensures the assigned value's type is compatible with the variable's declared type.

3. **Expressions**: Operators (`+`, `-`, `*`, `/`, `==`, `>`, etc.) are checked to ensure they are used with compatible operand types. For example, arithmetic operators require numeric operands of the exact same type, while `+` can also be used for string concatenation (both operands must be strings).

4. **Function Calls**: Arguments passed to functions are checked against the expected parameter types. The return value type is also enforced.

5. **Method Calls**: Similar to functions, arguments and the object the method is called on are type-checked.

6. **Array Operations**: Indexing requires an integer, and assigning elements requires matching the array's element type.

### Type Errors

Type errors found during the checking phase will prevent the code from compiling further, providing early feedback on potential issues:

```firescript
name: string = "John";
age: int8 = 30;

age = "thirty";  // Type error: Cannot assign string to int
name = 25;       // Type error: Cannot assign int to string
result: bool = age + name;  // Type error: Cannot add int and string
                           // Also cannot assign result to bool
```

## Type Introspection [PLANNED]

A `typeof` built-in returning a string representation of a value's type is planned but not yet implemented:

```firescript
// Future syntax
type1: string = typeof(42);        // "int8"
type2: string = typeof(3.14);      // "float32"
type3: string = typeof("hello");   // "string"
type4: string = typeof(true);      // "bool"
type5: string = typeof([1, 2, 3]); // "int8[]"
```

## Standard Library Types (Planned)

The following standard library types are planned but not yet implemented:
* **`BigInt`**: Arbitrary-precision integers for calculations requiring more than 64 bits.
* **`Decimal`**: Fixed-point, arbitrary-precision decimal type for precise calculations.
* **`list<T>`**: A dynamic array type that can grow and shrink, unlike fixed-size arrays.

## Generics

> Status: Generic functions and generic classes are [IMPLEMENTED], including type-union constraints and named constraint aliases. Interface-based constraints are [PLANNED] and are marked as such below.

Generics allow you to write flexible, reusable code that works with multiple types while maintaining type safety. Instead of writing separate functions for each type, you write one generic function that works with any compatible type.

#### Basic Generic Functions

A generic function is declared with type parameters in angle brackets after the function name:

```firescript
fn max<T>(a: T, b: T) -> T {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}

// Type parameter is inferred from arguments
largerInt: int8 = max(5i8, 10i8);        // T inferred as int8
largerF64: float64 = max(2.5, 1.5);      // T inferred as float64

// Or explicitly specified
largerFloat: float32 = max<float32>(3.14f32, 2.71f32);
```

#### Type Constraints

Type constraints restrict which types can be used with a generic function. This ensures the function only accepts types that support the required operations.

**Interface Constraints [PLANNED]:**

Interface-based constraints are planned alongside the interface system itself:

```firescript
// Future syntax
// T must satisfy the Comparable interface
fn max<T: Comparable>(a: T, b: T) -> T {
    if (a > b) { return a; }
    return b;
}
```

**Type Union Constraints:**

For simpler cases, you can use type unions to explicitly list which types are allowed:

```firescript
// T can be int32, int64, or float64
fn add<T: int32 | int64 | float64>(a: T, b: T) -> T {
    return a + b;
}

// Works with any of the specified types
result1: int32 = add(5i32, 10i32);        // ✅ Works
result2: float64 = add(3.14f64, 2.71f64); // ✅ Works
// int8 result3 = add(1i8, 2i8);         // ❌ Error: int8 not in union

// Type unions work with any types, including custom classes
class Point { /* ... */ }
class Circle { /* ... */ }

fn process<T: Point | Circle>(shape: T) -> T {
    // Can work with Point or Circle
    return shape;
}
```

**Multiple Constraints [PLANNED]:**

Combining interface constraints with type unions is planned for when interfaces land:

```firescript
// Future syntax
// T must satisfy Comparable AND be in the union
fn clamp<T: Comparable & (int32 | float64)>(value: T, min: T, max: T) -> T {
    if (value < min) { return min; }
    if (value > max) { return max; }
    return value;
}
```

**When to Use Each:**

- **Type unions** (`T: int32 | float64`): When you want to explicitly list allowed types, simple and explicit — available today
- **Constraint aliases** (`T: Numeric`): Named, reusable type unions — available today (see [Custom Type Constraints](#custom-type-constraints))
- **Interface constraints** (`T: Comparable`) [PLANNED]: When you need types with specific capabilities, works with any type that implements the interface

#### Type Union Constraints

Type unions provide a simple, explicit way to define generic constraints by listing the exact types allowed. This is inspired by Python's `Union` but with firescript's explicit syntax.

**Basic Type Unions:**

```firescript
// Simple union - T can be int32 or float64
fn convert<T: int32 | float64>(value: T) -> T {
    return value;
}

// Multiple types in union
fn process<T: int8 | int16 | int32 | int64>(value: T) -> T {
    return value * 2;
}

// Works with custom types too
class Dog { /* ... */ }
class Cat { /* ... */ }

fn feed<T: Dog | Cat>(animal: T) -> T {
    // Feed the animal
    return animal;
}
```

**Combining Unions with Interfaces [PLANNED]:**

Once interfaces are implemented, you will be able to require that types satisfy both an interface AND be in a specific union:

```firescript
// Future syntax
// T must be Comparable AND one of these specific types
fn max<T: Comparable & (int32 | int64 | float64)>(a: T, b: T) -> T {
    if (a > b) { return a; }
    return b;
}
```

**Practical Example:**

```firescript
// Define a function that only works with specific numeric types
fn safeDivide<T: float32 | float64>(a: T, b: T) -> T {
    if (b == 0.0) {
        return a - a;  // Safe zero default for floats
    }
    return a / b;
}

result1: float32 = safeDivide(10.0f32, 2.0f32);  // ✅ Works
result2: float64 = safeDivide(10.0f64, 2.0f64);  // ✅ Works
// int32 result3 = safeDivide(10i32, 2i32);     // ❌ Error: int32 not in union
```

#### Standard Constraint Aliases [IN DEVELOPMENT]

The standard library defines common constraint aliases as type unions (in `firescript/std/constraints.fire`):

- **`Numeric`** — all `intN`, `uintN`, and `floatN` types
- **`SignedInteger`** — `int8 | int16 | int32 | int64`
- **`UnsignedInteger`** — `uint8 | uint16 | uint32 | uint64`
- **`Integer`** — `SignedInteger | UnsignedInteger`
- **`FloatingPoint`** — `float32 | float64 | float128`

These are not yet importable from user code; for now, define equivalent constraint aliases in your own modules (see [Custom Type Constraints](#custom-type-constraints)). Interface-style constraints with behavioral requirements (`Comparable`, `Equatable`, etc.) are [PLANNED] as part of the interface system.



#### Multiple Type Parameters

Functions can declare multiple generic type parameters (e.g., `R convert<T, R>(T value)`). Function-typed parameters and casting between type parameters are [PLANNED]:

```firescript
// Future syntax
// Map a function over a value (function types are planned)
R map<T, R>(T value, R func(T)) {
    return func(value);
}
```

#### Generic Constants and Type-Associated Values [PLANNED]

For constants that need to adapt to the type precision, type-associated constant functions are planned:

```firescript
// Type-associated constants (planned syntax)
fn pi<T: float<N>>() -> T {
    // Compiler provides appropriate precision for each float type
    return cast<T>(3.141592653589793238462643383279502884197);
}

fn e<T: float<N>>() -> T {
    return cast<T>(2.718281828459045235360287471352662497757);
}

// Usage - type is inferred from context
fn circumference32(radius: float32) -> float32 {
    return 2.0f32 * pi<float32>() * radius;
}

fn circumference64(radius: float64) -> float64 {
    return 2.0f64 * pi<float64>() * radius;
}

// Or with type inference
fn area(radius: float32) -> float32 {
    piValue: float32 = pi();  // Type inferred as float32 from variable type
    return piValue * radius * radius;
}
```

#### Type Inference

The firescript compiler can infer generic type parameters from function arguments in most cases:

```firescript
fn identity<T>(value: T) -> T {
    return value;
}

// Type parameter inferred from argument
x: int32 = identity(42i32);        // T inferred as int32
s: string = identity("hello");      // T inferred as string

// Explicit type parameter when needed
y: float64 = identity<float64>(42.0); // T is float64
```

Type inference follows these rules:

1. If argument types match the parameter types, infer from arguments
2. If return type is known and argument types are ambiguous, infer from return type
3. If neither works, require explicit type parameters
4. All type parameters must be consistently inferred

```firescript
constraint NumericPrimitive = int32 | int64 | float32 | float64;

fn add<T: NumericPrimitive>(a: T, b: T) -> T {
    return a + b;
}

result1: int32 = add(10i32, 20i32);  // ✅ T inferred as int32
result2: float32 = add(1.5f32, 2.5f32);  // ✅ T inferred as float32

// int32 result3 = add(10i32, 20i64);  // ❌ Error: T cannot be both int32 and int64
```

#### Generic Classes

Generic classes create data structures that work with any type. Both owned and `copyable` generic classes are supported:

```firescript
class Box<T> {
    value: T;

    fn Box(value: T) {
        this.value = value;
    }

    fn getValue(&this) -> T {
        return this.value;
    }
}

// Usage
intBox: Box<int32> = Box<int32>(42i32);
```

The standard library's `Tuple<T, U>` and `Option<T>` (`@firescript/std.types`) are generic classes. See [Classes & Inheritance — Generic Classes](classes.md#generic-classes).

#### Generic Arrays and Collections (Planned)

The standard library will provide generic collection types:

```firescript
// Planned syntax
list<T> myList = list<int32>();
myList.push(1);
myList.push(2);
myList.push(3);

map<string, int32> scores = map<string, int32>();
scores.set("Alice", 100);
scores.set("Bob", 95);

aliceScore: int32? = scores.get("Alice");  // 100
```

#### Implementation Notes

Generics in firescript use **monomorphization** at compile time:

1. When you call a generic function with specific types, the compiler generates a specialized version
2. Each unique combination of type parameters gets its own compiled function
3. This means zero runtime overhead - generic code is as fast as hand-written type-specific code
4. The tradeoff is slightly larger binary size (one copy of the function per type combination used)

```firescript
// You write this once:
fn max<T: int32 | float32>(a: T, b: T) -> T {
    if (a > b) { return a; }
    return b;
}

// If you call it with int32 and float32:
x: int32 = max(5i32, 10i32);
y: float32 = max(3.14f32, 2.71f32);

// The compiler generates (conceptually):
// int32 max_int32(int32 a, int32 b) { ... }
// float32 max_float32(float32 a, float32 b) { ... }

// And replaces your calls with:
// int32 x = max_int32(5i32, 10i32);
// float32 y = max_float32(3.14f32, 2.71f32);
```

This approach is similar to C++ templates and Rust generics, ensuring that generic code has no performance penalty.

#### Custom Type Constraints

For frequently used type union constraints, you can define named constraint aliases to avoid repetition and improve code readability.

**Defining Constraint Aliases:**

```firescript
// Define a constraint alias using the 'constraint' keyword
constraint NumericPrimitive = int32 | int64 | float32 | float64;

constraint SignedInteger = int8 | int16 | int32 | int64;

constraint UnsignedInteger = uint8 | uint16 | uint32 | uint64;

constraint FloatingPoint = float32 | float64 | float128;
```

**Using Constraint Aliases:**

```firescript
// Use the constraint alias just like a built-in constraint
fn add<T: NumericPrimitive>(a: T, b: T) -> T {
    return a + b;
}

fn abs<T: SignedInteger>(x: T, zero: T) -> T {
    if (x < zero) {
        return -x;
    }
    return x;
}

fn clamp<T: FloatingPoint>(value: T, min: T, max: T) -> T {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

// Usage is natural
sum: int32 = add(10i32, 20i32);          // ✅ Works with NumericPrimitive
clamped: float64 = clamp(5.5, 0.0, 10.0); // ✅ Works with FloatingPoint
```

**Combining Constraint Aliases:**

You can combine constraint aliases with other constraints:

```firescript
constraint IntegerType = SignedInteger | UnsignedInteger;

// Combine with interface constraints
fn process<T: Comparable & IntegerType>(value: T) -> T {
    // T must be comparable AND one of the integer types
    return value;
}

// Combine multiple constraint aliases with unions
constraint AllNumeric = SignedInteger | UnsignedInteger | FloatingPoint;

fn compute<T: AllNumeric>(value: T) -> T {
    return value * value;
}
```

**Constraint Aliases for Custom Types:**

Constraint aliases also work with custom classes:

```firescript
class Circle { /* ... */ }
class Square { /* ... */ }
class Triangle { /* ... */ }

// Define a constraint for shape types
constraint Shape2D = Circle | Square | Triangle;

// Use in generic functions
fn area<T: Shape2D>(shape: T) -> T {
    // Calculate area for any 2D shape
    return shape.calculateArea();
}

// Can be combined with interfaces
interface Drawable {
    fn draw(&this) -> void;
}

fn render<T: Drawable & Shape2D>(shape: T) -> T {
    shape.draw();
    return shape;
}
```

**Benefits:**

1. **DRY (Don't Repeat Yourself)**: Define the constraint once, use it many times
2. **Readability**: `T: NumericPrimitive` is clearer than `T: int32 | int64 | float32 | float64`
3. **Maintainability**: Change the constraint in one place instead of updating every function
4. **Semantic clarity**: Names like `SignedInteger` convey intent better than type lists

**Constraint Aliases vs. Interfaces:**

```firescript
// Constraint alias - just a shorthand for a type union (implemented)
constraint FastInt = int32 | int64;
fn add<T: FastInt>(a: T, b: T) -> T { return a + b; }
// Expands to: T add<T: int32 | int64>(T a, T b)

// Interface - defines required capabilities (PLANNED, future syntax)
interface Printable {
    fn toString(&this) -> string;
}
fn print<T: Printable>(value: T) -> T { /* ... */ }
// Requires T to have a toString() method
```

**Scope and Visibility:**

firescript uses two different visibility boundaries:

- **Class scope** controls access to class members.
- **Module scope** controls what other files can import.

At module scope, symbols are private by default and must be explicitly exported to be imported from another file. That keeps a file's implementation details local while making its public API obvious.

Constraint aliases follow the same scoping rules as other declarations:

```firescript
// Module-level constraint (usable throughout the file)
constraint ModuleNumeric = int32 | float32;

// Exported module API
export constraint PublicNumeric = int32 | float64;
export fn compute<T: PublicNumeric>(value: T) -> T {
    return value;
}

// Importing another module can only access its exported symbols.
import my_module.{PublicNumeric, compute}
```

### Interfaces [PLANNED]

> Status: The entire interface system described in this section is [PLANNED]. None of it is implemented in the current compiler; all code below is future syntax.

Interfaces define a set of capabilities that types can implement. They are used primarily as constraints for generic type parameters, ensuring that generic code only accepts types that support the required operations.

**Key Design Principles:**

1. **Primitive types are closed**: You cannot implement interfaces directly on primitive types like `int32`, `float64`, etc.
2. **Built-in interfaces have compiler support**: Interfaces like `Numeric`, `Comparable`, etc. work with primitives through compiler magic.
3. **Custom interfaces need wrappers**: For custom interfaces, create wrapper classes or use standard library wrappers.
4. **Classes use `implements`**: Custom classes declare interfaces using the `implements` keyword (Java-style).

```firescript
// Built-in interfaces work with primitives (compiler support)
fn max<T: Comparable>(a: T, b: T) -> T { return a > b ? a : b; }
result: int32 = max(5i32, 10i32);  // ✅ Works

// Custom interfaces need wrapper classes
interface Printable {
    fn toString(&this) -> string;
}

class PrintableInt implements Printable {
    value: int32;
    fn toString(&this) -> string { return this.value as string; }
}
```

#### Defining an Interface

An interface is defined using the `interface` keyword followed by the interface name and a body:

```firescript
// Basic interface definition
interface Printable {
    // Method signature that implementing types must provide
    fn toString(&this) -> string;
}

// Interface with multiple methods
interface Drawable {
    fn draw(&this) -> void;
    fn move(&this, x: int32, y: int32) -> void;
    fn isVisible(&this) -> bool;
}
```

#### Interface Inheritance

Interfaces can inherit from other interfaces, creating a hierarchy of capabilities:

```firescript
// Base interface
interface Equatable {
    fn equals(&this, other: &this) -> bool;
}

// Child interface inherits parent's requirements
interface Comparable from Equatable {
    fn compare(&this, other: &this) -> int32;  // Returns -1, 0, or 1
}

// Types implementing Comparable must also implement Equatable
```

#### Implementing Interfaces for Types

Classes declare which interfaces they implement using the `implements` keyword:

```firescript
import @firescript/std.io.print;

// Define a class that implements an interface
class Point implements Printable {
    x: float32;
    y: float32;

    fn Point(&this, x: float32, y: float32) {
        this.x = x;
        this.y = y;
    }

    // Implement the required method from Printable
    fn toString(&this) -> string {
        return "Point(" + (this.x as string) + ", " + (this.y as string) + ")";
    }
}

// Implement multiple interfaces
class Circle implements Drawable, Printable {
    radius: float32;

    fn Circle(&this, radius: float32) {
        this.radius = radius;
    }

    // Implement Drawable methods
    fn draw(&this) -> void {
        print("Drawing circle with radius " + (this.radius as string));
    }

    fn move(&this, dx: int32, dy: int32) -> void {
        // Movement logic
    }

    fn isVisible(&this) -> bool {
        return true;
    }

    // Implement Printable method
    fn toString(&this) -> string {
        return "Circle(radius=" + (this.radius as string) + ")";
    }
}
```

#### Primitives with Generic Constraints

Built-in interfaces like `Numeric`, `Comparable`, etc. work directly with primitive types through compiler magic. You don't need wrappers for these:

```firescript
// Built-in interfaces work with primitives directly
fn max<T: Comparable>(a: T, b: T) -> T {
    return a > b ? a : b;
}

result: int32 = max(5i32, 10i32);  // ✅ Works! No wrapper needed
fResult: float64 = max(3.14f64, 2.71f64);  // ✅ Works!

// This is compiler magic - the compiler knows int32 satisfies Comparable
```

**For custom interfaces, you need wrappers:**

```firescript
import @firescript/std.io.print;

// Custom interface
interface Printable {
    fn toString(&this) -> string;
}

// This won't work with primitives directly
fn printValue<T: Printable>(value: T) -> void {
    print(value.toString());
}

// printValue(42i32);  // ❌ Error: int32 does not implement Printable

// Create a wrapper class
class PrintableInt implements Printable {
    value: int32;

    fn PrintableInt(&this, value: int32) {
        this.value = value;
    }

    fn toString(&this) -> string {
        return "Value: " + (this.value as string);
    }
}

// Now it works
printValue(PrintableInt(42));  // ✅ Works!
```

**Summary:**
- **Type unions** (`T: int32 | float64`): Simplest way to constrain primitives - **use this first!**
- **Built-in interfaces** (`SignedInt`, `Float`, `Comparable`, etc.): Work with primitives directly for broader type families
- **Custom interfaces with wrappers**: Only when you need custom methods on primitives

#### Using Interfaces as Generic Constraints

Interfaces are most commonly used to constrain generic type parameters:

```firescript
import @firescript/std.io.print;

// Function that works with any Printable type
fn printValue<T: Printable>(value: T) -> void {
    print(value.toString());
}

// Function that works with any Drawable type
fn renderAll<T: Drawable>(items: T[]) -> void {
    for (i: int32 = 0; i < items.length; i = i + 1) {
        items[i].draw();
    }
}

// Multiple interface constraints
fn processItem<T: Printable & Drawable>(item: T) -> void {
    print("Processing: " + item.toString());
    item.draw();
}
```

#### Marker Interfaces

Some interfaces don't require any methods - they simply mark that a type has certain properties. These are called marker interfaces:

```firescript
// Marker interface - no methods required
interface Copyable {
    // Types implementing this can be copied bitwise
}

interface Serializable {
    // Types implementing this can be serialized
}

// Implementing marker interfaces in class definition
class Point implements Copyable, Serializable {
    x: float32;
    y: float32;

    // No methods to implement - just marks Point as copyable and serializable
    fn Point(&this, x: float32, y: float32) {
        this.x = x;
        this.y = y;
    }
}
```

#### Built-in Interfaces

firescript provides several built-in interfaces that are automatically "implemented" by primitive types through compiler support. These are defined in `std/interfaces/`:

**Numeric Interfaces** (in `std/interfaces/numeric.fire`):
- `Numeric` - Any numeric type supporting arithmetic operations
- `Integer` - Any integer type (signed or unsigned)
- `SignedInt` - Signed integers only
- `UnsignedInt` - Unsigned integers only
- `Float` - Floating-point types only

**Comparison Interfaces** (in `std/interfaces/comparable.fire`):
- `Equatable` - Types supporting `==` and `!=`
- `Comparable` - Types supporting comparison operators (`<`, `>`, `<=`, `>=`)

**Memory Interfaces** (in `std/interfaces/copyable.fire`):
- `Copyable` - Types that can be copied (vs. moved)

These interfaces are automatically imported and available without explicit `import` statements.

**How Built-in Interfaces Work:**

- **Primitive types** (`int32`, `float64`, etc.): The compiler automatically recognizes that they satisfy built-in interfaces. You can use them directly with generic constraints.
- **Custom classes**: Must explicitly implement interfaces using `implements` in their class definition.

```firescript
// Built-in interfaces work with primitives
fn add<T: Numeric>(a: T, b: T) -> T {
    return a + b;
}

sum: int32 = add(5i32, 10i32);  // ✅ Compiler knows int32 satisfies Numeric

// Custom classes must explicitly implement
class MyNumber implements Numeric {
    value: int32;

    fn MyNumber(&this, value: int32) {
        this.value = value;
    }

    // Must implement Numeric operations...
}
```

#### Combining Interface Constraints

You can combine multiple interface constraints to require specific capabilities:

```firescript
// Works with any signed integer precision
fn negate<T: SignedInt>(value: T) -> T {
    return -value;
}

// Works with any float precision
fn normalize<T: Float>(value: T, min: T, max: T) -> T {
    return (value - min) / (max - min);
}

// Combine interface constraints
fn clamp<T: Comparable & Numeric>(value: T, min: T, max: T) -> T {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}
```

#### Default Implementations (Planned)

In the future, interfaces may support default method implementations:

```firescript
// Planned syntax
interface Comparable from Equatable {
    fn compare(&this, other: &this) -> int32;

    // Default implementations based on compare()
    fn lessThan(&this, other: &this) -> bool {
        return this.compare(other) < 0;
    }

    fn greaterThan(&this, other: &this) -> bool {
        return this.compare(other) > 0;
    }
}

// Types implementing Comparable only need to provide compare()
// They get lessThan() and greaterThan() for free
```

#### Associated Types (Planned)

Interfaces may support associated types for more flexible generic programming:

```firescript
// Planned syntax
interface Container {
    type Item;  // Associated type

    fn get(&this, index: int32) -> Item;
    fn set(&this, index: int32, value: Item) -> void;
    fn size(&this) -> int32;
}

impl Container for IntArray {
    type Item = int32;  // Specify the associated type

    fn get(&this, index: int32) -> int32 {
        return this.data[index];
    }

    fn set(&this, index: int32, value: int32) -> void {
        this.data[index] = value;
    }

    fn size(&this) -> int32 {
        return this.length;
    }
}
```

#### Interface Objects (Planned)

In the future, interfaces may be used as types themselves, allowing for dynamic dispatch:

```firescript
import @firescript/std.io.print;

// Planned syntax
fn printAll(items: Printable[]) -> void {  // Array of interface objects
    for (i: int32 = 0; i < items.length; i = i + 1) {
        print(items[i].toString());
    }
}

// Can pass any type implementing Printable
p: Point = Point(1.0f32, 2.0f32);
c: Circle = Circle(3.0f32);
mixed: Printable[] = [p, c];  // Different types, same interface
printAll(mixed);
```

#### Design Guidelines for Interfaces

When designing interfaces, follow these guidelines:

1. **Single Responsibility**: Each interface should represent one cohesive capability
2. **Small and Focused**: Prefer many small interfaces over few large ones
3. **Composable**: Use interface inheritance to build complex capabilities from simple ones
4. **Clear Naming**: Interface names should clearly indicate the capability (e.g., `Readable`, `Writable`, `Comparable`)
5. **Minimal Requirements**: Only include methods that are truly essential to the interface

```firescript
// Good: Small, focused interfaces
interface Readable {
    fn read(&this) -> string;
}

interface Writable {
    fn write(&this, data: string) -> void;
}

interface Seekable {
    fn seek(&this, position: int64) -> void;
}

// Can combine them as needed
class File implements Readable, Writable, Seekable {
    // ... fields ...

    // Implement all required methods
    fn read(&this) -> string { /* ... */ }
    fn write(&this, data: string) -> void { /* ... */ }
    fn seek(&this, position: int64) -> void { /* ... */ }
}

// Bad: One monolithic interface
interface FileOperations {
    fn read(&this) -> string;
    fn write(&this, data: string) -> void;
    fn seek(&this, position: int64) -> void;
    fn exists(&this) -> bool;
    fn delete(&this) -> void;
    // Too many unrelated operations!
}
```

### User-Defined Types (Classes)

Classes enable user-defined types with fields and methods, including constructors, inheritance, static methods, and generics. See [Classes & Inheritance](classes.md) for the full reference:

```firescript
class Point {
    x: float32;
    y: float32;

    fn Point(&mut this, x: float32, y: float32) {
        this.x = x;
        this.y = y;
    }

    fn dot(&this, other: &Point) -> float32 {
        return this.x * other.x + this.y * other.y;
    }
}
```

## Implementation Status

The current firescript compiler supports:

* [IMPLEMENTED] All integer types (`int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`)
* [IMPLEMENTED] All floating point types (`float32`, `float64`, `float128`)
* [IMPLEMENTED] `bool`, `char`, `string`
* [IMPLEMENTED] Nullable type modifiers
* [IMPLEMENTED] Arrays (as Owned heap-allocated types)
* [IMPLEMENTED] User-defined classes (including generic and `copyable` classes)
* [IMPLEMENTED] Static type checking for expressions and assignments
* [IMPLEMENTED] Generics
  * Generic functions (with and without constraints)
  * Type union constraints (`T: int32 | float64`)
  * Named constraint aliases (`constraint Name = ...`)
  * Generic classes
  * Type inference for generic calls, plus explicit type arguments
* [IMPLEMENTED] Explicit `as` casting: numeric ↔ numeric, string → numeric, and built-in types → `string`

Not yet implemented:

* [PLANNED] Type inference on variable declarations
* [PLANNED] Type introspection with `typeof`
* [PLANNED] Casts to `bool` or `char`
* [PLANNED] Interfaces (syntax and semantics documented above; implementation pending)
  * Interface definitions (`interface Name { }`)
  * Interface inheritance (`interface Child from Parent { }`)
  * Interface implementations (`class Type implements Interface { }`)
  * Built-in interfaces with compiler support (`Comparable`, `Equatable`, etc.)
  * Marker interfaces, default implementations, associated types, dynamic dispatch
* [PLANNED] Function types

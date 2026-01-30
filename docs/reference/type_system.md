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

### Explicit Casts (`as`)

firescript requires **explicit** numeric conversions. There are no implicit casts between integer widths/signedness.

Use Rust-style casts:

```firescript
int8 myInt = (59i16 as int8);
uint8 u = (255i16 as uint8);
float64 f = (42i32 as float64);
```

Notes:

* `as` is a postfix operator: `expr as type`.
* For readability, parentheses are recommended when mixing with other operators.
* `as` is currently supported for numeric-to-numeric casts.

### Integer Type (`intN` and `uintN`)

The `intN` types in firescript represent N-bit signed integers, while the `uintN` types represent N-bit unsigned integers.

```firescript
int8 small = 42;
int64 large = 9223372036854775807;  // Large integers are supported
int64 calculation = ((small as int64) + large) * 2i64;  // Arithmetic operations
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

**Type Inference for Literals:**

When you assign a literal to a variable with an explicit type, the literal automatically takes on that type:

```firescript
int8 small = 42;          // Literal 42 inferred as int8
uint16 medium = 30000;    // Literal 30000 inferred as uint16
int64 large = 9223372036854775807;  // Literal inferred as int64
float32 pi = 3.14;        // Literal 3.14 inferred as float32
float64 e = 2.71828;      // Literal 2.71828 inferred as float64
```

If the literal is too large or too small for the target type, you'll get a compile-time error:

```firescript
// int8 overflow = 200;   // ❌ Compile error: 200 exceeds int8 range (-128 to 127)
// uint8 negative = -1;   // ❌ Compile error: -1 invalid for unsigned type
```

**Explicit Type Suffixes:**

You can also explicitly specify the type using a suffix, which is useful in contexts where the type cannot be inferred (like in expressions):

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

Floating point literals can be specified in decimal or scientific notation.

**Type Inference for Literals:**

When you assign a floating-point literal to a variable with an explicit type, the literal automatically takes on that type:

```firescript
float32 pi = 3.14159;              // Literal inferred as float32
float64 e = 2.71828;               // Literal inferred as float64
float128 phi = 1.618033988749;     // Literal inferred as float128
float64 scientific = 6.022e23;     // Scientific notation, inferred as float64
```

**Explicit Type Suffixes:**

You can also explicitly specify the type using a suffix:

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

firescript has strict typing rules and requires explicit type conversions using casting syntax.

### Explicit Type Casting

To convert between types, use Java-style casting with parentheses:

```firescript
// Numeric conversions
int32 intVal = 42;
float64 floatVal = (float64)intVal;     // 42.0

float32 pi = 3.14f32;
int32 truncated = (int32)pi;            // 3 (truncates decimal)

// Between numeric types
int8 small = 100i8;
int64 large = (int64)small;             // 100i64

uint32 unsigned = 42u32;
int32 signed = (int32)unsigned;         // 42i32

// String conversions
string numStr = "42";
int32 parsed = (int32)numStr;           // 42
float64 parsedFloat = (float64)"3.14";  // 3.14

// To string
string str1 = (string)42;               // "42"
string str2 = (string)3.14f32;          // "3.14"
string str3 = (string)true;             // "true"

// Boolean conversions
bool fromString = (bool)"true";         // true
bool fromInt = (bool)1;                 // true (non-zero is true)

// Character conversions
char first = (char)"Hello";             // "H" - first character
```

**Casting Rules:**

1. **Numeric to numeric**: Always allowed, may lose precision or truncate
2. **String to numeric**: Parses the string, throws error if invalid format
3. **Numeric to string**: Converts to string representation
4. **Boolean to string**: "true" or "false"
5. **String to boolean**: "true" → true, anything else → false
6. **Numeric to boolean**: 0 → false, non-zero → true
7. **String to char**: Takes first character

**Invalid Casts:**

Some casts are not allowed and will result in compile-time errors:

```firescript
// int32 x = (int32)[1, 2, 3];  // ❌ Error: Cannot cast array to int32
// bool b = (bool)"hello";       // ⚠️ Runtime error: Invalid boolean string
```

### Mixed-Type Arithmetic

firescript does **not** perform implicit type conversions in arithmetic operations. When performing operations between different types or precisions, you must explicitly cast to the desired result type.

```firescript
int32 a = 10;
int64 b = 20i64;

// int32 result = a + b;  // ❌ Error: Cannot mix int32 and int64

// Must explicitly cast to desired type
int32 result1 = (int32)(a + (int32)b);  // Cast b to int32 first
int64 result2 = (int64)((int64)a + b);  // Cast a to int64 first

// Mixed integer and float
int32 intVal = 5;
float32 floatVal = 2.5f32;

// float32 mixed = intVal + floatVal;  // ❌ Error: Cannot mix int32 and float32

float32 result3 = (float32)((float32)intVal + floatVal);  // Cast int to float
int32 result4 = (int32)((int32)floatVal + intVal);        // Cast float to int (truncates)

// Different float precisions
float32 f32 = 3.14f32;
float64 f64 = 2.71f64;

// float64 sum = f32 + f64;  // ❌ Error: Cannot mix float32 and float64

float64 result5 = (float64)((float64)f32 + f64);  // Cast to float64
float32 result6 = (float32)(f32 + (float32)f64);  // Cast to float32
```

**Design Rationale:**

This explicit approach prevents silent precision loss and makes data type conversions visible in the code, aligning with firescript's philosophy of explicitness and safety.

### String Concatenation

String concatenation with `+` is an exception - it will implicitly convert non-string values to strings:

```firescript
string message = "Count: " + 42;  // "Count: 42" - int32 converted to string
string status = "Active: " + true;  // "Active: true" - bool converted to string
string pi = "Pi is approximately " + 3.14f32;  // Converts float to string
```

## Type Checking and Enforcement

The firescript parser includes a type-checking phase that runs after the initial syntax parsing.

### Static Type Checking

1. **Variable Declarations**: When you declare a variable (`int8 x = 5i8;`), the type checker verifies that the type of the initializer (`5i8`, which is `int8`) matches the declared type (`int8`).

2. **Assignments**: When assigning a value to an existing variable (`x = 10i8;`), the checker ensures the assigned value's type is compatible with the variable's declared type.

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

Generics allow you to write flexible, reusable code that works with multiple types while maintaining type safety. Instead of writing separate functions for each type, you write one generic function that works with any compatible type.

#### Basic Generic Functions

A generic function is declared with type parameters in angle brackets after the function name:

```firescript
T max<T>(T a, T b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}

// Type parameter is inferred from arguments
int8 largerInt = max(5i8, 10i8);        // T inferred as int8
string largerString = max("apple", "banana");  // T inferred as string

// Or explicitly specified
float32 largerFloat = max<float32>(3.14f32, 2.71f32);
```

#### Type Constraints

Type constraints restrict which types can be used with a generic function. This ensures the function only accepts types that support the required operations.

**Interface Constraints:**

```firescript
// T must satisfy the Comparable interface
T max<T: Comparable>(T a, T b) {
    return a > b ? a : b;
}

// T must satisfy the Numeric interface
T add<T: Numeric>(T a, T b) {
    return a + b;
}
```

**Type Union Constraints:**

For simpler cases, you can use type unions to explicitly list which types are allowed:

```firescript
// T can be int32, int64, or float64
T add<T: int32 | int64 | float64>(T a, T b) {
    return a + b;
}

// Works with any of the specified types
int32 result1 = add(5i32, 10i32);        // ✅ Works
float64 result2 = add(3.14f64, 2.71f64); // ✅ Works
// int8 result3 = add(1i8, 2i8);         // ❌ Error: int8 not in union

// Type unions work with any types, including custom classes
class Point { /* ... */ }
class Circle { /* ... */ }

T process<T: Point | Circle>(T shape) {
    // Can work with Point or Circle
    return shape;
}
```

**Multiple Constraints:**

You can combine both interface constraints and type unions:

```firescript
// T must satisfy Comparable AND be in the union
T clamp<T: Comparable & (int32 | float64)>(T value, T min, T max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

// Multiple interface constraints
T process<T: Printable & Drawable>(T item) {
    print(item.toString());
    item.draw();
    return item;
}
```

**When to Use Each:**

- **Interface constraints** (`T: Comparable`): When you need types with specific capabilities, works with any type that implements the interface
- **Type unions** (`T: int32 | float64`): When you want to explicitly list allowed types, simple and explicit
- **Built-in interfaces** (`T: Numeric`, `SignedInt`, `Float`): For common operations across type families

#### Type Union Constraints

Type unions provide a simple, explicit way to define generic constraints by listing the exact types allowed. This is inspired by Python's `Union` but with firescript's explicit syntax.

**Basic Type Unions:**

```firescript
// Simple union - T can be int32 or float64
T convert<T: int32 | float64>(T value) {
    return value;
}

// Multiple types in union
T process<T: int8 | int16 | int32 | int64>(T value) {
    return value * 2;
}

// Works with custom types too
class Dog { /* ... */ }
class Cat { /* ... */ }

T feed<T: Dog | Cat>(T animal) {
    // Feed the animal
    return animal;
}
```

**Combining Unions with Interfaces:**

You can require that types satisfy both an interface AND be in a specific union:

```firescript
// T must be Comparable AND one of these specific types
T max<T: Comparable & (int32 | int64 | float64)>(T a, T b) {
    return a > b ? a : b;
}

// Custom interface with type union
interface Drawable {
    void draw(&this);
}

class Square implements Drawable { /* ... */ }
class Circle implements Drawable { /* ... */ }

// T must implement Drawable AND be one of these types
T render<T: Drawable & (Square | Circle)>(T shape) {
    shape.draw();
    return shape;
}
```

**Type Unions vs. Interfaces:**

```firescript
// Using interface - open-ended, any type that implements Numeric
T addWithInterface<T: Numeric>(T a, T b) {
    return a + b;
}

// Using type union - closed, only these specific types
T addWithUnion<T: int32 | int64 | float64>(T a, T b) {
    return a + b;
}

// Interface: More flexible, allows future types
// Union: More explicit, you know exactly what's allowed
```

**Practical Example:**

```firescript
// Define a function that only works with specific numeric types
T safeDivide<T: float32 | float64>(T a, T b) {
    if (b == 0.0) {
        return 0.0;  // Safe default for floats
    }
    return a / b;
}

float32 result1 = safeDivide(10.0f32, 2.0f32);  // ✅ Works
float64 result2 = safeDivide(10.0f64, 2.0f64);  // ✅ Works
// int32 result3 = safeDivide(10i32, 2i32);     // ❌ Error: int32 not in union
```

#### Built-in Type Constraints

firescript provides several built-in constraint interfaces that are automatically implemented by appropriate types:

**Numeric Constraints:**

- **`Numeric`** - Any numeric type (int, uint, float of any precision)
  - Supports: `+`, `-`, `*`, `/`, `%`, `**`
  - Implemented by: All `intN`, `uintN`, and `floatN` types

- **`Integer`** - Any integer type (signed or unsigned)
  - Supports: All `Numeric` operations plus bitwise operations
  - Implemented by: All `intN` and `uintN` types

- **`SignedInt`** - Signed integers only
  - Supports: All `Integer` operations plus unary negation
  - Implemented by: All `intN` types (`int8`, `int16`, `int32`, `int64`)

- **`UnsignedInt`** - Unsigned integers only
  - Supports: All `Integer` operations
  - Implemented by: All `uintN` types (`uint8`, `uint16`, `uint32`, `uint64`)

- **`Float`** - Floating-point types only
  - Supports: All `Numeric` operations
  - Implemented by: All `floatN` types (`float32`, `float64`, `float128`)

**Behavioral Constraints:**

- **`Comparable`** - Types that can be compared
  - Supports: `<`, `>`, `<=`, `>=`, `==`, `!=`
  - Implemented by: All numeric types, `string`, `char`, `bool`

- **`Equatable`** - Types that support equality testing
  - Supports: `==`, `!=`
  - Implemented by: All built-in types

- **`Copyable`** - Types that can be copied (as opposed to moved)
  - All primitive types are `Copyable`
  - Classes are `Owned` by default (not `Copyable`)

**Examples:**

```firescript
// Works with any numeric type
T square<T: Numeric>(T x) {
    return x * x;
}

// Only works with floating-point types
T sqrt<T: Float>(T value) {
    // Implementation uses floating-point operations
    return __builtin_sqrt(value);
}

// Only works with signed integers
T abs<T: SignedInt>(T value) {
    return value < 0 ? -value : value;
}

// Works with any comparable type
T clamp<T: Comparable>(T value, T min, T max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}
```



#### Multiple Type Parameters

Functions can have multiple generic type parameters:

```firescript
// Convert from one type to another
R convert<T, R>(T value) {
    return cast<R>(value);
}

// Map a function over a value
R map<T, R>(T value, R func(T)) {
    return func(value);
}

// Combine two values of different types
R combine<T1, T2, R: Numeric>(T1 a, T2 b) {
    return cast<R>(a) + cast<R>(b);
}

// With constraints on each parameter
R interpolate<T: Float, R: Float>(T a, T b, R t) {
    return cast<R>(a) + cast<R>((b - a) * cast<T>(t));
}
```

#### Generic Constants and Type-Associated Values

For constants that need to adapt to the type precision, use type-associated constant functions:

```firescript
// Type-associated constants (planned syntax)
T pi<T: float<N>>() {
    // Compiler provides appropriate precision for each float type
    return cast<T>(3.141592653589793238462643383279502884197);
}

T e<T: float<N>>() {
    return cast<T>(2.718281828459045235360287471352662497757);
}

// Usage - type is inferred from context
float32 circumference32(float32 radius) {
    return 2.0f32 * pi<float32>() * radius;
}

float64 circumference64(float64 radius) {
    return 2.0f64 * pi<float64>() * radius;
}

// Or with type inference
float32 area(float32 radius) {
    float32 piValue = pi();  // Type inferred as float32 from variable type
    return piValue * radius * radius;
}
```

#### Type Inference

The firescript compiler can infer generic type parameters from function arguments in most cases:

```firescript
T identity<T>(T value) {
    return value;
}

// Type parameter inferred from argument
int32 x = identity(42i32);        // T inferred as int32
string s = identity("hello");      // T inferred as string

// Explicit type parameter when needed
float64 y = identity<float64>(42); // Converts 42 to float64
```

Type inference follows these rules:

1. If argument types match the parameter types, infer from arguments
2. If return type is known and argument types are ambiguous, infer from return type
3. If neither works, require explicit type parameters
4. All type parameters must be consistently inferred

```firescript
T add<T: Numeric>(T a, T b) {
    return a + b;
}

int32 result1 = add(10i32, 20i32);  // ✅ T inferred as int32
float32 result2 = add(1.5f32, 2.5f32);  // ✅ T inferred as float32

// int32 result3 = add(10i32, 20i64);  // ❌ Error: T cannot be both int32 and int64
```

#### Generic Classes (Planned)

Generic classes will allow creating data structures that work with any type:

```firescript
// Planned syntax
class Box<T> {
    T value;

    Box(&this, T value) {
        this.value = value;
    }

    T getValue(&this) {
        return this.value;
    }

    void setValue(&this, T newValue) {
        this.value = newValue;
    }
}

// Usage
Box<int32> intBox = Box(42i32);
Box<string> strBox = Box("hello");

int32 x = intBox.getValue();    // 42
string s = strBox.getValue();    // "hello"
```

Generic classes with constraints:

```firescript
// Planned syntax
class Pair<T: Comparable> {
    T first;
    T second;

    Pair(&this, T first, T second) {
        this.first = first;
        this.second = second;
    }

    T max(&this) {
        return this.first > this.second ? this.first : this.second;
    }
}
```

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

nullable int32 aliceScore = scores.get("Alice");  // 100
```

#### Implementation Notes

Generics in firescript use **monomorphization** at compile time:

1. When you call a generic function with specific types, the compiler generates a specialized version
2. Each unique combination of type parameters gets its own compiled function
3. This means zero runtime overhead - generic code is as fast as hand-written type-specific code
4. The tradeoff is slightly larger binary size (one copy of the function per type combination used)

```firescript
// You write this once:
T max<T: Comparable>(T a, T b) {
    return a > b ? a : b;
}

// If you call it with int32 and float32:
int32 x = max(5i32, 10i32);
float32 y = max(3.14f32, 2.71f32);

// The compiler generates (conceptually):
int32 max_int32(int32 a, int32 b) { return a > b ? a : b; }
float32 max_float32(float32 a, float32 b) { return a > b ? a : b; }

// And replaces your calls with:
int32 x = max_int32(5i32, 10i32);
float32 y = max_float32(3.14f32, 2.71f32);
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
T add<T: NumericPrimitive>(T a, T b) {
    return a + b;
}

T abs<T: SignedInteger>(T x, T zero) {
    if (x < zero) {
        return -x;
    }
    return x;
}

T clamp<T: FloatingPoint>(T value, T min, T max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}

// Usage is natural
int32 sum = add(10i32, 20i32);          // ✅ Works with NumericPrimitive
float64 clamped = clamp(5.5, 0.0, 10.0); // ✅ Works with FloatingPoint
```

**Combining Constraint Aliases:**

You can combine constraint aliases with other constraints:

```firescript
constraint IntegerType = SignedInteger | UnsignedInteger;

// Combine with interface constraints
T process<T: Comparable & IntegerType>(T value) {
    // T must be comparable AND one of the integer types
    return value;
}

// Combine multiple constraint aliases with unions
constraint AllNumeric = SignedInteger | UnsignedInteger | FloatingPoint;

T compute<T: AllNumeric>(T value) {
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
T area<T: Shape2D>(T shape) {
    // Calculate area for any 2D shape
    return shape.calculateArea();
}

// Can be combined with interfaces
interface Drawable {
    void draw(&this);
}

T render<T: Drawable & Shape2D>(T shape) {
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
// Constraint alias - just a shorthand for a type union
constraint FastInt = int32 | int64;
T add<T: FastInt>(T a, T b) { return a + b; }
// Expands to: T add<T: int32 | int64>(T a, T b)

// Interface - defines required capabilities
interface Printable {
    string toString(&this);
}
T print<T: Printable>(T value) { /* ... */ }
// Requires T to have a toString() method
```

**Scope and Visibility:**

Constraint aliases follow the same scoping rules as other declarations:

```firescript
// Module-level constraint (usable throughout the file)
constraint ModuleNumeric = int32 | float32;

// Within a namespace (planned)
namespace Math {
    constraint PreciseFloat = float64 | float128;
    
    T compute<T: PreciseFloat>(T value) {
        return value;
    }
}

// Import constraints from other modules (planned)
import std.types.{NumericPrimitive, SignedInteger};
```

### Interfaces

Interfaces define a set of capabilities that types can implement. They are used primarily as constraints for generic type parameters, ensuring that generic code only accepts types that support the required operations.

**Key Design Principles:**

1. **Primitive types are closed**: You cannot implement interfaces directly on primitive types like `int32`, `float64`, etc.
2. **Built-in interfaces have compiler support**: Interfaces like `Numeric`, `Comparable`, etc. work with primitives through compiler magic.
3. **Custom interfaces need wrappers**: For custom interfaces, create wrapper classes or use standard library wrappers.
4. **Classes use `implements`**: Custom classes declare interfaces using the `implements` keyword (Java-style).

```firescript
// Built-in interfaces work with primitives (compiler support)
T max<T: Comparable>(T a, T b) { return a > b ? a : b; }
int32 result = max(5i32, 10i32);  // ✅ Works

// Custom interfaces need wrapper classes
interface Printable {
    string toString(&this);
}

class PrintableInt implements Printable {
    int32 value;
    string toString(&this) { return toString(this.value); }
}
```

#### Defining an Interface

An interface is defined using the `interface` keyword followed by the interface name and a body:

```firescript
// Basic interface definition
interface Printable {
    // Method signature that implementing types must provide
    string toString(&this);
}

// Interface with multiple methods
interface Drawable {
    void draw(&this);
    void move(&this, int32 x, int32 y);
    bool isVisible(&this);
}
```

#### Interface Inheritance

Interfaces can inherit from other interfaces, creating a hierarchy of capabilities:

```firescript
// Base interface
interface Equatable {
    bool equals(&this, &this other);
}

// Child interface inherits parent's requirements
interface Comparable from Equatable {
    int32 compare(&this, &this other);  // Returns -1, 0, or 1
}

// Types implementing Comparable must also implement Equatable
```

#### Implementing Interfaces for Types

Classes declare which interfaces they implement using the `implements` keyword:

```firescript
// Define a class that implements an interface
class Point implements Printable {
    float32 x;
    float32 y;
    
    Point(&this, float32 x, float32 y) {
        this.x = x;
        this.y = y;
    }
    
    // Implement the required method from Printable
    string toString(&this) {
        return "Point(" + toString(this.x) + ", " + toString(this.y) + ")";
    }
}

// Implement multiple interfaces
class Circle implements Drawable, Printable {
    float32 radius;
    
    Circle(&this, float32 radius) {
        this.radius = radius;
    }
    
    // Implement Drawable methods
    void draw(&this) {
        print("Drawing circle with radius " + toString(this.radius));
    }
    
    void move(&this, int32 dx, int32 dy) {
        // Movement logic
    }
    
    bool isVisible(&this) {
        return true;
    }
    
    // Implement Printable method
    string toString(&this) {
        return "Circle(radius=" + toString(this.radius) + ")";
    }
}
```

#### Primitives with Generic Constraints

Built-in interfaces like `Numeric`, `Comparable`, etc. work directly with primitive types through compiler magic. You don't need wrappers for these:

```firescript
// Built-in interfaces work with primitives directly
T max<T: Comparable>(T a, T b) {
    return a > b ? a : b;
}

int32 result = max(5i32, 10i32);  // ✅ Works! No wrapper needed
float64 fResult = max(3.14f64, 2.71f64);  // ✅ Works!

// This is compiler magic - the compiler knows int32 satisfies Comparable
```

**For custom interfaces, you need wrappers:**

```firescript
// Custom interface
interface Printable {
    string toString(&this);
}

// This won't work with primitives directly
void printValue<T: Printable>(T value) {
    print(value.toString());
}

// printValue(42i32);  // ❌ Error: int32 does not implement Printable

// Create a wrapper class
class PrintableInt implements Printable {
    int32 value;
    
    PrintableInt(&this, int32 value) {
        this.value = value;
    }
    
    string toString(&this) {
        return "Value: " + toString(this.value);
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
// Function that works with any Printable type
void printValue<T: Printable>(T value) {
    print(value.toString());
}

// Function that works with any Drawable type
void renderAll<T: Drawable>(T[] items) {
    for (int32 i = 0; i < items.length; i = i + 1) {
        items[i].draw();
    }
}

// Multiple interface constraints
void processItem<T: Printable & Drawable>(T item) {
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
    float32 x;
    float32 y;
    
    // No methods to implement - just marks Point as copyable and serializable
    Point(&this, float32 x, float32 y) {
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
T add<T: Numeric>(T a, T b) {
    return a + b;
}

int32 sum = add(5i32, 10i32);  // ✅ Compiler knows int32 satisfies Numeric

// Custom classes must explicitly implement
class MyNumber implements Numeric {
    int32 value;
    
    MyNumber(&this, int32 value) {
        this.value = value;
    }
    
    // Must implement Numeric operations...
}
```

#### Combining Interface Constraints

You can combine multiple interface constraints to require specific capabilities:

```firescript
// Works with any signed integer precision
T negate<T: SignedInt>(T value) {
    return -value;
}

// Works with any float precision
T normalize<T: Float>(T value, T min, T max) {
    return (value - min) / (max - min);
}

// Combine interface constraints
T clamp<T: Comparable & Numeric>(T value, T min, T max) {
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
    int32 compare(&this, &this other);
    
    // Default implementations based on compare()
    bool lessThan(&this, &this other) {
        return this.compare(other) < 0;
    }
    
    bool greaterThan(&this, &this other) {
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
    
    Item get(&this, int32 index);
    void set(&this, int32 index, Item value);
    int32 size(&this);
}

impl Container for IntArray {
    type Item = int32;  // Specify the associated type
    
    int32 get(&this, int32 index) {
        return this.data[index];
    }
    
    void set(&this, int32 index, int32 value) {
        this.data[index] = value;
    }
    
    int32 size(&this) {
        return this.length;
    }
}
```

#### Interface Objects (Planned)

In the future, interfaces may be used as types themselves, allowing for dynamic dispatch:

```firescript
// Planned syntax
void printAll(Printable[] items) {  // Array of interface objects
    for (int32 i = 0; i < items.length; i = i + 1) {
        print(items[i].toString());
    }
}

// Can pass any type implementing Printable
Point p = Point(1.0f32, 2.0f32);
Circle c = Circle(3.0f32);
Printable[] mixed = [p, c];  // Different types, same interface
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
    string read(&this);
}

interface Writable {
    void write(&this, string data);
}

interface Seekable {
    void seek(&this, int64 position);
}

// Can combine them as needed
class File implements Readable, Writable, Seekable {
    // ... fields ...
    
    // Implement all required methods
    string read(&this) { /* ... */ }
    void write(&this, string data) { /* ... */ }
    void seek(&this, int64 position) { /* ... */ }
}

// Bad: One monolithic interface
interface FileOperations {
    string read(&this);
    void write(&this, string data);
    void seek(&this, int64 position);
    bool exists(&this);
    void delete(&this);
    // Too many unrelated operations!
}
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

* ✅ All integer types (`int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`)
* ✅ All floating point types (`float32`, `float64`, `float128`)
* ✅ Nullable type modifiers
* ✅ Arrays of Copyable types
* ✅ Static type checking for expressions and assignments
* ⚠️ Explicit type casting (only for numeric types at present)

Not yet implemented:

* ❌ Type inference on variable declarations
* ❌ Type introspection with `typeof`
* ❌ Tuples
* ❌ Interfaces (syntax and semantics documented, implementation pending)
  * ❌ Interface definitions (`interface Name { }`)
  * ❌ Interface inheritance (`interface Child from Parent { }`)
  * ❌ Interface implementations (`class Type implements Interface { }`)
  * ❌ Built-in interfaces with compiler support (Numeric, Comparable, etc.)
  * ❌ Primitive type wrapper classes (`Integer`, `Float`, etc.)
  * ❌ Marker interfaces
  * ❌ Default implementations in interfaces
  * ❌ Associated types
  * ❌ Interface objects / dynamic dispatch
* ❌ Generics (syntax and semantics documented, implementation pending)
  * ❌ Generic functions
  * ❌ Type constraints with interfaces
  * ❌ Type union constraints (`T: int32 | float64`)
  * ❌ Generic classes
  * ❌ Type inference for generics
* ❌ User-defined types (classes)
* ❌ Function types

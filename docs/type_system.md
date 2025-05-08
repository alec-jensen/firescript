# Type System in firescript

firescript employs a static type system to enhance code reliability and catch errors early during the compilation phase. This means that the type of every variable and expression is checked before the code is run.

## Built-in Types

firescript provides several fundamental data types:

* **`int`**: Represents whole numbers (integers). Example: `int age = 30`
* **`float`**: Represents single-precision floating-point numbers. Example: `float price = 19.95`
* **`double`**: Represents double-precision floating-point numbers, offering higher precision than `float`. Example: `double pi = 3.1415926535`
* **`bool`**: Represents boolean values, either `true` or `false`. Example: `bool isActive = true`
* **`string`**: Represents sequences of characters. Example: `string message = "Hello, World!"`
* **`char`**: Represents a single character. (Note: Currently handled similarly to strings in some contexts, formal `char` type might be refined). Example: `char initial = "A"`
* **`void`**: Represents the absence of a type, primarily used as the return type for functions that do not return a value.

## Type Semantics

### Integer Type (`int`)

The `int` type in firescript represents integers with arbitrary precision. There is no explicit size limit as in languages like C/C++, making it similar to Python integers that can grow as needed.

```firescript
int small = 42
int large = 9223372036854775807  // Large integers are supported
int calculation = (small + large) * 2  // Arithmetic operations
```

Integers support the following operations:
- Arithmetic: `+`, `-`, `*`, `/`, `%` (modulo), `**` (power)
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`
- Bit manipulation (planned but not yet implemented): `&`, `|`, `^`, `~`, `<<`, `>>`

### Floating Point Types (`float` and `double`)

The `float` type represents 32-bit floating-point numbers, while `double` represents 64-bit floating-point numbers with greater precision.

```firescript
float simpleDecimal = 3.14
double highPrecision = 3.141592653589793

// Scientific notation
double avogadro = 6.022e23
float tiny = 1.6e-19
```

Floating point numbers support:
- Arithmetic: `+`, `-`, `*`, `/`, `**` (power)
- Comparison: `==`, `!=`, `<`, `>`, `<=`, `>=`

### Boolean Type (`bool`)

The `bool` type has only two possible values: `true` and `false`. It's commonly used in conditional expressions.

```firescript
bool userLoggedIn = true
bool hasPermission = false

// Boolean operations
bool canAccess = userLoggedIn && hasPermission  // Logical AND
bool needsAttention = !userLoggedIn || !hasPermission  // Logical OR and NOT
```

Boolean values support:
- Logical operations: `&&` (AND), `||` (OR), `!` (NOT)
- Comparison: `==`, `!=`

### String Type (`string`)

The `string` type represents sequences of characters. Strings in firescript are immutable (cannot be changed after creation).

```firescript
string greeting = "Hello"
string name = "World"
string message = greeting + ", " + name + "!"  // String concatenation with +

// Multi-line strings
string paragraph = "This is a
multi-line
string"
```

Strings support:
- Concatenation: `+`
- Comparison: `==`, `!=`

### Character Type (`char`)

The `char` type represents a single character and is currently implemented as a string with length 1.

```firescript
char letter = "A"
char digit = "7"
char newline = "\n"  // Special character
```

### Arrays

Arrays are ordered collections of elements of the same type.

#### Declaration and Initialization

```firescript
// With initial values
int[] numbers = [1, 2, 3, 4, 5]
string[] fruits = ["apple", "banana", "cherry"]

// Empty array
bool[] flags = []
```

#### Array Operations

```firescript
int[] scores = [85, 92, 78]

// Accessing elements (zero-based indexing)
int firstScore = scores[0]  // 85

// Modifying elements
scores[1] = 95  // Array becomes [85, 95, 78]

// Array methods
scores.append(88)  // Add to end: [85, 95, 78, 88]
scores.insert(2, 82)  // Insert at index: [85, 95, 82, 78, 88]
int removed = scores.pop()  // Remove last: removed = 88, array = [85, 95, 82, 78]
removed = scores.pop(1)  // Remove at index: removed = 95, array = [85, 82, 78]

// Array properties
int count = scores.length  // 3

// Clearing arrays
scores.clear()  // Array becomes []
```

## Nullability

By default, variables cannot hold the value `null`. To allow a variable to be assigned `null`, you must explicitly declare it as `nullable`.

### Declaring Nullable Variables

```firescript
nullable string username = null  // Allowed
string title = "Default"

// title = null  // Error: Cannot assign null to non-nullable type 'string'

username = "John"  // Can be assigned a non-null value later
```

### Working with Nullable Values

When working with nullable variables, it's important to check for null before using them:

```firescript
nullable string data = null

// Safe pattern
if (data != null) {
    print(data)
}

// Could cause a runtime error if not checked
print(data)  // Might try to print null
```

## Type Compatibility and Conversions

firescript has strict typing rules but provides explicit conversion functions for common type conversions.

### Built-in Type Conversion Functions

```firescript
// String to numeric conversions
string numStr = "42"
int num = toInt(numStr)         // 42
float floatVal = toFloat("3.14")  // 3.14
double doubleVal = toDouble("2.71828")  // 2.71828

// Numeric to string conversions
string strFromInt = toString(42)     // "42"
string strFromFloat = toString(3.14)  // "3.14"

// Boolean conversions
bool boolValue = toBool("true")  // true
string strFromBool = toString(false)  // "false"

// Character conversion
char first = toChar("Hello")  // "H" - first character of string
```

### Implicit Type Conversions

firescript generally does not perform implicit type conversions, with some exceptions:

1. In binary numeric operations (`+`, `-`, `*`, `/`, etc.) between different numeric types:
   - If one operand is `double`, the result is `double`
   - If one operand is `float` and the other is `int`, the result is `float`

```firescript
int intVal = 5
float floatVal = 2.5
double doubleVal = 3.14

float result1 = intVal + floatVal    // Result is float 7.5
double result2 = floatVal * doubleVal  // Result is double 7.85
```

2. String concatenation with `+` will convert non-string values to strings:

```firescript
string message = "Count: " + 42  // "Count: 42"
string status = "Active: " + true  // "Active: true"
```

## Type Checking and Enforcement

The firescript parser includes a type-checking phase that runs after the initial syntax parsing.

### Static Type Checking

1. **Variable Declarations**: When you declare a variable (`int x = 5`), the type checker verifies that the type of the initializer (`5`, which is `int`) matches the declared type (`int`).

2. **Assignments**: When assigning a value to an existing variable (`x = 10`), the checker ensures the assigned value's type is compatible with the variable's declared type.

3. **Expressions**: Operators (`+`, `-`, `*`, `/`, `==`, `>`, etc.) are checked to ensure they are used with compatible operand types. For example, arithmetic operators generally require numeric types (`int`, `float`, `double`), while `+` can also be used for string concatenation. The result type of an expression is also determined (e.g., `1 + 2.0` results in a `float`).

4. **Function Calls**: Arguments passed to functions are checked against the expected parameter types. The return value type is also enforced.

5. **Method Calls**: Similar to functions, arguments and the object the method is called on are type-checked.

6. **Array Operations**: Indexing requires an integer, and assigning elements requires matching the array's element type.

### Type Errors

Type errors found during the checking phase will prevent the code from compiling further, providing early feedback on potential issues:

```firescript
string name = "John"
int age = 30

age = "thirty"  // Type error: Cannot assign string to int
name = 25       // Type error: Cannot assign int to string
bool result = age + name  // Type error: Cannot add int and string
                         // Also cannot assign result to bool
```

## Type Introspection

The `typeof` built-in function returns a string representing the type of a value:

```firescript
string type1 = typeof(42)        // "int"
string type2 = typeof(3.14)      // "float"
string type3 = typeof("hello")   // "string"
string type4 = typeof(true)      // "bool"
string type5 = typeof([1, 2, 3]) // "int[]"
```

## Advanced Type Features (Planned)

The following advanced type features are planned but not yet implemented:

### Tuples

Tuples will allow grouping of values with different types:

```firescript
// Future syntax
tuple<int, string> person = (30, "John")
int age = person[0]  // 30
string name = person[1]  // "John"
```

### Generics

Generic types will allow for more flexible and reusable code:

```firescript
// Future syntax
T max<T>(T a, T b) {
    if (a > b) {
        return a
    } else {
        return b
    }
}

int largerInt = max<int>(5, 10)  // 10
string largerString = max<string>("apple", "banana")  // "banana"
```

### User-Defined Types (Classes)

Classes will enable user-defined types with methods and properties:

```firescript
// Future syntax
class Point {
    float x
    float y
    
    Point(this, float x, float y) {
        this.x = x
        this.y = y
    }
    
    float distanceTo(this, Point other) {
        float dx = this.x - other.x
        float dy = this.y - other.y
        return toFloat((dx * dx + dy * dy) ** 0.5)
    }
}
```

## Implementation Status

The current firescript compiler supports:
- ✅ All primitive types: `int`, `float`, `double`, `bool`, `string`, `char`
- ✅ Nullable type modifiers
- ✅ Arrays of primitive types
- ✅ Static type checking for expressions and assignments
- ✅ Type conversion functions
- ✅ Type introspection with `typeof`

Not yet implemented:
- ❌ Tuples
- ❌ Generics
- ❌ User-defined types (classes)
- ❌ Interface types
- ❌ Function types

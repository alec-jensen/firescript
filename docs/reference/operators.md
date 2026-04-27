# Operators

> This is the canonical reference for all firescript operators. Operators mentioned in passing elsewhere in the docs (e.g., `type_system.md`, `control_flow.md`) defer to this page for full definitions.

## Arithmetic Operators

Arithmetic operators work on numeric types (`intN`, `uintN`, `floatN`). There are no implicit type conversions — both operands must be the same type, or you must cast explicitly before the operation.

| Operator | Name | Example |
|----------|------|---------|
| `+` | Addition | `a + b` |
| `-` | Subtraction | `a - b` |
| `*` | Multiplication | `a * b` |
| `/` | Division | `a / b` |
| `%` | Modulo | `a % b` |
| `**` | Power (exponentiation) | `a ** b` |

```firescript
int32 a = 10;
int32 b = 3;

int32 sum  = a + b;   // 13
int32 diff = a - b;   // 7
int32 prod = a * b;   // 30
int32 quot = a / b;   // 3  (integer division truncates toward zero)
int32 rem  = a % b;   // 1
int32 pow  = a ** b;  // 1000
```

Integer division truncates toward zero. Modulo returns the remainder with the same sign as the dividend (C-style, not Python-style).

The `+` operator is also used for string concatenation. When one operand is a `string`, the other is implicitly converted to a string. This is the only implicit conversion in the language.

```firescript
string msg = "Value: " + 42;  // "Value: 42"
```

## Assignment Operators

The basic assignment operator `=` stores a value in a variable. For Owned types (strings, arrays, user-defined classes), assignment performs a **move** — the source is invalidated. For Copyable types (`intN`, `floatN`, `bool`), assignment performs a bitwise copy.

```firescript
int32 x = 10;
x = 20;         // x is now 20

string a = "hello";
string b = a;   // a is moved into b; a is no longer valid
```

See [Memory Management](memory_management.md) for full move/copy semantics.

## Compound Assignment Operators

Compound assignment operators combine an arithmetic operation with assignment. They are equivalent to `x = x OP expr` and require both sides to be the same type.

| Operator | Equivalent to |
|----------|---------------|
| `+=` | `x = x + expr` |
| `-=` | `x = x - expr` |
| `*=` | `x = x * expr` |
| `/=` | `x = x / expr` |
| `%=` | `x = x % expr` |
| `**=` | `x = x ** expr` |

```firescript
int32 n = 10;
n += 5;   // n = 15
n -= 3;   // n = 12
n *= 2;   // n = 24
n /= 4;   // n = 6
n %= 4;   // n = 2
n **= 3;  // n = 8
```

## Increment and Decrement Operators

The postfix `++` and `--` operators increment or decrement a numeric variable by 1 in-place. Only the postfix form is supported; prefix `++x` is not.

| Operator | Name | Equivalent to |
|----------|------|---------------|
| `x++` | Post-increment | `x = x + 1` |
| `x--` | Post-decrement | `x = x - 1` |

```firescript
int32 i = 0;
i++;   // i = 1
i++;   // i = 2
i--;   // i = 1
```

These are most commonly used in `for` loop increments:

```firescript
for (int32 i = 0; i < 5; i++) {
    // i = 0, 1, 2, 3, 4
}
```

⚠️ **Note:** `++` and `--` are statements, not expressions. Using them as values (e.g., `int32 j = i++`) is not supported.

## Comparison Operators

Comparison operators evaluate to `bool`. Both operands must be the same type.

| Operator | Meaning |
|----------|---------|
| `==` | Equal |
| `!=` | Not equal |
| `<` | Less than |
| `>` | Greater than |
| `<=` | Less than or equal |
| `>=` | Greater than or equal |

```firescript
int32 a = 5;
int32 b = 10;

bool eq  = a == b;  // false
bool neq = a != b;  // true
bool lt  = a < b;   // true
bool gt  = a > b;   // false
bool lte = a <= b;  // true
bool gte = a >= b;  // false
```

Strings support `==` and `!=` for equality by value. Ordering comparisons (`<`, `>`, etc.) on strings are not supported.

## Logical Operators

Logical operators work on `bool` values and produce a `bool` result. `&&` and `||` use short-circuit evaluation — the right operand is only evaluated if the left operand does not determine the result.

| Operator | Name | Description |
|----------|------|-------------|
| `&&` | Logical AND | `true` only if both operands are `true` |
| `\|\|` | Logical OR | `true` if at least one operand is `true` |
| `!` | Logical NOT | Inverts a `bool` value |

```firescript
bool a = true;
bool b = false;

bool and = a && b;  // false
bool or  = a || b;  // true
bool not = !a;      // false
```

Short-circuit examples:

```firescript
// right side is never evaluated if left is false
bool result = isReady() && doWork();

// right side is never evaluated if left is true
bool fallback = hasCache() || loadFromDisk();
```

## Cast Operator

The `as` operator performs an explicit type conversion. It is a postfix operator with higher precedence than arithmetic. Parentheses are recommended when mixing with other operators for clarity.

```firescript
expr as TargetType
```

Supported conversions:

- Between any numeric types (`intN`, `uintN`, `floatN`)
- Numeric to `string` and `string` to numeric
- Numeric to `bool` (zero → `false`, non-zero → `true`)
- `string` to `bool` (`"true"` → `true`, anything else → `false`)

```firescript
int16 small  = 300i16;
int32 wide   = small as int32;   // widening: 300
int8  narrow = small as int8;    // narrowing: truncates to fit

float64 pi  = 3.14159f64;
int32   ipi = pi as int32;       // 3 (truncates toward zero)

string s = 42 as string;         // "42"
int32  n = "100" as int32;       // 100

bool fromInt = 1 as bool;        // true
bool fromStr = "true" as bool;   // true
```

⚠️ **Note:** Java/C-style casts (`(int32)value`) are not supported. Always use the postfix `as` form.

## Ternary Operator

❌ **Not yet implemented.**

The ternary operator is planned with the following syntax:

```firescript
condition ? trueValue : falseValue
```

Use an `if/else` block in the meantime:

```firescript
// Instead of: int32 abs = x < 0 ? -x : x;
int32 abs = 0;
if (x < 0) {
    abs = -x;
} else {
    abs = x;
}
```

## Bitwise Operators

❌ **Not yet implemented.**

The following bitwise operators are planned for integer types:

| Operator | Name |
|----------|------|
| `&` | Bitwise AND |
| `\|` | Bitwise OR |
| `^` | Bitwise XOR |
| `~` | Bitwise NOT |
| `<<` | Left shift |
| `>>` | Right shift |

## Operator Precedence

Operators are evaluated in the following order (highest precedence first). Operators on the same row have equal precedence and associate left-to-right unless noted.

| Level | Operators | Associativity |
|-------|-----------|---------------|
| 1 (highest) | `!` `-` `+` (unary) | Right |
| 2 | `**` | Right |
| 3 | `*` `/` `%` | Left |
| 4 | `+` `-` | Left |
| 5 | `<` `>` `<=` `>=` | Left |
| 6 | `==` `!=` | Left |
| 7 | `&&` | Left |
| 8 | `\|\|` | Left |
| 9 | `as` | Left |
| 10 (lowest) | `=` `+=` `-=` `*=` `/=` `%=` `**=` | Right |

Use parentheses to make evaluation order explicit when combining operators from different levels:

```firescript
int32 result = 2 + 3 * 4;          // 14 (not 20)
int32 result = (2 + 3) * 4;        // 20

bool check = a + 1 > b && c != 0;  // ((a + 1) > b) && (c != 0)
```

## Array Operators

❌ **Not yet implemented.**

The following operators are planned for arrays:

```firescript
// Future syntax
int8[3] a = [1, 2, 3];
int8[3] b = [4, 5, 6];

// add arrays element-wise
int8[3] c = a + b;  // Would be [5, 7, 9]

// subtract arrays element-wise
int8[3] e = b - a;  // Would be [3, 3, 3]

// add scalar to array
int8[3] g = a + 2;  // Would be [3, 4, 5]

// subtract scalar from array
int8[3] h = b - 1;  // Would be [3, 4, 5]

// multiply arrays element-wise
int8[3] j = a * b;  // Would be [4, 10, 18]

// divide arrays element-wise
int8[3] k = b / a;  // Would be [4, 2, 2]

// multiply arrays by scalar
int8[3] d = a * 2;  // Would be [2, 4, 6]

// divide arrays by scalar
int8[3] f = b / 2;  // Would be [2, 2, 3]

// dot product of two arrays
int8 dotProduct = a . b;  // Would be 32 (1*4 + 2*5 + 3*6)
```

## Implementation Status

| Operator group | Status |
|----------------|--------|
| Arithmetic (`+` `-` `*` `/` `%` `**`) | ✅ Implemented |
| Assignment (`=`) | ✅ Implemented |
| Compound assignment (`+=` `-=` `*=` `/=` `%=` `**=`) | ✅ Implemented |
| Increment / decrement (`++` `--`) | ✅ Implemented |
| Comparison (`==` `!=` `<` `>` `<=` `>=`) | ✅ Implemented |
| Logical (`&&` `\|\|` `!`) | ✅ Implemented |
| Cast (`as`) | ✅ Implemented |
| Ternary (`? :`) | ❌ Planned |
| Bitwise (`&` `\|` `^` `~` `<<` `>>`) | ❌ Planned |
| Array operators (`+` `-` `*` `/` `.`) | ❌ Planned |

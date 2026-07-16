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
a: int32 = 10;
b: int32 = 3;

sum: int32  = a + b;   // 13
diff: int32 = a - b;   // 7
prod: int32 = a * b;   // 30
quot: int32 = a / b;   // 3  (integer division truncates toward zero)
rem: int32  = a % b;   // 1
pow: int32  = a ** b;  // 1000
```

Integer division truncates toward zero. Modulo returns the remainder with the same sign as the dividend (C-style, not Python-style).

The `+` operator is also used for string concatenation. Both operands must be strings — there is no implicit conversion. Cast non-string values explicitly with `as`:

```firescript
msg: string = "Value: " + (42 as string);  // "Value: 42"
// string bad = "Value: " + 42;           // ❌ Error: cannot concatenate string and int32
```

## Assignment Operators

The basic assignment operator `=` stores a value in a variable. For Owned types (strings, arrays, user-defined classes), assignment performs a **move** — the source is invalidated. For Copyable types (`intN`, `floatN`, `bool`), assignment performs a bitwise copy.

```firescript
x: int32 = 10;
x = 20;         // x is now 20

a: string = "hello";
b: string = a;   // a is moved into b; a is no longer valid
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
n: int32 = 10;
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
i: int32 = 0;
i++;   // i = 1
i++;   // i = 2
i--;   // i = 1
```

These are most commonly used in `for` loop increments:

```firescript
for (i: int32 = 0; i < 5; i++) {
    // i = 0, 1, 2, 3, 4
}
```

⚠️ **Note:** `++` and `--` are statements, not expressions. Using them as values (e.g., `j: int32 = i++`) is not supported.

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
a: int32 = 5;
b: int32 = 10;

eq: bool  = a == b;  // false
neq: bool = a != b;  // true
lt: bool  = a < b;   // true
gt: bool  = a > b;   // false
lte: bool = a <= b;  // true
gte: bool = a >= b;  // false
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
a: bool = true;
b: bool = false;

and: bool = a && b;  // false
or: bool  = a || b;  // true
not: bool = !a;      // false
```

Short-circuit examples:

```firescript
// right side is never evaluated if left is false
result: bool = isReady() && doWork();

// right side is never evaluated if left is true
fallback: bool = hasCache() || loadFromDisk();
```

## Cast Operator

The `as` operator performs an explicit type conversion. It is a postfix operator with higher precedence than arithmetic. Parentheses are recommended when mixing with other operators for clarity.

```firescript
expr as TargetType
```

Supported conversions:

- Between any numeric types (`intN`, `uintN`, `floatN`)
- `string` to numeric
- Built-in types to `string` (numeric types, `bool`, `char`)

Casts *to* `bool` or `char` are not supported.

```firescript
small: int16  = 300i16;
wide: int32   = small as int32;   // widening: 300
narrow: int8 = small as int8;    // narrowing: truncates to fit

pi: float64  = 3.14159f64;
ipi: int32 = pi as int32;       // 3 (truncates toward zero)

s: string = 42 as string;         // "42"
n: int32 = "100" as int32;       // 100

t: string = true as string;       // "true"
```

⚠️ **Note:** Java/C-style casts (`(int32)value`) are not supported. Always use the postfix `as` form.

## Ternary Operator

**[PLANNED] — not yet implemented.**

A ternary expression is planned using the reserved `ternary` keyword:

```firescript
// Future syntax
max: int8 = ternary a > b then a else b;
```

Use an `if/else` block in the meantime:

```firescript
// Instead of a ternary expression:
abs: int32 = 0;
if (x < 0) {
    abs = -x;
} else {
    abs = x;
}
```

## Bitwise Operators

**[PLANNED] — not yet implemented.**

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
| 1 (highest) | `as` (postfix cast) | Left |
| 2 | `!` `-` `+` (unary) | Right |
| 3 | `**` | Right |
| 4 | `*` `/` `%` | Left |
| 5 | `+` `-` | Left |
| 6 | `<` `>` `<=` `>=` | Left |
| 7 | `==` `!=` | Left |
| 8 | `&&` | Left |
| 9 | `\|\|` | Left |
| 10 (lowest) | `=` `+=` `-=` `*=` `/=` `%=` `**=` | Right |

Use parentheses to make evaluation order explicit when combining operators from different levels:

```firescript
result: int32 = 2 + 3 * 4;          // 14 (not 20)
result: int32 = (2 + 3) * 4;        // 20

check: bool = a + 1 > b && c != 0;  // ((a + 1) > b) && (c != 0)
```

## Array Operators

**[PLANNED] — not yet implemented.**

The following operators are planned for arrays:

```firescript
// Future syntax
a: int8[3] = [1, 2, 3];
b: int8[3] = [4, 5, 6];

// add arrays element-wise
c: int8[3] = a + b;  // Would be [5, 7, 9]

// subtract arrays element-wise
e: int8[3] = b - a;  // Would be [3, 3, 3]

// add scalar to array
g: int8[3] = a + 2;  // Would be [3, 4, 5]

// subtract scalar from array
h: int8[3] = b - 1;  // Would be [3, 4, 5]

// multiply arrays element-wise
j: int8[3] = a * b;  // Would be [4, 10, 18]

// divide arrays element-wise
k: int8[3] = b / a;  // Would be [4, 2, 2]

// multiply arrays by scalar
d: int8[3] = a * 2;  // Would be [2, 4, 6]

// divide arrays by scalar
f: int8[3] = b / 2;  // Would be [2, 2, 3]

// dot product of two arrays
dotProduct: int8 = a . b;  // Would be 32 (1*4 + 2*5 + 3*6)
```

## Implementation Status

| Operator group | Status |
|----------------|--------|
| Arithmetic (`+` `-` `*` `/` `%` `**`) | [IMPLEMENTED] |
| Assignment (`=`) | [IMPLEMENTED] |
| Compound assignment (`+=` `-=` `*=` `/=` `%=` `**=`) | [IMPLEMENTED] |
| Increment / decrement (`++` `--`) | [IMPLEMENTED] |
| Comparison (`==` `!=` `<` `>` `<=` `>=`) | [IMPLEMENTED] |
| Logical (`&&` `\|\|` `!`) | [IMPLEMENTED] |
| Cast (`as`) | [IMPLEMENTED] |
| Ternary | [PLANNED] |
| Bitwise (`&` `\|` `^` `~` `<<` `>>`) | [PLANNED] |
| Array operators (`+` `-` `*` `/` `.`) | [PLANNED] |

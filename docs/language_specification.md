# firescript Language Specification

This document serves as the formal reference for the firescript programming language's syntax and semantics.

## 1. Lexical Structure

### Character Set

firescript source files are Unicode text files. The lexical grammar is defined in terms of Unicode code points.

### Comments

```firescript
// Single line comment

/* Multi-line
   comment */
```

### Tokens

- **Keywords**: `if`, `else`, `elif`, `while`, `for`, `break`, `continue`, `return`, `nullable`, `generator`, `const`, `ternary`, `int`, `float`, `double`, `bool`, `string`, `tuple`
- **Operators**: Assignment (`=`), Arithmetic (`+`, `-`, `*`, `/`, `%`, `**`), Comparison (`==`, `!=`, `>`, `<`, `>=`, `<=`), Logical (`&&`, `||`, `!`)
- **Separators**: `;`, `,`, `.`, `(`, `)`, `[`, `]`, `{`, `}`
- **Literals**: Integer, floating-point, double, boolean, string, null

## 2. Types

### Primitive Types

- `int`: Integer numbers with arbitrary precision
- `float`: Single-precision floating-point numbers
- `double`: Double-precision floating-point numbers
- `bool`: Boolean values (`true` or `false`)
- `string`: Text strings
- `char`: Single characters (currently handled similarly to strings)

### Nullability

By default, variables cannot hold the value `null`. The `nullable` keyword must be used to explicitly allow variables to be assigned `null`.

```firescript
nullable string name = null;  // Valid
string title = null;          // Invalid - cannot assign null to non-nullable type
```

### Arrays

Arrays are ordered collections of elements of the same type.

```firescript
int[] numbers = [1, 2, 3];
string[] names = ["Alice", "Bob"];
```

## 3. Variable Declarations and Assignments

### Declaration Syntax

```firescript
[nullability-modifier] [const-modifier] type identifier = expression;
```

### Examples

```firescript
int count = 10;
nullable string message = null;
const float PI = 3.14;
bool isActive = true;
```

## 4. Expressions

### Primary Expressions

- Variables: `x`
- Literals: `42`, `3.14`, `"hello"`, `true`, `null`
- Parenthesized expressions: `(x + y)`
- Function calls: `print("Hello")`
- Method calls: `array.append(5)`
- Array access: `scores[0]`

### Operators (in order of precedence)

1. Method/property access: `.`
2. Array access: `[]`
3. Function call: `()`
4. Unary: `+`, `-`, `!`
5. Power: `**`
6. Multiplicative: `*`, `/`, `%`
7. Additive: `+`, `-`
8. Relational: `<`, `>`, `<=`, `>=`
9. Equality: `==`, `!=`
10. Logical AND: `&&`
11. Logical OR: `||`
12. Assignment: `=`, `+=`, `-=`, `*=`, `/=`, `%=`, `**=`

## 5. Control Flow

### Conditional Statements

```firescript
if condition {
    // then branch
} else if otherCondition {
    // else-if branch
} else {
    // else branch
}
```

### While Loop

```firescript
while condition {
    // body
}
```

## 6. Functions

### Built-in Functions

- `print(value)`: Output a value
- `input(prompt)`: Read string from console
- `toInt(x)`, `toFloat(x)`, `toDouble(x)`, `toBool(x)`, `toString(x)`, `toChar(x)`: Type conversions
- `typeof(x)`: Returns type name

### User-defined Functions (Syntax)

```firescript
returnType functionName(paramType1 param1, paramType2 param2) {
    // function body
    return expression;
}
```

## 7. Arrays

### Operations

- `append(element)`: Add to end
- `insert(index, element)`: Insert at position
- `pop(index?)`: Remove and return element; default removes last
- `clear()`: Remove all elements
- `length`: Property for size

## 8. Scoping Rules

A new scope is created by any set of curly braces `{}`. Variables declared in an inner scope are not accessible in outer scopes. Variables declared in an outer scope are accessible in inner scopes. Variable shadowing is not allowed.

## 9. Syntax Flexibility

### Whitespace Handling

firescript is flexible with whitespace, which means that spaces, tabs, and line breaks are largely ignored by the compiler. While proper formatting with indentation and spacing is recommended for readability, the language allows code to be written in a more compact form.

For example, the following well-formatted code:

```firescript
int x = 1;
x += 2;
print(x);
int i = 0;
while (i < 10) {
    x += i;
    i++;
    print(x);
}
```

Could also be written as a single line with no spacing:

```firescript
intx=1;x+=2;print(x);inti=0;while(i<10){x+=i;i++;print(x);}
```

Although the compiler accepts both forms, it is strongly recommended to use clear formatting with appropriate whitespace for better code readability and maintainability.

## 10. Not Yet Implemented Features

- Array slicing and negative indices
- User-defined function definitions
- Classes and inheritance
- For loops
- Ternary operator

# Control Flow

**Note:** Only `if`/`else` chains and `while` loops are currently supported. C-style `for` loops, for-in loops, range loops, and the ternary operator are not supported by the compiler.

firescript supports structured control flow constructs.

## Conditional Statements

```firescript
if condition {
    // then-branch
} else if otherCondition {
    // else-if branch
} else {
    // else branch
}
```

## Loops

### While Loops

```firescript
while condition {
    // body
}
```

### C-style For Loops

```firescript
for (int i = 0; i < n; i++) {
    // body
}
```

### For-In Loops

```firescript
for (ElementType elem : array) {
    // body
}
```

### Range Loops

```firescript
for (int i : range(end)) {
    // 0 to end-1
}
```

### Loop Control

- `break` – exit loop
- `continue` – next iteration

## Ternary Operator

```firescript
int max = ternary a > b then a else b
```

## Not yet implemented

- `for` loops (`for`, `for-in`, `range`)
- Ternary operator
- `switch` / `case` statements
- Enhanced range parameters (`start`, `step`, `inclusive`)
- Comprehensions

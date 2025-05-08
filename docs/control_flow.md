# Control Flow

**Note:** Only `if`/`else` chains and `while` loops are currently supported. C-style `for` loops, for-in loops, range loops, and the ternary operator are not supported by the compiler.

## Introduction to Control Flow

Control flow structures determine the order in which statements are executed in a program. They allow for conditional execution (if/else) and repeated execution (loops) of code blocks. In firescript, control flow constructs use curly braces `{}` to define code blocks.

## Conditional Statements

Conditional statements execute different blocks of code depending on whether a specified condition evaluates to `true` or `false`. firescript supports `if`, `else if`, and `else` statements.

### Basic If Statement

The simplest form executes a block of code only if the condition is true:

```firescript
if (condition) {
    // Code executed only if condition is true
}
```

Example:

```firescript
int age = 18;
if (age >= 18) {
    print("You are eligible to vote");
}
```

### If-Else Statement

You can specify an alternative block of code to execute when the condition is false:

```firescript
if (condition) {
    // Code executed if condition is true
} else {
    // Code executed if condition is false
}
```

Example:

```firescript
int score = 65;
if (score >= 70) {
    print("Pass");
} else {
    print("Fail");
}
```

### If-Else If-Else Chains

For multiple conditions, you can use `else if`:

```firescript
if (condition1) {
    // Executed if condition1 is true
} else if (condition2) {
    // Executed if condition1 is false and condition2 is true
} else if (condition3) {
    // Executed if condition1 and condition2 are false and condition3 is true
} else {
    // Executed if all conditions are false
}
```

Example:

```firescript
int grade = 85;

if (grade >= 90) {
    print("A");
} else if (grade >= 80) {
    print("B");
} else if (grade >= 70) {
    print("C");
} else if (grade >= 60) {
    print("D");
} else {
    print("F");
}
```

### Nested Conditional Statements

Conditional statements can be nested within other conditional statements:

```firescript
bool hasDiscount = true;
int totalAmount = 120;

if (totalAmount > 100) {
    if (hasDiscount) {
        print("You qualify for a 15% discount");
    } else {
        print("You qualify for a 10% discount");
    }
} else {
    print("No discount available");
}
```

## Boolean Expressions in Conditions

Conditions can use various boolean operators:

- Comparison operators: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Logical operators: `&&` (AND), `||` (OR), `!` (NOT)

Example:

```firescript
int age = 25;
bool hasLicense = true;

if (age >= 18 && hasLicense) {
    print("You can drive");
}

if (!(age < 18 || !hasLicense)) {
    print("Also, you can drive"); // Equivalent to the above
}
```

## Loops

Loops allow for repeated execution of a block of code. firescript supports `while` loops and plans to support various forms of `for` loops in the future.

### While Loops

A `while` loop repeatedly executes a block of code as long as a specified condition is `true`:

```firescript
while (condition) {
    // Loop body: code executed repeatedly as long as condition is true
}
```

Example:

```firescript
int count = 0;
while (count < 5) {
    print(count);
    count = count + 1;
}
// Outputs: 0, 1, 2, 3, 4
```

#### Infinite Loops

A `while` loop with a condition that is always `true` creates an infinite loop. These should be used with caution and should include a break statement:

```firescript
while (true) {
    // This will run forever unless broken
    if (someCondition) {
        break; // Exit the loop
    }
}
```

#### Loop Control Statements

The following statements can control loop execution:

- `break` - Immediately exits the loop
- `continue` - Skips the rest of the current iteration and starts the next one

Example:

```firescript
int i = 0;
while (i < 10) {
    i = i + 1;
    
    if (i == 3) {
        continue; // Skip the rest of this iteration
    }
    
    if (i == 8) {
        break; // Exit the loop
    }
    
    print(i);
}
// Outputs: 1, 2, 4, 5, 6, 7
```

### Combining Loops and Conditionals

Loops and conditional statements can be combined to create powerful control flows:

```firescript
int[] numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
int sum = 0;
int i = 0;

while (i < numbers.length) {
    if (numbers[i] % 2 == 0) {
        sum = sum + numbers[i]; // Add only even numbers
    }
    i = i + 1;
}

print(sum); // Outputs: 30 (2 + 4 + 6 + 8 + 10)
```

## Future Control Flow Features

The following control flow features are planned but not yet implemented in the current compiler:

### C-style For Loops

```firescript
// Future syntax
for (int i = 0; i < 5; i++) {
    print(i);
}
```

### For-In Loops

```firescript
// Future syntax
string[] fruits = ["apple", "banana", "cherry"];
for (string fruit : fruits) {
    print(fruit);
}
```

### Range Loops

```firescript
// Future syntax
for (int i : range(5)) {
    print(i); // 0, 1, 2, 3, 4
}

for (int i : range(2, 8)) {
    print(i); // 2, 3, 4, 5, 6, 7
}

for (int i : range(1, 10, 2)) {
    print(i); // 1, 3, 5, 7, 9
}
```

### Ternary Operator

```firescript
// Future syntax
int max = ternary a > b then a else b;
```

### Switch Statements

```firescript
// Future syntax
switch (value) {
    case 1:
        // code for case 1
        break;
    case 2:
        // code for case 2
        break;
    default:
        // default code
}
```

## Best Practices

1. **Keep conditions simple**: Split complex conditions into multiple variables for better readability.

2. **Avoid deep nesting**: Too many nested if/else statements make code hard to follow. Consider refactoring deeply nested code.

3. **Be careful with while loops**: Always ensure that the condition will eventually become false to avoid infinite loops.

4. **Use appropriate loop types**: Once implemented, choose the right loop for the task: `while` for unknown iteration counts, `for` for counting, and `for-in` for collections.

## Implementation Status

The current firescript compiler supports:

- ✅ `if`/`else`/`else if` conditional statements
- ✅ `while` loops
- ✅ `break` and `continue` statements

Not yet implemented:

- ❌ C-style `for` loops
- ❌ `for-in` loops
- ❌ Range-based loops
- ❌ Ternary operator
- ❌ `switch`/`case` statements

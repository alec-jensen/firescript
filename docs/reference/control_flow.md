# Control Flow

firescript supports several control flow structures: conditional statements (`if`/`else`), while loops, C-style for loops, and for-in loops (over arrays, strings, and generators). Range-style loops are provided by the `@firescript/std.ranges` module. The ternary operator is not yet supported by the compiler.

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
import @firescript/std.io.print;

age: int8 = 18;
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
import @firescript/std.io.print;

score: int8 = 65;
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
import @firescript/std.io.print;

grade: int8 = 85;

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
import @firescript/std.io.print;

hasDiscount: bool = true;
totalAmount: int8 = 120;

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

Operator precedence for boolean expressions follows standard rules:

- `!` (highest)
- `&&`
- `||` (lowest)

Example:

```firescript
import @firescript/std.io.print;

age: int8 = 25;
hasLicense: bool = true;

if (age >= 18 && hasLicense) {
    print("You can drive");
}

if (!(age < 18 || !hasLicense)) {
    print("Also, you can drive"); // Equivalent to the above
}
```

## Loops

Loops allow for repeated execution of a block of code. firescript supports `while` loops, C-style `for` loops, and `for-in` loops.

### While Loops

A `while` loop repeatedly executes a block of code as long as a specified condition is `true`:

```firescript
while (condition) {
    // Loop body: code executed repeatedly as long as condition is true
}
```

Example:

```firescript
import @firescript/std.io.print;

count: uint8 = 0;
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
import @firescript/std.io.print;

i: uint8 = 0;
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
import @firescript/std.io.print;

numbers: int8[10] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
sum: int8 = 0;
i: uint8 = 0;

while (i < numbers.length()) {
    if (numbers[i] % 2 == 0) {
        sum = sum + numbers[i]; // Add only even numbers
    }
    i = i + 1;
}

print(sum); // Outputs: 30 (2 + 4 + 6 + 8 + 10)
```

## For Loops

firescript supports two types of for loops: C-style for loops and for-in loops.

### C-style For Loops

C-style for loops consist of three parts: initialization, condition, and increment. They are ideal for counting iterations.

```firescript
import @firescript/std.io.println;

for (i: int32 = 0; i < 5; i++) {
    println(i);
}
```

Any or all parts can be omitted:

```firescript
import @firescript/std.io.println;

i: int32 = 0;
for (; i < 5; i++) {  // Init omitted
    println(i);
}

for (j: int32 = 0; j < 10;) {  // Increment omitted
    println(j);
    j++;
}
```

Variables declared in the initialization section are scoped to the for loop:

```firescript
import @firescript/std.io.println;

for (i: int32 = 0; i < 3; i++) {
    println(i);
}
// i is not accessible here

// This is valid - i is redeclared in a new scope
for (i: int32 = 0; i < 5; i++) {
    println(i);
}
```

Nested for loops:

```firescript
import @firescript/std.io.println;

for (i: int32 = 0; i < 3; i++) {
    for (j: int32 = 0; j < 3; j++) {
        println(i * 3 + j);
    }
}
```

### For-In Loops

For-in loops iterate over elements in a collection (arrays, strings, or generators). The loop variable must be declared with a type:

```firescript
import @firescript/std.io.println;

numbers: int32[5] = [1, 2, 3, 4, 5];
for (num: int32 in numbers) {
    println(num);
}
```

For-in with array literals:

```firescript
import @firescript/std.io.println;

for (value: int32 in [10, 20, 30, 40, 50]) {
    println(value);
}
```

String iteration with for-in:

```firescript
import @firescript/std.io.println;

text: string = "hello";
for (ch: string in text) {
    println(ch);  // Prints each character: h, e, l, l, o
}
```

### Range Loops

Range-style counting loops are provided by the `@firescript/std.ranges` module, which exports the `range`, `rangeFrom`, and `rangeStep` generators:

```firescript
import @firescript/std.io.println;
import @firescript/std.ranges.range;
import @firescript/std.ranges.rangeFrom;
import @firescript/std.ranges.rangeStep;

for (i: int32 in range(5)) {
    println(i);  // 0, 1, 2, 3, 4
}

for (i: int32 in rangeFrom(2, 6)) {
    println(i);  // 2, 3, 4, 5
}

for (i: int32 in rangeStep(0, 10, 3)) {
    println(i);  // 0, 3, 6, 9
}
```

### Iterating Over Generators

`for-in` also works over any generator function, including user-defined ones (see [Functions & Methods](functions.md) for generator definitions):

```firescript
import @firescript/std.io.println;

fn countdown(n: int32) -> generator<int32> {
    i: int32 = n;
    while (i > 0) {
        yield i;
        i -= 1;
    }
}

for (v: int32 in countdown(3)) {
    println(v);  // 3, 2, 1
}
```

### Break and Continue in For Loops

Both `break` and `continue` work in for loops:

```firescript
import @firescript/std.io.println;

// Break: exit the loop early
for (i: int32 = 0; i < 10; i++) {
    if (i == 5) {
        break;  // Exit when i reaches 5
    }
    println(i);  // Prints 0, 1, 2, 3, 4
}

// Continue: skip to next iteration
for (i: int32 = 0; i < 5; i++) {
    if (i == 2) {
        continue;  // Skip when i is 2
    }
    println(i);  // Prints 0, 1, 3, 4
}
```

## Future Control Flow Features

The following control flow features are planned but not yet implemented in the current compiler:

### Ternary Operator

```firescript
// Future syntax
max: int8 = ternary a > b then a else b;
```

### Switch Statements

Switch statements provide a way to execute different parts of code based on the value of a variable:

```firescript
// Future syntax
switch (value) {
    case (1) {
        // code for case 1
    }
    case (2) {
        // code for case 2
    }
    case (value > 2 && value < 5) {
        // code for range case
    }
    default {
        // default code
        // executed if no cases match
    }
}
```

## Best Practices

1. **Keep conditions simple**: Split complex conditions into multiple variables for better readability.

2. **Avoid deep nesting**: Too many nested if/else statements make code hard to follow. Consider refactoring deeply nested code.

3. **Be careful with while loops**: Always ensure that the condition will eventually become false to avoid infinite loops.

4. **Use appropriate loop types**: Choose the right loop for the task: `while` for unknown iteration counts, `for` for counting, and `for-in` for collections.

## Implementation Status

The current firescript compiler supports:

- [IMPLEMENTED] `if`/`else`/`else if` conditional statements
- [IMPLEMENTED] `while` loops
- [IMPLEMENTED] C-style `for` loops
- [IMPLEMENTED] `for-in` loops (arrays, strings, and generators)
- [IMPLEMENTED] Range loops via `@firescript/std.ranges`
- [IMPLEMENTED] `break` and `continue` statements

Not yet implemented:

- [PLANNED] Ternary operator
- [PLANNED] `switch`/`case` statements

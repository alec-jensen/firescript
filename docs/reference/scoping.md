# Scoping in firescript

> Status: Scoping rules are [IMPLEMENTED]. See [Memory Management](./memory_management.md#overview) for authoritative ownership definitions.

In firescript, scopes define the visibility and lifetime of variables. Understanding how scopes work is crucial for writing correct and predictable code.

## Scope Creation

A new scope is created by **any** set of curly braces `{}`. This includes:

* **Control Flow Statements:** The bodies of `if`, `else if`, `else`, `for`, `while`, and other control flow statements each create their own scope.
* **Function Bodies:** The body of a function defines a scope.
* **Class Bodies:** The body of a class defines a scope.
* **Bare Braces:** You can create an explicit scope simply by using a pair of curly braces `{}` anywhere they are syntactically allowed.

```firescript
import @firescript/std.io.print;

// Global scope

globalVar: int32 = 10;

if (globalVar > 5) {
    // Inner scope 1 (if body)
    innerVar1: int32 = 20;
    print(globalVar);  // Accessing outer scope variable: OK (prints 10)
    print(innerVar1);  // Accessing current scope variable: OK (prints 20)
}

// print(innerVar1)  // ERROR: innerVar1 is not accessible here

{
    // Inner scope 2 (bare braces)
    innerVar2: int32 = 30;
    print(globalVar);  // Accessing outer scope variable: OK (prints 10)
    print(innerVar2);  // Accessing current scope variable: OK (prints 30)

    if (true) {
        // Inner scope 3 (nested if body)
        innerVar3: int32 = 40;
        print(globalVar);  // OK (prints 10)
        print(innerVar2);  // OK (prints 30)
        print(innerVar3);  // OK (prints 40)
    }
    // print(innerVar3)  // ERROR: innerVar3 is not accessible here
}

// print(innerVar2)  // ERROR: innerVar2 is not accessible here
```

## Scope Hierarchy and Variable Access

* **Outer Scope Access:** An inner scope can access variables declared in any of its enclosing (outer) scopes, all the way up to the global scope.
* **Inner Scope Isolation:** An outer scope *cannot* access variables declared within any of its inner scopes. Once a scope block is exited, all variables declared directly within that scope are destroyed and become inaccessible.
* **Variable Shadowing:** Variable shadowing is not allowed, since variables exist in their scope and all nested scopes. This means you cannot declare a variable with the same name as an existing variable in an outer scope.

## Detailed Scoping Rules

### 1. Variable Declaration and Initialization

Variables in firescript must be declared with an explicit type and initialized in the same statement. They are only accessible within their scope:

```firescript
import @firescript/std.io.print;

{
    x: int32 = 5;  // x is declared and initialized
    
    {
        // New inner scope
        print(x);  // Accessible, prints 5
        
        // int32 x = 10;  // ERROR: Cannot redeclare 'x' - shadowing is not allowed
        y: int32 = 15;  // y is only accessible in this scope
    }
    
    // print(y)  // ERROR: y is not defined in this scope
}
// print(x)  // ERROR: x is not defined in this scope
```

### 2. Variable Lifetime

Variables exist only from the point32 of their declaration to the end of their containing scope:

```firescript
{
    // print(a)  // ERROR: Cannot use 'a' before declaration
    
    a: int32 = 1;
    print(a);  // OK: 'a' exists here
    
    {
        b: int32 = 2;
        print(a);  // OK: 'a' from outer scope
        print(b);  // OK: 'b' from current scope
    }  // 'b' is destroyed here
    
    // print(b)  // ERROR: 'b' no longer exists
}  // 'a' is destroyed here
```

### 3. Global Scope

Variables declared outside any braces are in the global scope and are accessible throughout the entire program:

```firescript
globalValue: int32 = 100;  // Global variable

{
    print(globalValue);  // Accessible anywhere in the program
    
    {
        print(globalValue);  // Still accessible
    }
}

// User-defined functions also have access to global variables
```

### 4. Loop Scopes

Each iteration of a loop has its own scope:

```firescript
i: int32 = 0;
while (i < 3) {
    // New scope for each loop iteration
    temp: int32 = i * 10;
    print(temp);  // Prints 0, 10, 20
    i = i + 1;
}  // 'temp' is destroyed at the end of each iteration

// print(temp)  // ERROR: 'temp' is not accessible here
```

### 5. Conditional Scopes

Each branch of a conditional statement creates its own scope. This pattern prevents runtime issues where a variable may or may not be defined depending on the execution path:

```firescript
value: int32 = 5;

if (value > 10) {
    // Scope A
    result: int32 = value * 2;
    print(result);
} else if (value > 0) {
    // Scope B (different from Scope A)
    result: int32 = value + 10;  // OK to reuse the name 'result' here
    print(result);  // Prints 15
} else {
    // Scope C (different from Scopes A and B)
    result: int32 = 0;
    print(result);
}

// print(result)  // ERROR: 'result' is not accessible here
```

### 6. Nested Function Scopes

Functions create their own scopes:

```firescript
// Global scope
globalVar: int32 = 10;

fn exampleFunction() -> void {
    // Function scope
    functionVar: int32 = 20;
    print(globalVar);  // OK: access to global scope
    
    {
        // Inner scope within the function
        innerVar: int32 = 30;
        print(functionVar);  // OK: access to containing function scope
        print(globalVar);    // OK: access to global scope
    }
    
    // print(innerVar)  // ERROR: not accessible outside its scope
}

// print(functionVar)  // ERROR: function variables only exist in function scope
```

## Variable Scope vs. Object Lifetime

It's important to distinguish between a variable's scope (where it can be accessed) and an object's lifetime (how long it exists in memory and when it is dropped):

```firescript
{
    // myObj variable is scoped to this block
    myObj: Person = Person("John", 30);

    // myObj goes out of scope here
    // The Person object is dropped when its final owner goes out of scope
    // (deterministic behavior – see Memory Management).
}
```

## Best Practices for Effective Scoping

1. **Keep scopes as small as possible**: Declare variables in the smallest scope where they are needed.

2. **Declare variables close to their first use**: This improves code readability and maintainability.

3. **Use explicit scopes for temporary variables**: Use bare braces `{}` to create explicit scopes for temporary variables.

   ```firescript
   {
       // Temporary calculation scope
       temp: int32 = complexCalculation();
       result = temp * 2;
   }  // 'temp' is no longer accessible, reducing scope pollution
   ```

4. **Be consistent with variable naming**: Use clear, descriptive names to avoid confusion, especially with variables in different scopes.

5. **Avoid deeply nested scopes**: Excessive nesting can make code harder to read and understand.

## Interaction With Ownership

- Scope exit triggers deterministic drop of all still-owned values declared in that scope.
- A move transfers ownership; the original variable becomes invalid immediately after the move.
- A borrow (`&T`) never extends lifetime; it relies on the original owner remaining in scope.
- Last-use analysis may drop a value before the lexical end of the scope if no further uses are provable.

## Implementation Details

firescript's scoping mechanism is implemented as a stack of symbol tables. When looking up a variable:

1. The compiler first checks the innermost scope (top of the stack)
2. If not found, it progressively checks outer scopes
3. If the variable is not found in any scope, a compilation error occurs

## Common Scoping Errors

### 1. Accessing Variables Outside Their Scope

```firescript
{
    value: int8 = 10;
}
print(value)  // ERROR: 'value' is not defined in this scope
```

### 2. Redeclaring Variables in the Same Scope

```firescript
count: int8 = 5;
count: int8 = 10;  // ERROR: 'count' is already defined
```

### 3. Attempting Variable Shadowing

```firescript
value: int8 = 10;
if (true) {
    value: int8 = 20;  // ERROR: Shadowing is not allowed in firescript
}
```

### 4. Using Variables Before Declaration

```firescript
print(result);  // ERROR: Cannot use 'result' before declaration
result: int8 = 42;
```

## Implementation Status

Scope handling in firescript is fully implemented:

* [IMPLEMENTED] Block scopes with curly braces
* [IMPLEMENTED] Variable visibility rules
* [IMPLEMENTED] Prohibition of variable shadowing
* [IMPLEMENTED] Scope nesting and hierarchy
* [IMPLEMENTED] Variable lifetime management

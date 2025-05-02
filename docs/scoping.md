# Scoping in firescript

In firescript, scopes define the visibility and lifetime of variables. Understanding how scopes work is crucial for writing correct and predictable code.

## Scope Creation

A new scope is created by **any** set of curly braces `{}`. This includes:

* **Control Flow Statements:** The bodies of `if`, `else if`, `else`, `for`, `while`, and other control flow statements each create their own scope.
* **Function Bodies:** The body of a function defines a scope.
* **Class Bodies:** The body of a class defines a scope.
* **Bare Braces:** You can create an explicit scope simply by using a pair of curly braces `{}` anywhere they are syntactically allowed.

```firescript
// Global scope

int globalVar = 10;

if (globalVar > 5) {
    // Inner scope 1 (if body)
    int innerVar1 = 20;
    print(globalVar); // Accessing outer scope variable: OK (prints 10)
    print(innerVar1); // Accessing current scope variable: OK (prints 20)
}

// print(innerVar1); // ERROR: innerVar1 is not accessible here

{
    // Inner scope 2 (bare braces)
    int innerVar2 = 30;
    print(globalVar); // Accessing outer scope variable: OK (prints 10)
    print(innerVar2); // Accessing current scope variable: OK (prints 30)

    if (true) {
        // Inner scope 3 (nested if body)
        int innerVar3 = 40;
        print(globalVar); // OK (prints 10)
        print(innerVar2); // OK (prints 30)
        print(innerVar3); // OK (prints 40)
    }
    // print(innerVar3); // ERROR: innerVar3 is not accessible here
}

// print(innerVar2); // ERROR: innerVar2 is not accessible here
```

## Scope Hierarchy and Variable Access

* **Outer Scope Access:** An inner scope can access variables declared in any of its enclosing (outer) scopes, all the way up to the global scope.
* **Inner Scope Isolation:** An outer scope *cannot* access variables declared within any of its inner scopes. Once a scope block is exited, all variables declared directly within that scope are destroyed and become inaccessible.
* **Variable Shadowing:** Variable shadowing is not allowed. firescript will throw an error if you try to declare a variable with the same name in an inner scope that already exists in an outer scope. This is to prevent confusion and ensure that the intended variable is always accessed.

This strict scoping rule helps prevent errors related to variables potentially being uninitialized or accessed outside their intended lifetime. It ensures that if a variable name exists within a scope, it is guaranteed to have been properly declared either in the current scope or an outer one.

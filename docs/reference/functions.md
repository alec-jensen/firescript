# Functions & Methods

## Built-in Functions

For the purposes of most code, firescript does not provide any built-in functions. Things like io and math are provided by the standard library.

## User-defined Functions

```firescript
// Basic function definition
returnType functionName(paramType1 param1, paramType2 param2) {
    // function body
    return returnValue;
}

// Examples:
int32 add(int32 a, int32 b) {
    return a + b;
}

void greet(string name) {
    print("Hello, " + name);
}

float32 calculateAverage(&int32[] numbers) {
    int32 sum = 0;
    int32 i = 0;
    while (i < numbers.length()) {
        sum = sum + numbers[i];
        i = i + 1;
    }
    return (sum as float32) / (numbers.length() as float32);
}
```

Functions support parameters, return values, and recursion.

### Ownership Notes

- Parameters of Owned types (strings, arrays, user-defined objects) move into the function. After a call, an argument of an owned type is no longer valid unless the function returns it.
- Borrow syntax (`&T`) passes a read-only view without moving ownership. Borrowed arguments remain valid after the call.
- For Copyable types (e.g., `intN`, `floatN`, `bool`, `char`), calls pass by value; borrowing is not defined for Copyable types.
- String concatenation produces new `string` values. Strings are Owned and use move semantics.
- Arrays are Owned and use move semantics.

See [Memory Management](memory_management.md) for the full rules.

## Generic Functions

Functions can declare type parameters in angle brackets after the function name. The compiler monomorphizes each unique instantiation at compile time. Type parameters can be constrained with type unions or named constraint aliases (see [Type System — Generics](type_system.md#generics)):

```firescript
T max<T: int32 | int64>(T a, T b) {
    if (a > b) {
        return a;
    }
    return b;
}

int32 larger = max(10, 20);  // T inferred as int32
```

## Generator Functions

A generator function produces a lazy sequence of values with `yield`. Generators are declared with the `generator<T>` return type and are consumed with `for-in` loops:

```firescript
import @firescript/std.io.println;

generator<int32> countdown(int32 n) {
    int32 i = n;
    while (i > 0) {
        yield i;
        i -= 1;
    }
}

for (int32 v in countdown(3)) {
    println(v);  // 3, 2, 1
}
```

The standard library's `@firescript/std.ranges` module provides ready-made `range`, `rangeFrom`, and `rangeStep` generators.

## Methods

Methods are functions that belong to class instances. Methods declare a receiver: `&this` for read-only access, `&mut this` for mutable access. Static methods belong to the class itself and take no receiver:

```firescript
class Person {
    string name;
    int32 age;

    // Constructor
    Person(&mut this, string name, int32 age) {
        this.name = name;
        this.age = age;
    }

    // Instance method (read-only receiver)
    string introduce(&this) {
        return "My name is " + this.name + " and I'm " + (this.age as string) + " years old";
    }

    // Static method
    static string getSpecies() {
        return "Human";
    }
}
```

See [Classes & Inheritance](classes.md) for full details on methods, constructors, and receivers.

## Best Practices for Functions

1. **Single responsibility**: Each function should perform a single, well-defined task.

2. **Descriptive names**: Use verb-based names that clearly describe what the function does.

3. **Input validation**: Check function arguments for validity when appropriate.

4. **Error handling**: Consider how your function will handle error conditions.

5. **Pure functions**: When possible, write pure functions (functions without side-effects that return the same output for the same input).

## Future Function Features

The following function-related features are planned but not yet implemented:

- Optional parameters with default values:

```firescript
// Future syntax
void greet(string name, string greeting = "Hello") {
    print(greeting + ", " + name);
}
```

- Named arguments in calls:

```firescript
// Future syntax
calculateRectangle(width: 10, height: 20);
```

- Variadic parameters (variable number of arguments):

```firescript
// Future syntax
int32 sum(int32... numbers) {
    int32 total = 0;
    for (int32 num in numbers) {
        total = total + num;
    }
    return total;
}
```

- Function overloading:

```firescript
// Future syntax
int32 add(int32 a, int32 b) {
    return a + b;
}

float32 add(float32 a, float32 b) {
    return a + b;
}
```

## Implementation Status

- [IMPLEMENTED] User-defined function definitions (parameters, return values, recursion)
- [IMPLEMENTED] Generic functions with constraints
- [IMPLEMENTED] Generator functions (`generator<T>`, `yield`)
- [IMPLEMENTED] Methods on classes (including static methods)
- [PLANNED] Optional, named, or variadic parameters
- [PLANNED] Function overloading

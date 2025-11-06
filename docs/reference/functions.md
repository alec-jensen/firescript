# Functions & Methods

> Status: This section includes planned semantics for the ownership-based memory model. See [Memory Management](./memory_management.md) for authoritative definitions.

## Built-in Functions

firescript provides a set of built-in functions that are available for use without requiring any imports. These functions provide essential functionality for input/output, type conversion, and type introspection.

### Input/Output Functions

- **`print(value)`** – Outputs a value to the console

```firescript
print("Hello, world!");  // Prints: Hello, world!
print(42);               // Prints: 42
print(true);             // Prints: true
```

  This function accepts values of any type and converts them to strings for display.

- **`input(prompt)`** – Reads a string from the console

```firescript
string name = input("Enter your name: ");
print("Hello, " + name);
```

  The `prompt` parameter is displayed to the user before waiting for input.

### Type Introspection

- **`typeof(value)`** – Returns the type name of a value as a string

```firescript
string typeOfNumber = typeof(42);         // "int"
string typeOfText = typeof("hello");      // "string"
string typeOfArray = typeof([1, 2, 3]);   // "int[]"
```

  This can be useful for debugging and for implementing type-dependent behavior.

### Testing

- **`assert(condition, message)`** – Asserts that a condition is true, otherwise raises an error with the given message

```firescript
int x = 5;
assert(x > 0, "x must be positive");  // Passes
assert(x < 0, "x must be negative");  // Fails with error: "Assertion failed: x must be negative"
```

## Using Built-in Functions

Functions are called by specifying the function name followed by parentheses containing the arguments:

```firescript
// Converting user input to a number
string inputValue = input("Enter a number: ");
int parsedValue = toInt(inputValue);
print("You entered: " + toString(parsedValue));

// Type checking
int number = 42;
string typeInfo = typeof(number);
print("The type of " + toString(number) + " is " + typeInfo);
```

### Chain of Function Calls

Built-in functions can be chained together:

```firescript
// Get input, convert to int, double it, and print
int result = toInt(input("Enter a number: ")) * 2;
print("Double of your number is: " + toString(result));
```

## User-defined Functions

```firescript
// Basic function definition
returnType functionName(paramType1 param1, paramType2 param2) {
    // function body
    return returnValue;
}

// Examples:
int add(int a, int b) {
    return a + b;
}

void greet(string name) {
    print("Hello, " + name);
}

float calculateAverage(int[] numbers) {
    int sum = 0;
    int i = 0;
    while (i < numbers.length) {
        sum = sum + numbers[i];
        i = i + 1;
    }
    return toFloat(sum) / toFloat(numbers.length);
}
```

### Ownership Notes (Planned Semantics)

- Parameters of owned types move into the function. After a call, an argument of an owned type is no longer valid unless the function returns it.
- Future explicit borrow syntax (`&T`) will allow passing a read-only view without moving ownership. Borrowed arguments remain valid after the call.
 - For Copyable types (e.g., `intN`, `floatN`, `bool`, `char`, `string`), calls pass by value; borrowing is not defined for Copyable types.
 - `input()` returns a new `string` (Copyable).
 - `toString()` and string concatenation produce new `string` values. Strings are Copyable and passed by value.
 - Cloning is explicit for Owned values (not needed for Copyable types like `string`).
- Examples currently show simple pass semantics until borrow syntax is implemented.

## Methods (Planned, Not Implemented)

Methods are functions that belong to objects. This feature is planned but **not yet implemented**:

```firescript
class Person {
    string name
    int age
    
    // Constructor method
    Person(&this, string name, int age) {
        this.name = name;
        this.age = age;
    }
    
    // Instance method
    string introduce(&this) {
        return "My name is " + this.name + " and I'm " + toString(this.age) + " years old";
    }
    
    // Static method
    static string getSpecies() {
        return "Human";
    }
}
```

## Best Practices for Functions

Although user-defined functions aren't implemented yet, here are best practices to follow when they become available:

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
int sum(int... numbers) {
    int total = 0;
    for (int num : numbers) {
        total = total + num;
    }
    return total;
}
```

- Function overloading:

```firescript
// Future syntax
int add(int a, int b) {
    return a + b;
}

float add(float a, float b) {
    return a + b;
}
```

## Implementation Status

- ✅ Built-in functions: `print`, `input`, type conversions, `typeof`
- ✅ Array methods: `append`, `insert`, `pop`, `clear`, `length`
- ✅ User-defined function definitions
- ❌ Methods on objects
- ❌ Optional, named, or variadic parameters
- ❌ Function overloading

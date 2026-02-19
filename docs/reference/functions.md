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

- Parameters of owned types (strings, arrays, user-defined objects) move into the function. After a call, an argument of an owned type is no longer valid unless the function returns it.
- Future explicit borrow syntax (`&T`) will allow passing a read-only view without moving ownership. Borrowed arguments remain valid after the call.
 - For Copyable types (e.g., `intN`, `floatN`, `bool`, `char`), calls pass by value; borrowing is not defined for Copyable types.
 - `toString()` and string concatenation produce new `string` values. Strings are Owned and use move semantics.
 - Arrays are Owned and use move semantics.
 - Cloning is explicit for Owned values (needed for `string`, arrays, and user-defined objects).
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
- ✅ Methods on objects
- ❌ Optional, named, or variadic parameters
- ❌ Function overloading

# Functions & Methods

**Note:** User-defined function definitions, methods on objects, optional or named parameters, variadic parameters, and function overloading are currently not supported by the compiler. Only built-in functions are available in the current implementation.

## Built-in Functions

firescript provides a set of built-in functions that are available for use without requiring any imports. These functions provide essential functionality for input/output, type conversion, and type introspection.

### Input/Output Functions

- **`print(value)`** – Outputs a value to the console

  ```firescript
  print("Hello, world!")  // Prints: Hello, world!
  print(42)               // Prints: 42
  print(true)             // Prints: true
  ```

  This function accepts values of any type and converts them to strings for display.

- **`input(prompt)`** – Reads a string from the console

  ```firescript
  string name = input("Enter your name: ")
  print("Hello, " + name)
  ```

  The `prompt` parameter is displayed to the user before waiting for input.

### Type Conversion Functions

These functions convert values from one type to another:

- **`toInt(value)`** – Converts a value to an integer

  ```firescript
  string numberString = "123"
  int number = toInt(numberString)  // 123
  
  float floatVal = 45.7
  int intVal = toInt(floatVal)      // 45 (truncated)
  ```

- **`toFloat(value)`** – Converts a value to a float (32-bit floating point)

  ```firescript
  int count = 5
  float floatCount = toFloat(count)  // 5.0
  
  string pi = "3.14159"
  float piValue = toFloat(pi)        // 3.14159
  ```

- **`toDouble(value)`** – Converts a value to a double (64-bit floating point)

  ```firescript
  int bigNumber = 1000000
  double doubleBig = toDouble(bigNumber)  // 1000000.0 (with double precision)
  
  string sciNotation = "6.022e23"
  double avogadro = toDouble(sciNotation)  // 6.022e23
  ```

- **`toBool(value)`** – Converts a value to a boolean

  ```firescript
  string truthy = "true"
  bool flag = toBool(truthy)  // true
  
  string falsy = "false"
  bool notFlag = toBool(falsy)  // false
  
  // Non-string inputs:
  bool nonZero = toBool(1)      // true
  bool zero = toBool(0)         // false
  ```

- **`toString(value)`** – Converts a value to a string

  ```firescript
  int number = 42
  string text = toString(number)  // "42"
  
  bool state = true
  string stateText = toString(state)  // "true"
  
  float decimal = 3.14
  string piText = toString(decimal)  // "3.14"
  ```

- **`toChar(value)`** – Converts a value to a character (represented as a string)

  ```firescript
  string word = "Hello"
  char firstLetter = toChar(word)  // "H" (first character)
  
  int codePoint = 65
  char letter = toChar(codePoint)  // "A" (ASCII value 65)
  ```

### Type Introspection

- **`typeof(value)`** – Returns the type name of a value as a string

  ```firescript
  string typeOfNumber = typeof(42)         // "int"
  string typeOfText = typeof("hello")      // "string"
  string typeOfArray = typeof([1, 2, 3])   // "int[]"
  ```

  This can be useful for debugging and for implementing type-dependent behavior.

## Using Built-in Functions

Functions are called by specifying the function name followed by parentheses containing the arguments:

```firescript
// Converting user input to a number
string inputValue = input("Enter a number: ")
int parsedValue = toInt(inputValue)
print("You entered: " + toString(parsedValue))

// Type checking
int number = 42
string typeInfo = typeof(number)
print("The type of " + toString(number) + " is " + typeInfo)
```

### Chain of Function Calls

Built-in functions can be chained together:

```firescript
// Get input, convert to int, double it, and print
int result = toInt(input("Enter a number: ")) * 2
print("Double of your number is: " + toString(result))
```

## User-defined Functions (Planned, Not Implemented)

The following syntax is planned for user-defined functions but is **not yet implemented** in the current compiler:

```firescript
// Basic function definition
returnType functionName(paramType1 param1, paramType2 param2) {
    // function body
    return returnValue;
}

// Examples:
int add(int a, int b) {
    return a + b
}

void greet(string name) {
    print("Hello, " + name)
}

float calculateAverage(int[] numbers) {
    int sum = 0
    int i = 0
    while (i < numbers.length) {
        sum = sum + numbers[i]
        i = i + 1
    }
    return toFloat(sum) / toFloat(numbers.length)
}
```

## Methods (Planned, Not Implemented)

Methods are functions that belong to objects. This feature is planned but **not yet implemented**:

```firescript
class Person {
    string name
    int age
    
    // Constructor method
    Person(this, string name, int age) {
        this.name = name
        this.age = age
    }
    
    // Instance method
    string introduce(this) {
        return "My name is " + this.name + " and I'm " + toString(this.age) + " years old"
    }
    
    // Static method
    static string getSpecies() {
        return "Human"
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
      print(greeting + ", " + name)
  }
  ```

- Named arguments:

  ```firescript
  // Future syntax
  calculateRectangle(width: 10, height: 20)
  ```

- Variadic parameters (variable number of arguments):

  ```firescript
  // Future syntax
  int sum(int... numbers) {
      int total = 0
      for (int num : numbers) {
          total = total + num
      }
      return total
  }
  ```

- Function overloading:

  ```firescript
  // Future syntax
  int add(int a, int b) {
      return a + b
  }
  
  float add(float a, float b) {
      return a + b
  }
  ```

- First-class functions and closures:

  ```firescript
  // Future syntax
  function<int, int, int> operation = add
  int result = operation(5, 3)
  ```

## Implementation Status

- ✅ Built-in functions: `print`, `input`, type conversions, `typeof`
- ✅ Array methods: `append`, `insert`, `pop`, `clear`, `length`
- ❌ User-defined function definitions
- ❌ Methods on objects
- ❌ Optional, named, or variadic parameters
- ❌ Function overloading
- ❌ First-class functions and closures

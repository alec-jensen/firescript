# Functions & Methods

**Note:** User-defined function definitions, methods on objects, optional or named parameters, variadic parameters, and function overloading are currently not supported by the compiler.

FireScript supports both built-in and user-defined functions, as well as methods on objects and arrays.

## Built-in Functions

- `print(value)` – output a value
- `input(prompt)` – read string from console
- `toInt(x)`, `toFloat(x)`, `toDouble(x)`, `toBool(x)`, `toString(x)`, `toChar(x)` – conversions
- `typeof(x)` – returns type name

## User-defined Functions

```firescript
int add(int a, int b) {
    return a + b
}

float average(int a, int b) {
    // optional parameters not yet implemented
    return toFloat(a + b) / 2.0
}
```

- Define with return type, name, parameters, and body.
- `void` functions: use `void` as return type.

## Methods

- Instance methods take `this` as first parameter
- Static methods: use `static` keyword

```firescript
class Person {
    string name;
    Person(this, string name) {
        this.name = name
    }
    static string greet() {
        return "Hello"
    }
}
```

## Array Methods

See [Arrays](arrays.md).

## Not yet implemented

- Default or named arguments in functions
- Variadic parameters
- First-class function types and closures

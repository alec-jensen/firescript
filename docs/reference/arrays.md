# Arrays

> Only arrays with literal initialization and methods `length` are supported by the compiler. Array slicing, negative indices, and other utility methods are not implemented.

## Array Basics

In firescript, arrays are fixed-size, ordered collections of elements that all share the same type. Arrays are declared using square brackets and the size after the type.

## Declaration and Initialization

Arrays are declared by appending `[N]` to any valid type and initializing with values in square brackets:

```firescript
// Array initialization with values
int[5] numbers = [10, 20, 30, 40, 50];
string[3] names = ["Alice", "Bob", "Charlie"];
bool[3] flags = [true, false, true];
```

All elements in an array must be of the same type as specified in the declaration.

## Accessing Array Elements

Individual array elements can be accessed using zero-based indexing:

```firescript
int[5] scores = [85, 92, 78, 90, 88];

// Access individual elements
int firstScore = scores[0];    // 85
int thirdScore = scores[2];    // 78

// Modifying elements
scores[1] = 95;                // Array becomes [85, 95, 78, 90, 88]
```

⚠️ **Warning:** Accessing an index outside the array bounds will cause a runtime error. Always ensure your index is valid before access.

## Array Operations

firescript provides several built-in methods for manipulating arrays:

- **`length`** – Property that returns the current size of the array

```firescript
int[5] data = [5, 10, 15, 20, 25];
int size = data.length;      // size = 5
```

## Working with Arrays

### Iterating Over Arrays

Use a `while` loop with an index variable to iterate over array elements:

```firescript
string[5] cities = ["New York", "London", "Tokyo", "Paris", "Sydney"];
int i = 0;
while (i < cities.length) {
    print(cities[i]);
    i = i + 1;
}
```

### Array as Function Arguments

Arrays can be passed to functions:

```firescript
// Example of how it would work when user-defined functions are implemented
int sum(int[] numbers) {
    int total = 0;
    int i = 0;
    while (i < numbers.length) {
        total = total + numbers[i];
        i = i + 1;
    }
    return total;
}

// Usage
int[5] values = [1, 2, 3, 4, 5];
int result = sum(values);  // 15
```

### Nested Arrays

Arrays can contain other arrays (though this is not fully implemented yet):

```firescript
// 2D array example
int[3][3] matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
];

// Accessing elements
int element = matrix[1][2];  // 6
```

## Common Array Patterns

### Finding an Element

```firescript
int[5] numbers = [10, 20, 30, 40, 50];
int target = 30;
int index = -1;
int i = 0;

while (i < numbers.length) {
    if (numbers[i] == target) {
        index = i;
        break;
    }
    i = i + 1;
}

// index = 2 if found, -1 if not found
```

## Features Not Yet Implemented

The following array features are planned but not yet implemented in the current compiler:

- **Array slicing** (`arr[start:end:step]`) – Extract a portion of the array

```firescript
// Future syntax
int[] numbers = [10, 20, 30, 40, 50];
int[] subset = numbers[1:4];  // Would be [20, 30, 40]
```

- **Negative indices** – Access elements from the end of the array

```firescript
// Future syntax
string[] words = ["apple", "banana", "cherry"];
string last = words[-1];     // Would be "cherry"
```

- **Additional utility methods**:
  - `index(value)` – Find the index of the first occurrence of a value
  - `count(value)` – Count occurrences of a value
  - `sort()` – Sort the array elements

## Implementation Status

Arrays are functional but with limited operations in the current compiler:

- ✅ Array declaration and initialization
- ✅ Element access with positive indices
- ✅ Length property
- ❌ Array slicing
- ❌ Negative indices
- ❌ Advanced utility methods
- ❌ Multi-dimensional array operations

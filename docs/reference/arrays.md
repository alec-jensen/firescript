# Arrays

> Core arrays are fixed-size. The compiler supports `length()`, negative indexing, `index(value)`, and `count(value)`. Array slicing and core `sort()` are not implemented; sorting should come from standard library containers/utilities.

## Array Basics

In firescript, arrays are fixed-size, ordered collections of elements that all share the same type. Arrays are Owned types—they are stored on the heap with pointers on the stack and use move semantics. Arrays are declared using square brackets and the size after the type.

## Declaration and Initialization

Arrays are declared by appending `[N]` to any valid type, where `N` is the fixed size. Arrays can be initialized with values in square brackets, or left uninitialized to be zero-initialized:

```firescript
// Array initialization with explicit values
int8[5] numbers = [10, 20, 30, 40, 50];
string[3] names = ["Alice", "Bob", "Charlie"];
bool[3] flags = [true, false, true];

// Array with declared size, zero-initialized
int32[10] zeros = [];           // All elements are 0
float32[100] empty = [];        // All elements are 0.0

// Array with declared size and partial initializer
int32[5] partial = [1, 2, 3];   // Error: initializer size must match declared size
```

All elements in an array must be of the same type as specified in the declaration. The declared size must match the number of initializer elements if an initializer is provided.

## Accessing Array Elements

Individual array elements can be accessed using zero-based indexing:

```firescript
int8[5] scores = [85, 92, 78, 90, 88];

// Access individual elements
int8 firstScore = scores[0];    // 85
int8 thirdScore = scores[2];    // 78

// Modifying elements
scores[1] = 95;                // Array becomes [85, 95, 78, 90, 88]

// Negative indexing (from end)
int8 lastScore = scores[-1];    // 88 (last element)
int8 secondLast = scores[-2];   // 90 (second to last)
```

⚠️ **Warning:** Accessing an index outside the array bounds will cause a runtime error. Always ensure your index is valid before access.

## Array Operations

firescript provides several built-in methods for manipulating arrays:

- **`length()`** – Method that returns the current size of the array

```firescript
int8[5] data = [5, 10, 15, 20, 25];
int8 size = data.length();      // size = 5
```

## Working with Arrays

### Iterating Over Arrays

Use a `while` loop with an index variable, or a `for-in` loop to iterate over array elements:

```firescript
string[5] cities = ["New York", "London", "Tokyo", "Paris", "Sydney"];

// Using while loop with index
uint8 i = 0;
while (i < cities.length()) {
    print(cities[i]);
    i = i + 1;
}

// Using for-in loop (preferred)
for (string city in cities) {
    print(city);
}
```

String iteration is also supported with `for-in`, iterating over individual characters:

```firescript
string text = "hello";
for (string ch in text) {
    print(ch);  // Prints: h, e, l, l, o
}
```

### Array as Function Arguments

Arrays can be passed to functions. Function parameters can specify a fixed array size or use a size placeholder:

```firescript
// Function with sized array parameter
int32 sum(&int8[5] numbers) {
    int32 total = 0;
    uint8 i = 0;
    while (i < numbers.length()) {
        total = total + numbers[i];
        i = i + 1;
    }
    return total;
}

// Usage
int8[5] values = [1, 2, 3, 4, 5];
int32 result = sum(values);  // 15
```

### Nested Arrays

Arrays can contain other arrays (though this is not fully implemented yet):

```firescript
// 2D array example
int8[3][3] matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
];

// Accessing elements
int8 element = matrix[1][2];  // 6
```

## Common Array Patterns

### Finding an Element

```firescript
int8[5] numbers = [10, 20, 30, 40, 50];
int8 target = 30;
int8 index = -1;
uint8 i = 0;

while (i < numbers.length()) {
    if (numbers[i] == target) {
        index = i;
        break;
    }
    i = i + 1;
}

// index = 2 if found, -1 if not found
```

### Counting Occurrences

```firescript
int8[10] data = [1, 2, 1, 3, 1, 2, 1, 4, 5, 1];
int8 count = 0;
for (int8 val in data) {
    if (val == 1) {
        count = count + 1;
    }
}
// count = 5
```

## Features Not Yet Implemented

The following array features are planned but not yet implemented in the current compiler:

- **Array slicing** (`arr[start:end:step]`) – Extract a portion of the array

```firescript
// Future syntax
int8[5] numbers = [10, 20, 30, 40, 50];
int8[3] subset = numbers[1:4];  // Would be [20, 30, 40]
```

- **Additional utility methods**:
    - `sort()` – Sorting is not a core fixed-size array method; use standard library containers/utilities for sorting behavior

- **Array arithmetic** – Element-wise operations between arrays

Will use SIMD where possible for performance.

```firescript
// Future syntax
int8[3] a = [1, 2, 3];
int8[3] b = [4, 5, 6];

// add arrays element-wise
int8[3] c = a + b;  // Would be [5, 7, 9]

// subtract arrays element-wise
int8[3] e = b - a;  // Would be [3, 3, 3]

// add scalar to array
int8[3] g = a + 2;  // Would be [3, 4, 5]

// subtract scalar from array
int8[3] h = b - 1;  // Would be [3, 4, 5]

// multiply arrays element-wise
int8[3] j = a * b;  // Would be [4, 10, 18]

// divide arrays element-wise
int8[3] k = b / a;  // Would be [4, 2, 2]

// multiply arrays by scalar
int8[3] d = a * 2;  // Would be [2, 4, 6]

// divide arrays by scalar
int8[3] f = b / 2;  // Would be [2, 2, 3]

// dot product of two arrays
int8 dotProduct = a . b;  // Would be 32 (1*4 + 2*5 + 3*6)
```

## Implementation Status

Arrays are functional but with limited operations in the current compiler:

- ✅ Array declaration and initialization
- ✅ Element access with positive indices
- ✅ Negative index access for fixed-size arrays (`arr[-1]`)
- ✅ `length()` method (including on array function parameters)
- ✅ `index(value)` and `count(value)` on fixed-size arrays
- ✅ `for-in` loop over arrays (including array function parameters)
- ❌ Array slicing
- ❌ Core fixed-size array `sort()` method (use standard library)
- ❌ Multi-dimensional array operations

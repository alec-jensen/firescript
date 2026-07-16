# Arrays

> Core arrays are fixed-size. The compiler supports `length()`, negative indexing, `index(value)`, and `count(value)`. Array slicing and core `sort()` are not implemented; sorting should come from standard library containers/utilities.

## Array Basics

In firescript, arrays are fixed-size, ordered collections of elements that all share the same type. Arrays are Owned types—they are stored on the heap with pointers on the stack and use move semantics. Arrays are declared using square brackets and the size after the type.

## Declaration and Initialization

Arrays are declared by appending `[N]` to any valid type, where `N` is the fixed size. Arrays can be initialized with values in square brackets, or left uninitialized to be zero-initialized. When an initializer is provided, the size may be omitted (`T[]`) and is inferred from the initializer:

```firescript
// Array initialization with explicit values
numbers: int8[5] = [10, 20, 30, 40, 50];
names: string[3] = ["Alice", "Bob", "Charlie"];
flags: bool[3] = [true, false, true];

// Size inferred from the initializer
inferred: int32[] = [1, 2, 3, 4, 5];   // int32[5]

// Array with declared size, zero-initialized
zeros: int32[10] = [];           // All elements are 0
empty: float32[100] = [];        // All elements are 0.0

// Array with declared size and partial initializer
partial: int32[5] = [1, 2, 3];   // Error: initializer size must match declared size
```

All elements in an array must be of the same type as specified in the declaration. The declared size must match the number of initializer elements if an initializer is provided.

## Accessing Array Elements

Individual array elements can be accessed using zero-based indexing:

```firescript
scores: int8[5] = [85, 92, 78, 90, 88];

// Access individual elements
firstScore: int8 = scores[0];    // 85
thirdScore: int8 = scores[2];    // 78

// Modifying elements
scores[1] = 95;                // Array becomes [85, 95, 78, 90, 88]

// Negative indexing (from end)
lastScore: int8 = scores[-1];    // 88 (last element)
secondLast: int8 = scores[-2];   // 90 (second to last)
```

⚠️ **Warning:** Accessing an index outside the array bounds will cause a runtime error. Always ensure your index is valid before access.

## Array Operations

firescript provides several built-in methods for manipulating arrays:

- **`length()`** – Method that returns the current size of the array

```firescript
data: int8[5] = [5, 10, 15, 20, 25];
size: int8 = data.length();      // size = 5
```

## Working with Arrays

### Iterating Over Arrays

Use a `while` loop with an index variable, or a `for-in` loop to iterate over array elements:

```firescript
cities: string[5] = ["New York", "London", "Tokyo", "Paris", "Sydney"];

// Using while loop with index
i: uint8 = 0;
while (i < cities.length()) {
    print(cities[i]);
    i = i + 1;
}

// Using for-in loop (preferred)
for (city: string in cities) {
    print(city);
}
```

String iteration is also supported with `for-in`, iterating over individual characters:

```firescript
text: string = "hello";
for (ch: string in text) {
    print(ch);  // Prints: h, e, l, l, o
}
```

### Array as Function Arguments

Arrays can be passed to functions. Array parameters may be unsized (`T[]`), accepting an array of any length:

```firescript
// Function with array parameter
fn sum(numbers: int32[]) -> int32 {
    total: int32 = 0;
    i: int32 = 0;
    while (i < numbers.length()) {
        total = total + numbers[i];
        i = i + 1;
    }
    return total;
}

// Usage
values: int32[] = [1, 2, 3, 4, 5];
result: int32 = sum(values);  // 15
```

Arrays are Owned values, so passing one to an owned parameter moves it. Use a borrowed parameter (`&int32[] numbers`) to keep using the array at the call site afterwards — see [Memory Management](memory_management.md).

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
element: int8 = matrix[1][2];  // 6
```

## Common Array Patterns

### Finding an Element

```firescript
numbers: int8[5] = [10, 20, 30, 40, 50];
target: int8 = 30;
index: int8 = -1;
i: uint8 = 0;

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
data: int8[10] = [1, 2, 1, 3, 1, 2, 1, 4, 5, 1];
count: int8 = 0;
for (val: int8 in data) {
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
numbers: int8[5] = [10, 20, 30, 40, 50];
subset: int8[3] = numbers[1:4];  // Would be [20, 30, 40]
```

- **Additional utility methods**:
    - `sort()` – Sorting is not a core fixed-size array method; use standard library containers/utilities for sorting behavior

- **Array arithmetic** – Element-wise operations between arrays

Will use SIMD where possible for performance.

```firescript
// Future syntax
a: int8[3] = [1, 2, 3];
b: int8[3] = [4, 5, 6];

// add arrays element-wise
c: int8[3] = a + b;  // Would be [5, 7, 9]

// subtract arrays element-wise
e: int8[3] = b - a;  // Would be [3, 3, 3]

// add scalar to array
g: int8[3] = a + 2;  // Would be [3, 4, 5]

// subtract scalar from array
h: int8[3] = b - 1;  // Would be [3, 4, 5]

// multiply arrays element-wise
j: int8[3] = a * b;  // Would be [4, 10, 18]

// divide arrays element-wise
k: int8[3] = b / a;  // Would be [4, 2, 2]

// multiply arrays by scalar
d: int8[3] = a * 2;  // Would be [2, 4, 6]

// divide arrays by scalar
f: int8[3] = b / 2;  // Would be [2, 2, 3]

// dot product of two arrays
dotProduct: int8 = a . b;  // Would be 32 (1*4 + 2*5 + 3*6)
```

## Implementation Status

Arrays are functional but with limited operations in the current compiler:

- [IMPLEMENTED] Array declaration and initialization (sized `T[N]` and inferred `T[]` forms)
- [IMPLEMENTED] Element access with positive indices
- [IMPLEMENTED] Negative index access for fixed-size arrays (`arr[-1]`)
- [IMPLEMENTED] `length()` method (including on array function parameters)
- [IMPLEMENTED] `index(value)` and `count(value)` on fixed-size arrays
- [IMPLEMENTED] `for-in` loop over arrays (including array function parameters)
- [PLANNED] Array slicing
- [PLANNED] Core fixed-size array `sort()` method (use standard library)
- [PLANNED] Multi-dimensional array operations

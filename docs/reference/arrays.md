# Arrays

**Note:** Only dynamic arrays with literal initialization and methods `append`, `insert`, `pop`, `clear`, and `length` are supported by the compiler. Array slicing, negative indices, and other utility methods are not implemented.

## Array Basics

In firescript, arrays are dynamic, ordered collections of elements that all share the same type. Arrays can grow and shrink in size through various operations and are declared using square brackets after the type.

## Declaration and Initialization

Arrays are declared by appending `[]` to any valid type and initializing with values in square brackets:

```firescript
// Array initialization with values
int[] numbers = [10, 20, 30, 40, 50];
string[] names = ["Alice", "Bob", "Charlie"];
bool[] flags = [true, false, true];

// Empty array initialization
float[] prices = [];
```

All elements in an array must be of the same type as specified in the declaration.

## Accessing Array Elements

Individual array elements can be accessed using zero-based indexing:

```firescript
int[] scores = [85, 92, 78, 90, 88];

// Access individual elements
int firstScore = scores[0];    // 85
int thirdScore = scores[2];    // 78

// Modifying elements
scores[1] = 95;                // Array becomes [85, 95, 78, 90, 88]
```

⚠️ **Warning:** Accessing an index outside the array bounds will cause a runtime error. Always ensure your index is valid before access.

## Array Operations

firescript provides several built-in methods for manipulating arrays:

### Adding Elements

- **`append(element)`** – Add an element to the end of the array

```firescript
int[] numbers = [1, 2, 3];
numbers.append(4);        // Array becomes [1, 2, 3, 4]
```

- **`insert(index, element)`** – Insert an element at the specified position

```firescript
string[] fruits = ["apple", "orange", "banana"];
fruits.insert(1, "grape");   // Array becomes ["apple", "grape", "orange", "banana"]
```

### Removing Elements

- **`pop()`** – Remove and return the last element of the array

```firescript
int[] stack = [10, 20, 30];
int lastItem = stack.pop();  // lastItem = 30, stack becomes [10, 20]
```

- **`pop(index)`** – Remove and return the element at the specified index

```firescript
string[] colors = ["red", "green", "blue", "yellow"];
string removed = colors.pop(1);  // removed = "green", colors becomes ["red", "blue", "yellow"]
```

### Other Operations

- **`clear()`** – Removes all elements from the array

```firescript
bool[] flags = [true, false, true];
flags.clear();               // Array becomes []
```

- **`length`** – Property that returns the current size of the array

```firescript
int[] data = [5, 10, 15, 20, 25];
int size = data.length;      // size = 5
```

## Working with Arrays

### Iterating Over Arrays

Use a `while` loop with an index variable to iterate over array elements:

```firescript
string[] cities = ["New York", "London", "Tokyo", "Paris", "Sydney"];
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
int[] values = [1, 2, 3, 4, 5];
int result = sum(values);  // 15
```

### Nested Arrays

Arrays can contain other arrays (though this is not fully implemented yet):

```firescript
// 2D array example
int[][] matrix = [
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
int[] numbers = [10, 20, 30, 40, 50];
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

### Filtering Elements

```firescript
int[] numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
int[] evenNumbers = [];
int i = 0;

while (i < numbers.length) {
    if (numbers[i] % 2 == 0) {
        evenNumbers.append(numbers[i]);
    }
    i = i + 1;
}

// evenNumbers = [2, 4, 6, 8, 10]
```

### Transforming Arrays

```firescript
int[] numbers = [1, 2, 3, 4, 5];
int[] doubled = [];
int i = 0;

while (i < numbers.length) {
    doubled.append(numbers[i] * 2);
    i = i + 1;
}

// doubled = [2, 4, 6, 8, 10]
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
  - `remove(value)` – Remove the first occurrence of a value
  - `index(value)` – Find the index of the first occurrence of a value
  - `count(value)` – Count occurrences of a value
  - `sort()` – Sort the array elements

## Implementation Status

Arrays are functional but with limited operations in the current compiler:

- ✅ Array declaration and initialization
- ✅ Element access with positive indices
- ✅ Basic methods: append, insert, pop, clear
- ✅ Length property
- ❌ Array slicing
- ❌ Negative indices
- ❌ Advanced utility methods
- ❌ Multi-dimensional array operations

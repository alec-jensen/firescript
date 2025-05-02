# Arrays

**Note:** Only dynamic arrays with literal initialization and methods `append`, `insert`, `pop`, `clear`, and `length` are supported by the compiler. Array slicing, negative indices, and other utility methods are not implemented.

firescript supports dynamic arrays similar to Python lists.

## Declaration

```firescript
int[] nums = [1, 2, 3]
string[] words = []
```

## Operations

- `append(element)` – add to end
- `insert(index, element)` – insert at position
- `pop(index?)` – remove and return element; default removes last
- `clear()` – remove all elements
- `length` – property for size

```firescript
nums.append(4)
print(nums.pop(0))
print(nums)
```

## Not yet implemented

- Array slicing (`arr[start:end:step]`)
- Negative indices (e.g., `arr[-1]`)
- `remove(value)` – remove by value
- `index(value)` – get index of a value
- `count(value)` – count occurrences of a value
- `sort()` – sort the array

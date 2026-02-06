# Benchmarks

## Recursive Fibonacci

Algorithm pseudo‑code:

```
function fibonacci(n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

fibonacci(47)
```

Fibonacci of 47 is used to provide a reasonable runtime for comparison. Test is run 5 times and the average time is reported.
Tests are run on an AMD Ryzen 7 5800H processor.
These tests were run against the latest stable releases of each language's compiler/interpreter as of October 2025.

| Language      | Time (seconds) |
|---------------|----------------|
| C             | 3.5s (avg)     |
| firescript ⭐ | 4.2s (avg)     |
| Rust          | 5.8s (avg)     |
| Zig           | 6.5s (avg)     |
| Go            | 13.2s (avg)    |

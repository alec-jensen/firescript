# Types & Variables

**Note:** Tuple types, the generic placeholder `T`, and declarations without an initializer are not supported by the compiler. Only built-in primitive types (`int`, `float`, `double`, `bool`, `string`, `char`) are fully implemented.

FireScript supports the following built-in types:

- Numeric: `int`, `float`, `double`
- Boolean: `bool` (`true`, `false`)
- Text: `string`, `char`
- Composite: `tuple<T1, T2, …>`
- Generic placeholder: `T`

## Declaration and Initialization

```firescript
int age = 30
nullable string name = null
const float PI = 3.14
tuple<int, string> pair = (1, "two")
```

- Use `nullable` to allow a variable to hold `null`.
- Use `const` to declare read-only bindings.
- **Not yet implemented:** full support for tuple operations and generic type inference.

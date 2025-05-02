# Type System in firescript

firescript employs a static type system to enhance code reliability and catch errors early during the compilation phase. This means that the type of every variable and expression is checked before the code is run.

## Built-in Types

firescript provides several fundamental data types:

* **`int`**: Represents whole numbers (integers). Example: `int age = 30;`
* **`float`**: Represents single-precision floating-point numbers. Example: `float price = 19.95f;`
* **`double`**: Represents double-precision floating-point numbers, offering higher precision than `float`. Example: `double pi = 3.1415926535;`
* **`bool`**: Represents boolean values, either `true` or `false`. Example: `bool isActive = true;`
* **`string`**: Represents sequences of characters. Example: `string message = "Hello, World!";`
* **`char`**: Represents a single character. (Note: Currently handled similarly to strings in some contexts, formal `char` type might be refined). Example: `char initial = 'A';`
* **`void`**: Represents the absence of a type, primarily used as the return type for functions that do not return a value.

## Arrays

Arrays are ordered collections of elements of the *same* type.

* **Declaration**: Use square brackets `[]` after the type name.

    ```firescript
    int[] scores = [10, 20, 30];
    string[] names = ["Alice", "Bob"];
    ```

* **Access**: Use square brackets with an integer index (0-based).

    ```firescript
    int firstScore = scores[0]; // firstScore is 10
    ```

* **Type Checking**: The type checker ensures that you only assign arrays of the correct element type and access elements correctly. Array literals must contain elements of a consistent type.

## Nullability

By default, variables cannot hold the value `null`. To allow a variable to be assigned `null`, you must explicitly declare it as `nullable`.

* **Declaration**: Use the `nullable` keyword before the type.

    ```firescript
    nullable string username = null; // Allowed
    string title = "Default";

    title = null; // Error: Cannot assign null to non-nullable type 'string'

    username = "John"; // Can be assigned a non-null value later
    ```

* **Type Checking**: The type checker prevents assigning `null` to non-nullable variables and helps avoid null reference errors.

## Type Checking and Enforcement

The firescript parser includes a type-checking phase that runs after the initial syntax parsing.

1. **Variable Declarations**: When you declare a variable (`int x = 5;`), the type checker verifies that the type of the initializer (`5`, which is `int`) matches the declared type (`int`).
2. **Assignments**: When assigning a value to an existing variable (`x = 10;`), the checker ensures the assigned value's type is compatible with the variable's declared type.
3. **Expressions**: Operators (`+`, `-`, `*`, `/`, `==`, `>`, etc.) are checked to ensure they are used with compatible operand types. For example, arithmetic operators generally require numeric types (`int`, `float`, `double`), while `+` can also be used for string concatenation. The result type of an expression is also determined (e.g., `1 + 2.0` results in a `float`).
4. **Function Calls**: Arguments passed to functions are checked against the expected parameter types. The return value type is also enforced.
5. **Method Calls**: Similar to functions, arguments and the object the method is called on are type-checked.
6. **Array Operations**: Indexing requires an integer, and assigning elements requires matching the array's element type.

Type errors found during this phase will prevent the code from compiling further, providing early feedback on potential issues.

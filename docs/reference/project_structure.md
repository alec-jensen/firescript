# Project Structure

## init.fire

say you have the following project structure:

```
my_project/
├── src/
│   ├── main.fire
│   └── math
│       └── constants.fire
```

and you wanted to have functions directly available on `math`. You would create an `init.fire` file in the `math` directory:

```my_project/
├── src/
│   ├── main.fire
│   └── math
│       ├── init.fire
│       └── constants.fire
```

The `init.fire` file could look like this:

```firescript
// math/init.fire
int32 add(int32 a, int32 b) {
    return a + b;
}
```

Now, in your `main.fire`, you can import the `math` module and use the `add` function directly:

```firescript// main.fire
import math.add;

int32 result = add(5, 10);
```
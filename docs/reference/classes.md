# Classes & Inheritance

> Status: Classes are [IMPLEMENTED] — fields, methods, constructors, static methods, single inheritance, and generic classes all work in the current compiler. Sections describing planned semantics (e.g., custom `drop` destructors, interfaces) are marked as such. See [Memory Management](./memory_management.md) and the [Glossary](../glossary.md#memory-management-terms) for authoritative lifetime terminology.

## Object-Oriented Programming in firescript

firescript's class system is designed to provide a clean, intuitive approach to object-oriented programming with features like single inheritance, constructors, and both instance and static methods.

## Ownership & Lifetime

Classes are Owned (Non-Trivially Copyable) types unless specified otherwise. Their instances participate in the deterministic ownership model:

- Construction produces a new owned instance. Binding the result to a variable creates that variable as the initial owner.
- Passing an instance to a function parameter of owned type moves it; the caller's binding becomes invalid after the call unless the value is returned.
- Borrow syntax (`&Person`) allows read-only access to an instance without moving ownership.
- Fields that are owned types are dropped in reverse order of their construction when the containing object is dropped.
- A `drop(this)` method (planned) acts as a destructor. It runs exactly once at the inserted drop point. Compiler-inserted drops for owned values are implemented; user-defined `drop` methods are not yet.
- Cloning an instance will be explicit (`person.clone()`) if the type supports it (planned; semantics: deep vs copy-on-write TBD per type design).
- Inheritance does not change ownership: moving a `Student` moves its base `Person` subobject as part of the same operation.
- Borrowed references cannot escape beyond the lifetime of the owning instance; the compiler enforces non-escaping borrows.

Receiver convention: firescript distinguishes three receiver forms:

- **`&this`** — read-only borrow. The method may read fields but cannot assign to them. Use this for query/observer methods.
- **`&mut this`** — mutable borrow. The method may read and write fields without consuming the instance. Use this for constructors and any method that modifies state.
- **`this`** (owning) — the method takes ownership of the instance and consumes it. Use this only when the instance will be destroyed or irreversibly transferred (e.g., a `drop(this)` destructor).

The compiler enforces this: assigning to `this.field` inside a `&this` method is a compile error.

Borrowing applies only to Owned (Non-Trivially Copyable) types. Copyable types (`intN`, `floatN`, `bool`, `char`) are always passed and returned by value with implicit bitwise copy; using a borrow marker on copyable values is unnecessary and omitted below. Owned types include `string`, arrays, and user-defined classes. When you see `&Type` it implies the type is Owned.

### Example: Deterministic Drop Ordering

```firescript
class HandleBundle {
    File log;
    Socket conn;

    HandleBundle(&mut this, File &log, Socket &conn) {
        this.log = log;     // constructed first
        this.conn = conn;   // constructed second
    }

    drop(this) {            // planned destructor
        // Custom cleanup (optional). Fields are then dropped automatically
        // in reverse: conn then log.
    }
}

HandleBundle hb = makeHandles(); // this would be invalid since you need to provide owned File and Socket
process(&hb);  // borrow
// last use of hb here -> compiler may drop immediately after
```

### Takeaways

- Instances behave like other owned values: moves invalidate the source; borrows do not.
- Destruction is deterministic; order is reverse of field construction unless overridden by explicit semantics.
- No implicit deep copies: cloning is explicit.
- Inheritance does not introduce implicit sharing or reference counting.

## Naming Rules for Classes

Class names follow the same lexer rule as all other identifiers (see [Variables — Naming Rules](variables.md#naming-rules)): they must start with a letter or underscore and may contain letters, digits, and underscores.

By convention, class names use **PascalCase** (e.g., `Person`, `HttpClient`, `Vec2`). This is a convention only — the compiler does not enforce it.

Class field and method names follow the exact same rules as variable names.

## Defining a Class

A class in firescript is defined using the `class` keyword, followed by the class name and a block containing fields and methods:

```firescript
import @firescript/std.io.println;

class Person {
    // Fields (instance variables)
    string name;
    int32 age;
    bool isEmployed;

    // Constructor: 'this' refers to the instance being created.
    // Constructors mutate fields, so they take '&mut this'.
    Person(&mut this, string name, int32 age, bool isEmployed) {
        this.name = name;
        this.age = age;
        this.isEmployed = isEmployed;
    }

    // Instance method
    // Non-mutating: read-only borrow receiver
    string describe(&this) {
        return this.name + " is " + (this.age as string);
    }

    // Mutating via mutable borrow (does not consume the instance)
    void celebrate(&mut this) {
        this.age = this.age + 1;
        println(this.name + " is now " + (this.age as string) + " years old!");
    }

    // Static method (belongs to the class, not instances)
    static string species() {
        return "Homo sapiens";
    }
}
```

### Fields

Fields declare the data that each instance of a class will contain. Each field must have a type:

```firescript
class Rectangle {
    float32 width;
    float32 height;
    string color;
}
```

Fields can be nullable or const:

```firescript
class Configuration {
    const string APP_NAME;       // Constant field
    nullable string lastUser;    // Can be null
}
```

### Constructors

Constructors are special methods that initialize a new instance of a class. They take a receiver as their first parameter, which refers to the instance being created. Because constructors assign fields, the receiver is `&mut this`.

```firescript
class Point {
    float32 x;
    float32 y;

    // Basic constructor
    Point(&mut this, float32 x, float32 y) {
        this.x = x;
        this.y = y;
    }
}
```

Default parameter values (e.g., `float32 x = 0.0`) are [PLANNED] and not yet supported.

### Instance Methods

Instance methods are functions that belong to an instance of a class. They always take a receiver (`&this` or `&mut this`) as their first parameter:

```firescript
class Circle {
    float32 radius;

    Circle(&mut this, float32 radius) {
        this.radius = radius;
    }

    // Instance methods
    // Non-mutating
    float32 getArea(&this) {
        return 3.14159f32 * this.radius * this.radius;
    }

    float32 getCircumference(&this) {
        return 2.0f32 * 3.14159f32 * this.radius;
    }

    // Mutating via mutable borrow
    void scale(&mut this, float32 factor) {
        this.radius = this.radius * factor;
    }
}
```

### Static Methods

Static methods belong to the class itself rather than any instance. They don't take a `this` parameter:

```firescript
class MathUtils {
    // Static methods
    static int8 max(int8 a, int8 b) {
        if (a > b) {
            return a;
        } else {
            return b;
        }
    }

    static float32 average(float32 a, float32 b) {
        return (a + b) / 2.0;
    }
}
```

## Creating and Using Objects

Once a class is defined, you can create instances (objects) of that class:

```firescript
// Creating objects ('new' is optional)
Person alice = Person("Alice", 30, true);
Person bob = new Person("Bob", 25, false);

// Using instance methods
println(alice.describe());
alice.celebrate();

// Using static methods
string speciesName = Person.species();
```

## Inheritance

Inheritance allows a class to inherit fields and methods from another class. firescript supports single inheritance using the `from` keyword:

### `super` Attribute

The `super` attribute is an alias for the parent class and functions like super in other languages. It allows you to call the parent class's constructor from the child class (`this.super(...)`).
The main difference of `super` in firescript is that it is an attribute of the instance (`this.super`). Calling a parent's *method* implementation through `this.super.method(...)` is [PLANNED] and not yet supported.

```firescript
class Student from Person {
    string school;

    Student(&mut this, string name, int32 age, string school) {
        this.super(name, age, false);  // Call parent constructor
        this.school = school;
    }

    // Override parent method
    string describe(&this) {
        return this.name + " is " + (this.age as string) + " at " + this.school;
    }
}

Student s = new Student("Jane", 18, "State University");
println(s.describe());  // Uses Student's describe
println(s.name);        // Inherited field
```

### Method Overriding

Child classes can override methods from the parent class by redefining them:

```firescript
class Shape {
    string color;

    Shape(&mut this, string color) {
        this.color = color;
    }

    string describe(&this) {
        return "A " + this.color + " shape";
    }
}

class Square from Shape {
    float32 side;

    Square(&mut this, float32 side, string color) {
        this.super(color);
        this.side = side;
    }

    // Override the parent's describe method
    string describe(&this) {
        return "A " + this.color + " square with side " + (this.side as string);
    }
}
```

Calling the overridden parent implementation (`this.super.describe()`) is [PLANNED] and not yet supported.

## Polymorphism [PLANNED]

Polymorphism will allow objects of different classes in the same inheritance hierarchy to be treated as objects of a common superclass. This is not yet implemented:

```firescript
// Future syntax
Person[] people = [
    Person("Alice", 25, false),
    Student("Bob", 20, "State University")
];

uint8 i = 0;
while (i < people.length()) {
    println(people[i].describe());
    i = i + 1;
}
```

## Generic Classes

Classes support one or more type parameters declared with angle-bracket syntax. The compiler monomorphizes each unique instantiation automatically.

```firescript
copyable class Pair<T, U> {
    T first;
    U second;

    Pair(T first, U second) {
        this.first = first;
        this.second = second;
    }
}

// Usage
Pair<int32, string> p = Pair<int32, string>(42, "hello");
println(p.first);   // 42
println(p.second);  // hello
```

Both `copyable` and owned (heap-allocated) generic classes are supported. `@firescript/std.types` provides ready-made `Tuple<T, U>` and `Option<T>` types (see [Standard Library — Types](std/types.md)).

## Copyable Classes

A class may be annotated `copyable` to become Copyable if it satisfies:
1. All fields are Copyable.
2. No `drop` defined.
3. Fixed-size representation.
4. No disallowed interior references.

```firescript
copyable class Point {
    float32 x;
    float32 y;

    Point(&mut this, float32 x, float32 y) {
        this.x = x;
        this.y = y;
    }
}
```

Copyable class values copy bitwise; moves do not invalidate the source.

## Planned Class Features (Not Yet Implemented)

The following features are planned for future versions of firescript:

### Interfaces

```firescript
// Future syntax
interface Drawable {
    void draw(&this);
    bool isVisible(&this);
}

class Circle implements Drawable {
    float32 radius;
    
    Circle(&this, float32 radius) {
        this.radius = radius;
    }
    
    // Must implement all interface methods
    void draw(&this) {
        print("Drawing circle with radius " + (this.radius as string));
    }
    
    bool isVisible(&this) {
        return true;
    }
}

// Multiple interfaces
interface Movable {
    void move(&this, int32 dx, int32 dy);
}

class Square implements Drawable, Movable {
    float32 x;
    float32 y;
    float32 size;
    
    Square(&this, float32 x, float32 y, float32 size) {
        this.x = x;
        this.y = y;
        this.size = size;
    }
    
    // Implement Drawable
    void draw(&this) {
        print("Drawing square at (" + (this.x as string) + ", " + (this.y as string) + ")");
    }
    
    bool isVisible(&this) {
        return true;
    }
    
    // Implement Movable
    void move(&this, int32 dx, int32 dy) {
        this.x = this.x + cast<float32>(dx);
        this.y = this.y + cast<float32>(dy);
    }
}
```

### Abstract Classes and Methods

```firescript
// Future syntax
abstract class Animal {
    string species;
    
    Animal(&this, string &species) {
        this.species = species;
    }
    
    // Abstract method - no implementation
    abstract string makeSound(&this);
    
    // Regular method with implementation
    string getSpecies(&this) { // non-mutating borrow
        return this.species;
    }
}

class Cat from Animal {
    // Must implement abstract methods
    string makeSound(&this) { // non-mutating
        return "Meow";
    }
}
```

## Best Practices for Class Design

1. **Single Responsibility Principle**: Each class should have only one reason to change.\
2. **Favor Composition Over Inheritance**: Use object composition rather than complex inheritance hierarchies.
3. **Keep Inheritance Hierarchies Shallow**: Deep inheritance can lead to complexity.
4. **Use Descriptive Names**: Class names should be nouns, method names should be verbs.

## Implementation Status

Classes in firescript in the current compiler:

- [IMPLEMENTED] Class definitions
- [IMPLEMENTED] Instance fields and methods (`&this` / `&mut this` receivers)
- [IMPLEMENTED] Constructors (with `this.super(...)` chaining)
- [IMPLEMENTED] Static methods
- [IMPLEMENTED] Single inheritance (including multi-level)
- [IMPLEMENTED] Method overriding
- [IMPLEMENTED] Generic classes
- [IMPLEMENTED] Copyable classes (`copyable class`)
- [PLANNED] Calling parent methods via `this.super.method(...)`
- [PLANNED] Polymorphism
- [PLANNED] Interfaces
- [PLANNED] Access modifiers
- [PLANNED] Abstract classes
- [PLANNED] Custom `drop(this)` destructors
- [PLANNED] Default parameter values

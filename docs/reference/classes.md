# Classes & Inheritance

> Status: This page describes planned class semantics that integrate with the ownership-based memory model. See [Memory Management](./memory_management.md) and the [Glossary](../glossary.md#memory-management-terms) for authoritative lifetime terminology.

**Note:** Class definitions, inheritance, and methods are currently not supported by the compiler. This documentation describes the planned implementation.

## Object-Oriented Programming in firescript

firescript's class system is designed to provide a clean, intuitive approach to object-oriented programming with features like single inheritance, constructors, and both instance and static methods.

## Ownership & Lifetime (Planned)

Classes are Owned (Non-Trivially Copyable) types unless specified otherwise. Their instances participate in the deterministic ownership model:

- Construction produces a new owned instance. Binding the result to a variable creates that variable as the initial owner.
- Passing an instance to a function parameter of owned type moves it; the caller's binding becomes invalid after the call unless the value is returned.
- Future borrow syntax (`&Person`) will allow read-only access to an instance without moving ownership.
- Fields that are owned types are dropped in reverse order of their construction when the containing object is dropped.
- A `drop(this)` method (planned) acts as a destructor. It runs exactly once at the inserted drop point.
- Cloning an instance will be explicit (`person.clone()`) if the type supports it (semantics: deep vs copy-on-write TBD per type design).
- Inheritance does not change ownership: moving a `Student` moves its base `Person` subobject as part of the same operation.
- Borrowed references cannot escape beyond the lifetime of the owning instance; the compiler enforces non-escaping borrows.

Receiver convention (planned): Methods use a borrowed receiver `&this` by default—even when mutating fields—because internal mutation does not require taking ownership of the entire object. A method takes an owning `this` only when it will consume the instance (e.g., irreversible state transition, transferring internal resources, or explicit `drop(this)` destructor). Examples below follow this convention.

Borrowing applies only to Owned (Non-Trivially Copyable) types. Trivially Copyable (TC) types (`int`, `float`, `double`, `bool`, etc.) are always passed and returned by value with implicit bitwise copy; using a borrow marker on TC values is unnecessary and omitted below. When you see `&Type` it implies the type is Owned.

### Example: Deterministic Drop Ordering

```firescript
class HandleBundle {
    File log;
    Socket conn;

    HandleBundle(&this, File &log, Socket &conn) {
        this.log = log;     // constructed first
        this.conn = conn;   // constructed second
    }

    drop(&this) {            // planned destructor
        // Custom cleanup (optional). Fields are then dropped automatically
        // in reverse: conn then log.
    }
}

HandleBundle hb = makeHandles();
process(&hb);  // borrow
// last use of hb here -> compiler may drop immediately after
```

### Takeaways

- Instances behave like other owned values: moves invalidate the source; borrows do not.
- Destruction is deterministic; order is reverse of field construction unless overridden by explicit semantics.
- No implicit deep copies: cloning is explicit.
- Inheritance does not introduce implicit sharing or reference counting.

## Defining a Class

A class in firescript is defined using the `class` keyword, followed by the class name and a block containing fields and methods:

```firescript
class Person {
    // Fields (instance variables)
    string name;
    nullable int8 age;
    bool isEmployed;

    // Constructor: 'this' refers to the instance being created
    Person(&this, string &name, nullable int8 age = null, bool isEmployed = false) {
        this.name = name;
        this.age = age;
        this.isEmployed = isEmployed;
    }

    // Instance methods
    // Non-mutating: borrow receiver
    string getName(&this) {
        return &this.name;
    }

    nullable int getAge(&this) {
        return &this.age;
    }

    // Mutating via borrow (allowed; does not consume the instance)
    void celebrate(&this) {
        if (this.age != null) {
            this.age = this.age + 1;
            print(this.name + " is now " + toString(this.age) + " years old!");
        } else {
            print(this.name + " is celebrating!");
        }
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

Constructors are special methods that initialize a new instance of a class. They always take `this` as their first parameter, which refers to the instance being created. For most cases, `this` will be a borrowed parameter, unless you are transferring ownership of the instance.

```firescript
class Point {
    float32 x;
    float32 y;
    
    // Basic constructor
    Point(&this, float32 x, float32 y) {
        this.x = x;
        this.y = y;
    }
    
    // With default values (when implemented)
    Point(&this, float32 x = 0.0, float32 y = 0.0) {
        this.x = x;
        this.y = y;
    }
}
```

### Instance Methods

Instance methods are functions that belong to an instance of a class. They always take `this` as their first parameter:

```firescript
class Circle {
    float32 radius;

    Circle(&this, float32 radius) {
        this.radius = radius;
    }
    
    // Instance methods
    // Non-mutating
    float getArea(&this) {
        return 3.14159 * this.radius * this.radius;
    }

    float getCircumference(&this) {
        return 2.0 * 3.14159 * this.radius;
    }

    // Mutating via borrow
    void scale(&this, float32 factor) {
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
// Creating objects
Person alice = Person("Alice", 30, true);
Person bob = Person("Bob", null);

// Using instance methods
string aliceName = alice.getName();
alice.celebrate();

// Using static methods
string speciesName = Person.species();
```

## Inheritance

Inheritance allows a class to inherit fields and methods from another class. firescript supports single inheritance using the `from` keyword:

```firescript
class Student from Person {
    string school;
    string[] courses;
    
    Student(&this, string name, int8 age, string school) {
        super.Student(name, age);  // Call parent constructor
        this.school = school;
        this.courses = [];
    }
    
    // Additional methods
    void enroll(&this, string &course) {
        this.courses.append(course);
        print(this.name + " enrolled in " + course);
    }
    
    string[] getCourses(&this) {
        return this.courses;
    }
    
    // Override parent method
    void celebrate(&this) {
        super.celebrate();  // Call parent method
        print("Time for a student party!");
    }
}
```

### Method Overriding

Child classes can override methods from the parent class. To call the parent class's implementation, use `super`:

```firescript
class Shape {
    string color;
    
    Shape(&this, string color) {
        this.color = color;
    }
    
    string describe(&this) {
        return "A " + this.color + " shape";
    }
}

class Square from Shape {
    float32 side;
    
    Square(&this, float32 side, string color) {
        super.Shape(color);
        this.side = side;
    }
    
    // Override the parent's describe method
    string describe(&this) {
        return super.describe() + " (square with side " + toString(this.side) + ")";
    }
}
```

## Polymorphism

Polymorphism allows objects of different classes in the same inheritance hierarchy to be treated as objects of a common superclass:

```firescript
// Example of future planned polymorphism
Person[] people = [
    Person("Alice", 25),
    Student("Bob", 20, "State University")
];

uint8 i = 0;
while (i < people.length) {
    print(people[i].getName());
    i = i + 1;
}
```

## Planned Class Features (Not Yet Implemented)

The following features are planned for future versions of firescript:

### Interfaces

```firescript
// Future syntax
interface Drawable {
    void draw(&this)
    bool isVisible(&this)
}

class Circle implements Drawable {
    // Must implement all interface methods
    void draw(&this) {
        // Drawing implementation
    }
    
    bool isVisible(&this) {
        return true;
    }
}
```

### Generics on Classes

```firescript
// Future syntax
class Box<T> {
    nullable T value;
    
    Box(&this) {
        this.value = null;
    }
    
    void set(&this, T newValue) { // if T is Owned this is a borrow; if T is TC it's just a copy
        this.value = newValue;
    }

    nullable T get(&this) {
        return this.value;
    }
}

// Usage
Box<int> intBox = Box<int>();
intBox.set(42);
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

Classes in firescript are planned but not yet implemented in the current compiler:

- ❌ Class definitions
- ❌ Instance fields and methods
- ❌ Constructors
- ❌ Static methods
- ❌ Inheritance
- ❌ Method overriding
- ❌ Polymorphism
- ❌ Interfaces
- ❌ Access modifiers
- ❌ Abstract classes
- ❌ Meta-attributes/annotations
- ❌ Generics on classes

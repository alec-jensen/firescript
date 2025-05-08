# Classes & Inheritance

**Note:** Class definitions, inheritance, and methods are currently not supported by the compiler. This documentation describes the planned implementation.

## Object-Oriented Programming in firescript

firescript's class system is designed to provide a clean, intuitive approach to object-oriented programming with features like single inheritance, constructors, and both instance and static methods.

## Defining a Class

A class in firescript is defined using the `class` keyword, followed by the class name and a block containing fields and methods:

```firescript
class Person {
    // Fields (instance variables)
    string name;
    nullable int age;
    bool isEmployed;

    // Constructor: 'this' refers to the instance being created
    Person(this, string name, nullable int age = null, bool isEmployed = false) {
        this.name = name;
        this.age = age;
        this.isEmployed = isEmployed;
    }

    // Instance methods
    string getName(this) {
        return this.name;
    }

    nullable int getAge(this) {
        return this.age;
    }

    void celebrate(this) {
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
    float width;
    float height;
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

Constructors are special methods that initialize a new instance of a class. They always take `this` as their first parameter, which refers to the instance being created:

```firescript
class Point {
    float x;
    float y;
    
    // Basic constructor
    Point(this, float x, float y) {
        this.x = x;
        this.y = y;
    }
    
    // With default values (when implemented)
    Point(this, float x = 0.0, float y = 0.0) {
        this.x = x;
        this.y = y;
    }
}
```

### Instance Methods

Instance methods are functions that belong to an instance of a class. They always take `this` as their first parameter:

```firescript
class Circle {
    float radius;
    
    Circle(this, float radius) {
        this.radius = radius;
    }
    
    // Instance methods
    float getArea(this) {
        return 3.14159 * this.radius * this.radius;
    }
    
    float getCircumference(this) {
        return 2.0 * 3.14159 * this.radius;
    }
    
    void scale(this, float factor) {
        this.radius = this.radius * factor;
    }
}
```

### Static Methods

Static methods belong to the class itself rather than any instance. They don't take a `this` parameter:

```firescript
class MathUtils {
    // Static methods
    static int max(int a, int b) {
        if (a > b) {
            return a;
        } else {
            return b;
        }
    }
    
    static float average(float a, float b) {
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
    
    Student(this, string name, int age, string school) {
        super.Student(name, age);  // Call parent constructor
        this.school = school;
        this.courses = [];
    }
    
    // Additional methods
    void enroll(this, string course) {
        this.courses.append(course);
        print(this.name + " enrolled in " + course);
    }
    
    string[] getCourses(this) {
        return this.courses;
    }
    
    // Override parent method
    void celebrate(this) {
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
    
    Shape(this, string color) {
        this.color = color;
    }
    
    string describe(this) {
        return "A " + this.color + " shape";
    }
}

class Square from Shape {
    float side;
    
    Square(this, float side, string color) {
        super.Shape(color);
        this.side = side;
    }
    
    // Override the parent's describe method
    string describe(this) {
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

int i = 0;
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
    void draw(this)
    bool isVisible(this)
}

class Circle implements Drawable {
    // Must implement all interface methods
    void draw(this) {
        // Drawing implementation
    }
    
    bool isVisible(this) {
        return true;
    }
}
```

### Generics on Classes

```firescript
// Future syntax
class Box<T> {
    nullable T value;
    
    Box(this) {
        this.value = null;
    }
    
    void set(this, T newValue) {
        this.value = newValue;
    }
    
    nullable T get(this) {
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
    
    Animal(this, string species) {
        this.species = species;
    }
    
    // Abstract method - no implementation
    abstract string makeSound(this);
    
    // Regular method with implementation
    string getSpecies(this) {
        return this.species;
    }
}

class Cat from Animal {
    // Must implement abstract methods
    string makeSound(this) {
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

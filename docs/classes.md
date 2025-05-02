# Classes & Inheritance

**Note:** Class definitions, inheritance, and methods are currently not supported by the compiler.

firescript provides class definitions, constructors, instance/static methods, and single inheritance.

## Defining a Class

```firescript
class Person {
    string name;
    nullable int age;

    // Constructor: 'this' is the instance
    Person(this, string name, int age) {
        this.name = name
        this.age = age
    }

    // Instance method
    string getName(this) {
        return this.name
    }

    // Static method
    static string species() {
        return "Homo sapiens"
    }
}
```

## Inheritance

```firescript
class Student from Person {
    string school;

    Student(this, string name, int age, string school) {
        super.Student(name, age)  // call parent constructor
        this.school = school
    }

    string getSchool(this) {
        return this.school
    }
}
```

## Not yet implemented

- Interfaces and multiple inheritance
- Generics on classes
- Meta‑attributes and user‑defined annotations
- Access modifiers (`public`, `private`, `protected`)
- Abstract classes and methods

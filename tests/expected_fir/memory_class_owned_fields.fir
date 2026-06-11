module memory_class_owned_fields

type Person owned {
  name: string
  age: int32
}

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    Call(stdout, [%1], ["own"])
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    Call(stdout, [%3], ["own"])
    Return()
}

function Person.Person(this: &mut Person, name: string, age: int32) -> Person {
  block_0:
    %0 = Allocate(Person, [])
    DeclareLocal("this", Person, %0)
    %1 = LoadVar("name") -> string
    %2 = LoadVar("this") -> Person
    StoreField(%2, "name", %1)
    %3 = LoadVar("age") -> int32
    %4 = LoadVar("this") -> Person
    StoreField(%4, "age", %3)
    %5 = LoadVar("this") -> Person
    Return(%5)
}

function Person.greet(this: &Person) -> string {
  block_0:
    %0 = StringLiteral("Hello, ", string)
    %1 = LoadVar("this") -> Person
    %2 = LoadField(%1, "name")
    %3 = BinaryOp("+", %0, %2)
    Return(%3)
}

function main() -> void {
  block_0:
    %0 = StringLiteral("Alice", string)
    %1 = IntLiteral(30, int32)
    %2 = Call(Person.Person, [%0, %1], ["own", "own"]) -> Person
    DeclareLocal("p", Person, %2)
    %3 = LoadVar("p") -> Person
    %4 = LoadField(%3, "name")
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("p") -> Person
    %6 = LoadField(%5, "age")
    Call(println, [%6], ["borrow"])
    %7 = LoadVar("p") -> Person
    %8 = MethodCall(%7, "greet", [], []) -> string
    Call(println, [%8], ["borrow"])
    %9 = LoadVar("p") -> Person
    Drop(%9)
    Return()
}

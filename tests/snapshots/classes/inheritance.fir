module inheritance

type Person owned {
  name: string
  age: int32
}

type Student owned : Person {
  name: string
  age: int32
  school: string
}

type A owned {
  id: string
}

type B owned : A {
  id: string
  bid: string
}

type C owned : B {
  bid: string
  id: string
  cid: string
}

type D owned : C {
  cid: string
  bid: string
  id: string
  did: string
}

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("text", string, %1)
    %2 = LoadVar("text") -> string
    Call(stdout, [%2], ["borrow"])
    %3 = LoadVar("text") -> string
    Drop(%3)
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("cast_text", string, %1)
    %2 = LoadVar("cast_text") -> string
    %3 = StringLiteral("\n", string)
    %4 = BinaryOp("+", %2, %3)
    DeclareLocal("text", string, %4)
    %5 = LoadVar("cast_text") -> string
    Drop(%5)
    %6 = LoadVar("text") -> string
    Call(stdout, [%6], ["borrow"])
    %7 = LoadVar("text") -> string
    Drop(%7)
    Return()
}

function Person.Person(name: string, age: int32) -> Person {
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

function Person.describe(this: &Person) -> string {
  block_0:
    %0 = LoadVar("this") -> Person
    %1 = LoadField(%0, "name")
    %2 = StringLiteral(" is ", string)
    %3 = BinaryOp("+", %1, %2)
    %4 = LoadVar("this") -> Person
    %5 = LoadField(%4, "age")
    %6 = Call(toString, [%5], ["borrow"]) -> string
    %7 = BinaryOp("+", %3, %6)
    Return(%7)
}

function Student.Student(name: string, age: int32, school: string) -> Student {
  block_0:
    %0 = Allocate(Student, [])
    DeclareLocal("this", Student, %0)
    %1 = LoadVar("name") -> string
    %2 = LoadVar("age") -> int32
    %3 = Call(Person.Person, [%1, %2], ["own", "own"]) -> Person
    %4 = LoadVar("this") -> Student
    %5 = LoadField(%3, "name")
    StoreField(%4, "name", %5)
    %6 = LoadField(%3, "age")
    StoreField(%4, "age", %6)
    Call(free_shallow, [%3], ["own"])
    %7 = LoadVar("school") -> string
    %8 = LoadVar("this") -> Student
    StoreField(%8, "school", %7)
    %9 = LoadVar("this") -> Student
    Return(%9)
}

function Student.describe(this: &Student) -> string {
  block_0:
    %0 = LoadVar("this") -> Student
    %1 = LoadField(%0, "name")
    %2 = StringLiteral(" is ", string)
    %3 = BinaryOp("+", %1, %2)
    %4 = LoadVar("this") -> Student
    %5 = LoadField(%4, "age")
    %6 = Call(toString, [%5], ["borrow"]) -> string
    %7 = BinaryOp("+", %3, %6)
    %8 = StringLiteral(" at ", string)
    %9 = BinaryOp("+", %7, %8)
    %10 = LoadVar("this") -> Student
    %11 = LoadField(%10, "school")
    %12 = BinaryOp("+", %9, %11)
    Return(%12)
}

function A.A(id: string) -> A {
  block_0:
    %0 = Allocate(A, [])
    DeclareLocal("this", A, %0)
    %1 = LoadVar("id") -> string
    %2 = LoadVar("this") -> A
    StoreField(%2, "id", %1)
    %3 = LoadVar("this") -> A
    Return(%3)
}

function A.root(this: &A) -> string {
  block_0:
    %0 = LoadVar("this") -> A
    %1 = LoadField(%0, "id")
    Return(%1)
}

function A.chain(this: &A) -> string {
  block_0:
    %0 = StringLiteral("A(", string)
    %1 = LoadVar("this") -> A
    %2 = LoadField(%1, "id")
    %3 = BinaryOp("+", %0, %2)
    %4 = StringLiteral(")", string)
    %5 = BinaryOp("+", %3, %4)
    Return(%5)
}

function B.B(id: string, bid: string) -> B {
  block_0:
    %0 = Allocate(B, [])
    DeclareLocal("this", B, %0)
    %1 = LoadVar("id") -> string
    %2 = Call(A.A, [%1], ["own"]) -> A
    %3 = LoadVar("this") -> B
    %4 = LoadField(%2, "id")
    StoreField(%3, "id", %4)
    Call(free_shallow, [%2], ["own"])
    %5 = LoadVar("bid") -> string
    %6 = LoadVar("this") -> B
    StoreField(%6, "bid", %5)
    %7 = LoadVar("this") -> B
    Return(%7)
}

function B.onlyB(this: &B) -> string {
  block_0:
    %0 = LoadVar("this") -> B
    %1 = LoadField(%0, "bid")
    Return(%1)
}

function B.chain(this: &B) -> string {
  block_0:
    %0 = StringLiteral("A(", string)
    %1 = LoadVar("this") -> B
    %2 = LoadField(%1, "id")
    %3 = BinaryOp("+", %0, %2)
    %4 = StringLiteral(")->B(", string)
    %5 = BinaryOp("+", %3, %4)
    %6 = LoadVar("this") -> B
    %7 = LoadField(%6, "bid")
    %8 = BinaryOp("+", %5, %7)
    %9 = StringLiteral(")", string)
    %10 = BinaryOp("+", %8, %9)
    Return(%10)
}

function B.root(this: &B) -> string {
  block_0:
    %0 = LoadVar("this") -> B
    %1 = LoadField(%0, "id")
    Return(%1)
}

function C.C(id: string, bid: string, cid: string) -> C {
  block_0:
    %0 = Allocate(C, [])
    DeclareLocal("this", C, %0)
    %1 = LoadVar("id") -> string
    %2 = LoadVar("bid") -> string
    %3 = Call(B.B, [%1, %2], ["own", "own"]) -> B
    %4 = LoadVar("this") -> C
    %5 = LoadField(%3, "id")
    StoreField(%4, "id", %5)
    %6 = LoadField(%3, "bid")
    StoreField(%4, "bid", %6)
    Call(free_shallow, [%3], ["own"])
    %7 = LoadVar("cid") -> string
    %8 = LoadVar("this") -> C
    StoreField(%8, "cid", %7)
    %9 = LoadVar("this") -> C
    Return(%9)
}

function C.onlyC(this: &C) -> string {
  block_0:
    %0 = LoadVar("this") -> C
    %1 = LoadField(%0, "cid")
    Return(%1)
}

function C.chain(this: &C) -> string {
  block_0:
    %0 = StringLiteral("A(", string)
    %1 = LoadVar("this") -> C
    %2 = LoadField(%1, "id")
    %3 = BinaryOp("+", %0, %2)
    %4 = StringLiteral(")->B(", string)
    %5 = BinaryOp("+", %3, %4)
    %6 = LoadVar("this") -> C
    %7 = LoadField(%6, "bid")
    %8 = BinaryOp("+", %5, %7)
    %9 = StringLiteral(")->C(", string)
    %10 = BinaryOp("+", %8, %9)
    %11 = LoadVar("this") -> C
    %12 = LoadField(%11, "cid")
    %13 = BinaryOp("+", %10, %12)
    %14 = StringLiteral(")", string)
    %15 = BinaryOp("+", %13, %14)
    Return(%15)
}

function C.onlyB(this: &C) -> string {
  block_0:
    %0 = LoadVar("this") -> C
    %1 = LoadField(%0, "bid")
    Return(%1)
}

function C.root(this: &C) -> string {
  block_0:
    %0 = LoadVar("this") -> C
    %1 = LoadField(%0, "id")
    Return(%1)
}

function D.D(id: string, bid: string, cid: string, did: string) -> D {
  block_0:
    %0 = Allocate(D, [])
    DeclareLocal("this", D, %0)
    %1 = LoadVar("id") -> string
    %2 = LoadVar("bid") -> string
    %3 = LoadVar("cid") -> string
    %4 = Call(C.C, [%1, %2, %3], ["own", "own", "own"]) -> C
    %5 = LoadVar("this") -> D
    %6 = LoadField(%4, "id")
    StoreField(%5, "id", %6)
    %7 = LoadField(%4, "bid")
    StoreField(%5, "bid", %7)
    %8 = LoadField(%4, "cid")
    StoreField(%5, "cid", %8)
    Call(free_shallow, [%4], ["own"])
    %9 = LoadVar("did") -> string
    %10 = LoadVar("this") -> D
    StoreField(%10, "did", %9)
    %11 = LoadVar("this") -> D
    Return(%11)
}

function D.chain(this: &D) -> string {
  block_0:
    %0 = StringLiteral("A(", string)
    %1 = LoadVar("this") -> D
    %2 = LoadField(%1, "id")
    %3 = BinaryOp("+", %0, %2)
    %4 = StringLiteral(")->B(", string)
    %5 = BinaryOp("+", %3, %4)
    %6 = LoadVar("this") -> D
    %7 = LoadField(%6, "bid")
    %8 = BinaryOp("+", %5, %7)
    %9 = StringLiteral(")->C(", string)
    %10 = BinaryOp("+", %8, %9)
    %11 = LoadVar("this") -> D
    %12 = LoadField(%11, "cid")
    %13 = BinaryOp("+", %10, %12)
    %14 = StringLiteral(")->D(", string)
    %15 = BinaryOp("+", %13, %14)
    %16 = LoadVar("this") -> D
    %17 = LoadField(%16, "did")
    %18 = BinaryOp("+", %15, %17)
    %19 = StringLiteral(")", string)
    %20 = BinaryOp("+", %18, %19)
    Return(%20)
}

function D.onlyC(this: &D) -> string {
  block_0:
    %0 = LoadVar("this") -> D
    %1 = LoadField(%0, "cid")
    Return(%1)
}

function D.onlyB(this: &D) -> string {
  block_0:
    %0 = LoadVar("this") -> D
    %1 = LoadField(%0, "bid")
    Return(%1)
}

function D.root(this: &D) -> string {
  block_0:
    %0 = LoadVar("this") -> D
    %1 = LoadField(%0, "id")
    Return(%1)
}

function main() -> void {
  block_0:
    %0 = StringLiteral("Jane", string)
    %1 = IntLiteral(18, int32)
    %2 = StringLiteral("School", string)
    %3 = Call(Student.Student, [%0, %1, %2], ["own", "own", "own"]) -> Student
    DeclareLocal("s", Student, %3)
    %4 = LoadVar("s") -> Student
    %5 = MethodCall(%4, "describe", [], []) -> string
    Call(println, [%5], ["borrow"])
    %6 = LoadVar("s") -> Student
    %7 = LoadField(%6, "name")
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("s") -> Student
    %9 = LoadField(%8, "age")
    Call(println, [%9], ["borrow"])
    %10 = LoadVar("s") -> Student
    Drop(%10)
    %11 = StringLiteral("a", string)
    %12 = StringLiteral("b", string)
    %13 = StringLiteral("c", string)
    %14 = StringLiteral("d", string)
    %15 = Call(D.D, [%11, %12, %13, %14], ["own", "own", "own", "own"]) -> D
    DeclareLocal("d", D, %15)
    %16 = LoadVar("d") -> D
    %17 = MethodCall(%16, "chain", [], []) -> string
    Call(println, [%17], ["borrow"])
    %18 = LoadVar("d") -> D
    %19 = LoadField(%18, "id")
    Call(println, [%19], ["borrow"])
    %20 = LoadVar("d") -> D
    %21 = LoadField(%20, "bid")
    Call(println, [%21], ["borrow"])
    %22 = LoadVar("d") -> D
    %23 = LoadField(%22, "cid")
    Call(println, [%23], ["borrow"])
    %24 = LoadVar("d") -> D
    %25 = LoadField(%24, "did")
    Call(println, [%25], ["borrow"])
    %26 = LoadVar("d") -> D
    %27 = MethodCall(%26, "root", [], []) -> string
    Call(println, [%27], ["borrow"])
    %28 = LoadVar("d") -> D
    %29 = MethodCall(%28, "onlyB", [], []) -> string
    Call(println, [%29], ["borrow"])
    %30 = LoadVar("d") -> D
    %31 = MethodCall(%30, "onlyC", [], []) -> string
    Call(println, [%31], ["borrow"])
    %32 = LoadVar("d") -> D
    Drop(%32)
    Return()
}

fir module inheritance

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

function<T> @print(value: &T) -> void {
  L0:
    %0 = loadvar.T value
    %1 = cast.string %0
    local text: string = %1
    %2 = loadvar.string text
    call @stdout(%2 borrow)
    %3 = loadvar.string text
    drop %3
    ret
}

function<T> @println(value: &T) -> void {
  L0:
    %0 = loadvar.T value
    %1 = cast.string %0
    local cast_text: string = %1
    %2 = loadvar.string cast_text
    %3 = strconst "\n"
    %4 = binop "+", %2, %3
    local text: string = %4
    %5 = loadvar.string cast_text
    drop %5
    %6 = loadvar.string text
    call @stdout(%6 borrow)
    %7 = loadvar.string text
    drop %7
    ret
}

function @Person.Person(name: string, age: int32) -> Person {
  L0:
    %0 = alloc.Person()
    local this: Person = %0
    %1 = loadvar.string name
    %2 = loadvar.Person this
    storefield %2, "name", %1
    %3 = loadvar.int32 age
    %4 = loadvar.Person this
    storefield %4, "age", %3
    %5 = loadvar.Person this
    ret %5
}

function @Person.describe(this: &Person) -> string {
  L0:
    %0 = loadvar.Person this
    %1 = loadfield.string %0, "name"
    %2 = strconst " is "
    %3 = binop "+", %1, %2
    %4 = loadvar.Person this
    %5 = loadfield.int32 %4, "age"
    %6 = call.string @toString(%5 borrow)
    %7 = binop "+", %3, %6
    ret %7
}

function @Student.Student(name: string, age: int32, school: string) -> Student {
  L0:
    %0 = alloc.Student()
    local this: Student = %0
    %1 = loadvar.string name
    %2 = loadvar.int32 age
    %3 = call.Person @Person.Person(%1 own, %2 own)
    %4 = loadvar.Student this
    %5 = loadfield.string %3, "name"
    storefield %4, "name", %5
    %6 = loadfield.int32 %3, "age"
    storefield %4, "age", %6
    call @free_shallow(%3 own)
    %7 = loadvar.string school
    %8 = loadvar.Student this
    storefield %8, "school", %7
    %9 = loadvar.Student this
    ret %9
}

function @Student.describe(this: &Student) -> string {
  L0:
    %0 = loadvar.Student this
    %1 = loadfield.string %0, "name"
    %2 = strconst " is "
    %3 = binop "+", %1, %2
    %4 = loadvar.Student this
    %5 = loadfield.int32 %4, "age"
    %6 = call.string @toString(%5 borrow)
    %7 = binop "+", %3, %6
    %8 = strconst " at "
    %9 = binop "+", %7, %8
    %10 = loadvar.Student this
    %11 = loadfield.string %10, "school"
    %12 = binop "+", %9, %11
    ret %12
}

function @A.A(id: string) -> A {
  L0:
    %0 = alloc.A()
    local this: A = %0
    %1 = loadvar.string id
    %2 = loadvar.A this
    storefield %2, "id", %1
    %3 = loadvar.A this
    ret %3
}

function @A.root(this: &A) -> string {
  L0:
    %0 = loadvar.A this
    %1 = loadfield.string %0, "id"
    ret %1
}

function @A.chain(this: &A) -> string {
  L0:
    %0 = strconst "A("
    %1 = loadvar.A this
    %2 = loadfield.string %1, "id"
    %3 = binop "+", %0, %2
    %4 = strconst ")"
    %5 = binop "+", %3, %4
    ret %5
}

function @B.B(id: string, bid: string) -> B {
  L0:
    %0 = alloc.B()
    local this: B = %0
    %1 = loadvar.string id
    %2 = call.A @A.A(%1 own)
    %3 = loadvar.B this
    %4 = loadfield.string %2, "id"
    storefield %3, "id", %4
    call @free_shallow(%2 own)
    %5 = loadvar.string bid
    %6 = loadvar.B this
    storefield %6, "bid", %5
    %7 = loadvar.B this
    ret %7
}

function @B.onlyB(this: &B) -> string {
  L0:
    %0 = loadvar.B this
    %1 = loadfield.string %0, "bid"
    ret %1
}

function @B.chain(this: &B) -> string {
  L0:
    %0 = strconst "A("
    %1 = loadvar.B this
    %2 = loadfield.string %1, "id"
    %3 = binop "+", %0, %2
    %4 = strconst ")->B("
    %5 = binop "+", %3, %4
    %6 = loadvar.B this
    %7 = loadfield.string %6, "bid"
    %8 = binop "+", %5, %7
    %9 = strconst ")"
    %10 = binop "+", %8, %9
    ret %10
}

function @B.root(this: &B) -> string {
  L0:
    %0 = loadvar.B this
    %1 = loadfield.string %0, "id"
    ret %1
}

function @C.C(id: string, bid: string, cid: string) -> C {
  L0:
    %0 = alloc.C()
    local this: C = %0
    %1 = loadvar.string id
    %2 = loadvar.string bid
    %3 = call.B @B.B(%1 own, %2 own)
    %4 = loadvar.C this
    %5 = loadfield.string %3, "id"
    storefield %4, "id", %5
    %6 = loadfield.string %3, "bid"
    storefield %4, "bid", %6
    call @free_shallow(%3 own)
    %7 = loadvar.string cid
    %8 = loadvar.C this
    storefield %8, "cid", %7
    %9 = loadvar.C this
    ret %9
}

function @C.onlyC(this: &C) -> string {
  L0:
    %0 = loadvar.C this
    %1 = loadfield.string %0, "cid"
    ret %1
}

function @C.chain(this: &C) -> string {
  L0:
    %0 = strconst "A("
    %1 = loadvar.C this
    %2 = loadfield.string %1, "id"
    %3 = binop "+", %0, %2
    %4 = strconst ")->B("
    %5 = binop "+", %3, %4
    %6 = loadvar.C this
    %7 = loadfield.string %6, "bid"
    %8 = binop "+", %5, %7
    %9 = strconst ")->C("
    %10 = binop "+", %8, %9
    %11 = loadvar.C this
    %12 = loadfield.string %11, "cid"
    %13 = binop "+", %10, %12
    %14 = strconst ")"
    %15 = binop "+", %13, %14
    ret %15
}

function @C.onlyB(this: &C) -> string {
  L0:
    %0 = loadvar.C this
    %1 = loadfield.string %0, "bid"
    ret %1
}

function @C.root(this: &C) -> string {
  L0:
    %0 = loadvar.C this
    %1 = loadfield.string %0, "id"
    ret %1
}

function @D.D(id: string, bid: string, cid: string, did: string) -> D {
  L0:
    %0 = alloc.D()
    local this: D = %0
    %1 = loadvar.string id
    %2 = loadvar.string bid
    %3 = loadvar.string cid
    %4 = call.C @C.C(%1 own, %2 own, %3 own)
    %5 = loadvar.D this
    %6 = loadfield.string %4, "id"
    storefield %5, "id", %6
    %7 = loadfield.string %4, "bid"
    storefield %5, "bid", %7
    %8 = loadfield.string %4, "cid"
    storefield %5, "cid", %8
    call @free_shallow(%4 own)
    %9 = loadvar.string did
    %10 = loadvar.D this
    storefield %10, "did", %9
    %11 = loadvar.D this
    ret %11
}

function @D.chain(this: &D) -> string {
  L0:
    %0 = strconst "A("
    %1 = loadvar.D this
    %2 = loadfield.string %1, "id"
    %3 = binop "+", %0, %2
    %4 = strconst ")->B("
    %5 = binop "+", %3, %4
    %6 = loadvar.D this
    %7 = loadfield.string %6, "bid"
    %8 = binop "+", %5, %7
    %9 = strconst ")->C("
    %10 = binop "+", %8, %9
    %11 = loadvar.D this
    %12 = loadfield.string %11, "cid"
    %13 = binop "+", %10, %12
    %14 = strconst ")->D("
    %15 = binop "+", %13, %14
    %16 = loadvar.D this
    %17 = loadfield.string %16, "did"
    %18 = binop "+", %15, %17
    %19 = strconst ")"
    %20 = binop "+", %18, %19
    ret %20
}

function @D.onlyC(this: &D) -> string {
  L0:
    %0 = loadvar.D this
    %1 = loadfield.string %0, "cid"
    ret %1
}

function @D.onlyB(this: &D) -> string {
  L0:
    %0 = loadvar.D this
    %1 = loadfield.string %0, "bid"
    ret %1
}

function @D.root(this: &D) -> string {
  L0:
    %0 = loadvar.D this
    %1 = loadfield.string %0, "id"
    ret %1
}

function @main() -> void {
  L0:
    %0 = strconst "Jane"
    %1 = const.int32 18
    %2 = strconst "School"
    %3 = call.Student @Student.Student(%0 own, %1 own, %2 own)
    local s: Student = %3
    %4 = loadvar.Student s
    %5 = mcall.string %4, "describe"()
    call @println(%5 borrow)
    %6 = loadvar.Student s
    %7 = loadfield.string %6, "name"
    call @println(%7 borrow)
    %8 = loadvar.Student s
    %9 = loadfield.int32 %8, "age"
    call @println(%9 borrow)
    %10 = loadvar.Student s
    drop %10
    %11 = strconst "a"
    %12 = strconst "b"
    %13 = strconst "c"
    %14 = strconst "d"
    %15 = call.D @D.D(%11 own, %12 own, %13 own, %14 own)
    local d: D = %15
    %16 = loadvar.D d
    %17 = mcall.string %16, "chain"()
    call @println(%17 borrow)
    %18 = loadvar.D d
    %19 = loadfield.string %18, "id"
    call @println(%19 borrow)
    %20 = loadvar.D d
    %21 = loadfield.string %20, "bid"
    call @println(%21 borrow)
    %22 = loadvar.D d
    %23 = loadfield.string %22, "cid"
    call @println(%23 borrow)
    %24 = loadvar.D d
    %25 = loadfield.string %24, "did"
    call @println(%25 borrow)
    %26 = loadvar.D d
    %27 = mcall.string %26, "root"()
    call @println(%27 borrow)
    %28 = loadvar.D d
    %29 = mcall.string %28, "onlyB"()
    call @println(%29 borrow)
    %30 = loadvar.D d
    %31 = mcall.string %30, "onlyC"()
    call @println(%31 borrow)
    %32 = loadvar.D d
    drop %32
    ret
}

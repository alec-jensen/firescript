fir module memory_class_owned_fields

type Person owned {
  name: string
  age: int32
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

function @Person.greet(this: &Person) -> string {
  L0:
    %0 = strconst "Hello, "
    %1 = loadvar.Person this
    %2 = loadfield.string %1, "name"
    %3 = binop "+", %0, %2
    ret %3
}

function @main() -> void {
  L0:
    %0 = strconst "Alice"
    %1 = const.int32 30
    %2 = call.Person @Person.Person(%0 own, %1 own)
    local p: Person = %2
    %3 = loadvar.Person p
    %4 = loadfield.string %3, "name"
    call @println(%4 borrow)
    %5 = loadvar.Person p
    %6 = loadfield.int32 %5, "age"
    call @println(%6 borrow)
    %7 = loadvar.Person p
    %8 = mcall.string %7, "greet"()
    call @println(%8 borrow)
    %9 = loadvar.Person p
    drop %9
    ret
}

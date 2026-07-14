fir module generics_class_basic

type Pair<T, U> copyable {
  first: T
  second: U
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

function<T, U> @Pair.Pair(first: T, second: U) -> Pair {
  L0:
    %0 = alloc.Pair()
    local this: Pair = %0
    %1 = loadvar.T first
    %2 = loadvar.Pair this
    storefield %2, "first", %1
    %3 = loadvar.U second
    %4 = loadvar.Pair this
    storefield %4, "second", %3
    %5 = loadvar.Pair this
    ret %5
}

function @main() -> void {
  L0:
    %0 = const.int32 10
    %1 = const.int32 20
    %2 = call.Pair<int32, int32> @Pair.Pair(%0 own, %1 own)
    local p1: Pair<int32, int32> = %2
    %3 = const.int32 42
    %4 = strconst "hello"
    %5 = call.Pair<int32, string> @Pair.Pair(%3 own, %4 own)
    local p2: Pair<int32, string> = %5
    %6 = loadvar.Pair<int32, int32> p1
    %7 = loadfield.int32 %6, "first"
    call @println(%7 borrow)
    %8 = loadvar.Pair<int32, int32> p1
    %9 = loadfield.int32 %8, "second"
    call @println(%9 borrow)
    %10 = loadvar.Pair<int32, string> p2
    %11 = loadfield.int32 %10, "first"
    call @println(%11 borrow)
    %12 = loadvar.Pair<int32, string> p2
    %13 = loadfield.string %12, "second"
    call @println(%13 borrow)
    ret
}

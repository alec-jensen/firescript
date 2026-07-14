fir module imports_multi

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

function @square(x: int32) -> int32 {
  L0:
    %0 = loadvar.int32 x
    %1 = loadvar.int32 x
    %2 = binop "*", %0, %1
    ret %2
}

function @double_val(x: int32) -> int32 {
  L0:
    %0 = loadvar.int32 x
    %1 = loadvar.int32 x
    %2 = binop "+", %0, %1
    ret %2
}

function @wrap(s: string) -> string {
  L0:
    %0 = strconst "["
    %1 = loadvar.string s
    %2 = binop "+", %0, %1
    %3 = strconst "]"
    %4 = binop "+", %2, %3
    %5 = loadvar.string s
    drop %5
    ret %4
}

function @main() -> void {
  L0:
    %0 = const.int32 100
    local MAX: int32 = %0
    %1 = strconst "-- Math Operations --"
    call @println(%1 borrow)
    %2 = const.int32 5
    %3 = call.int32 @square(%2 own)
    call @println(%3 borrow)
    %4 = const.int32 10
    %5 = call.int32 @square(%4 own)
    call @println(%5 borrow)
    %6 = loadvar.int32 MAX
    call @println(%6 borrow)
    %7 = strconst "-- String Operations --"
    call @println(%7 borrow)
    %8 = strconst "hello"
    %9 = call.string @wrap(%8 own)
    call @println(%9 borrow)
    %10 = strconst "imports work"
    %11 = call.string @wrap(%10 own)
    call @println(%11 borrow)
    ret
}

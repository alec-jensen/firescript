fir module fibonacci

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

function @fib(n: int64) -> int64 {
  L0:
    %0 = loadvar.int64 n
    %1 = const.int64 1
    %2 = binop "<=", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.int64 n
    %4 = const.int64 1
    %5 = binop "-", %3, %4
    %6 = call.int64 @fib(%5 own)
    %7 = loadvar.int64 n
    %8 = const.int64 2
    %9 = binop "-", %7, %8
    %10 = call.int64 @fib(%9 own)
    %11 = binop "+", %6, %10
    ret %11

  L2:
    %12 = loadvar.int64 n
    ret %12
}

function @main() -> void {
  L0:
    %0 = const.int64 20
    %1 = call.int64 @fib(%0 own)
    call @println(%1 borrow)
    ret
}

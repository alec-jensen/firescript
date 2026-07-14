fir module types_int64

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

function @main() -> void {
  L0:
    %0 = const.int64 9223372036854775807
    local i64_test: int64 = %0
    %1 = const.int64 9223372036854775808
    %2 = unop "-", %1
    local i64_negative: int64 = %2
    %3 = loadvar.int64 i64_test
    call @println(%3 borrow)
    %4 = loadvar.int64 i64_negative
    call @println(%4 borrow)
    %5 = loadvar.int64 i64_test
    %6 = const.int64 1000
    %7 = binop "/", %5, %6
    call @println(%7 borrow)
    ret
}

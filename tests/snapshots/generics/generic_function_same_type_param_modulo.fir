fir module generic_function_same_type_param_modulo

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

function<T> @modT(a: T, b: T) -> T {
  L0:
    %0 = loadvar.T a
    %1 = loadvar.T b
    %2 = binop "%", %0, %1
    ret %2
}

function @main() -> void {
  L0:
    %0 = const.int32 5
    %1 = const.int32 2
    %2 = call.int32 @modT(%0 own, %1 own)
    call @println(%2 borrow)
    ret
}

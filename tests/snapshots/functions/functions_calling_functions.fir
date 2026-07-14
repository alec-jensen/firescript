fir module functions_calling_functions

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

function @add(a: int32, b: int32) -> int32 {
  L0:
    %0 = loadvar.int32 a
    %1 = loadvar.int32 b
    %2 = binop "+", %0, %1
    ret %2
}

function @double(x: int32) -> int32 {
  L0:
    %0 = loadvar.int32 x
    %1 = const.int32 2
    %2 = binop "*", %0, %1
    ret %2
}

function @addThenDouble(a: int32, b: int32) -> int32 {
  L0:
    %0 = loadvar.int32 a
    %1 = loadvar.int32 b
    %2 = call.int32 @add(%0 own, %1 own)
    local sum: int32 = %2
    %3 = loadvar.int32 sum
    %4 = call.int32 @double(%3 own)
    ret %4
}

function @complexCalc(a: int32, b: int32, c: int32) -> int32 {
  L0:
    %0 = loadvar.int32 a
    %1 = loadvar.int32 b
    %2 = binop "+", %0, %1
    local temp: int32 = %2
    %3 = loadvar.int32 temp
    %4 = loadvar.int32 c
    %5 = binop "*", %3, %4
    storevar temp, %5
    %6 = loadvar.int32 temp
    %7 = const.int32 100
    %8 = binop ">", %6, %7
    br %8, L2, L1

  L1:
    %9 = loadvar.int32 temp
    ret %9

  L2:
    %10 = loadvar.int32 temp
    %11 = const.int32 2
    %12 = binop "/", %10, %11
    ret %12
}

function @main() -> void {
  L0:
    %0 = const.int32 2
    %1 = const.int32 3
    %2 = call.int32 @addThenDouble(%0 own, %1 own)
    call @println(%2 borrow)
    %3 = const.int32 10
    %4 = const.int32 20
    %5 = const.int32 5
    %6 = call.int32 @complexCalc(%3 own, %4 own, %5 own)
    call @println(%6 borrow)
    %7 = const.int32 2
    %8 = const.int32 3
    %9 = const.int32 4
    %10 = call.int32 @complexCalc(%7 own, %8 own, %9 own)
    call @println(%10 borrow)
    ret
}

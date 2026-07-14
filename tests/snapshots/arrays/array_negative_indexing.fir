fir module array_negative_indexing

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

function @last(values: int32[]) -> int32 {
  L0:
    %0 = loadvar.int32[] values
    %1 = const.int32 1
    %2 = unop "-", %1
    %3 = indexarray.int32 %0, %2
    %4 = loadvar.int32[] values
    drop %4
    ret %3
}

function @main() -> void {
  L0:
    %0 = const.int32 10
    %1 = const.int32 20
    %2 = const.int32 30
    %3 = const.int32 40
    %4 = arrayconst.int32[4] [%0, %1, %2, %3]
    local nums: int32[4] = %4
    %5 = loadvar.int32[4] nums
    %6 = const.int32 1
    %7 = unop "-", %6
    %8 = indexarray.int32 %5, %7
    call @println(%8 borrow)
    %9 = loadvar.int32[4] nums
    %10 = const.int32 2
    %11 = unop "-", %10
    %12 = indexarray.int32 %9, %11
    call @println(%12 borrow)
    %13 = const.int32 3
    %14 = unop "-", %13
    local idx: int32 = %14
    %15 = loadvar.int32[4] nums
    %16 = loadvar.int32 idx
    %17 = indexarray.int32 %15, %16
    call @println(%17 borrow)
    %18 = const.int32 99
    %19 = loadvar.int32[4] nums
    %20 = const.int32 1
    %21 = unop "-", %20
    storearray %19, %21, %18
    %22 = loadvar.int32[4] nums
    %23 = const.int32 3
    %24 = indexarray.int32 %22, %23
    call @println(%24 borrow)
    %25 = loadvar.int32[4] nums
    %26 = call.int32 @last(%25 own)
    call @println(%26 borrow)
    ret
}

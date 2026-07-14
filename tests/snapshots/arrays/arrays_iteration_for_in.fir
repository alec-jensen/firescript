fir module arrays_iteration_for_in

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
    %0 = const.int32 5
    %1 = const.int32 10
    %2 = const.int32 15
    %3 = const.int32 20
    %4 = arrayconst.int32[4] [%0, %1, %2, %3]
    local nums: int32[4] = %4
    %5 = const.int32 0
    local __i_n: int32 = %5
    jmp L1

  L1:
    %6 = loadvar.int32 __i_n
    %7 = const.int32 4
    %8 = binop "<", %6, %7
    br %8, L2, L3

  L2:
    %9 = loadvar.int32[4] nums
    %10 = loadvar.int32 __i_n
    %11 = indexarray.int32 %9, %10
    local n: int32 = %11
    %12 = loadvar.int32 n
    call @println(%12 borrow)
    jmp L4

  L3:
    %13 = loadvar.int32[4] nums
    drop %13
    ret

  L4:
    %14 = loadvar.int32 __i_n
    %15 = const.int32 1
    %16 = binop "+", %14, %15
    storevar __i_n, %16
    jmp L1
}

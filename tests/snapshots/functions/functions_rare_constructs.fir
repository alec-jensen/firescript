fir module functions_rare_constructs

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

function @sumArray(values: int32[]) -> int32 {
  L0:
    %0 = const.int32 0
    local total: int32 = %0
    %1 = const.int32 0
    local i: int32 = %1
    jmp L1

  L1:
    %2 = loadvar.int32 i
    %3 = loadvar.int32[] values
    %4 = call.int32 @array_length(%3 borrow)
    %5 = binop "<", %2, %4
    br %5, L2, L3

  L2:
    %6 = loadvar.int32 total
    %7 = loadvar.int32[] values
    %8 = loadvar.int32 i
    %9 = indexarray.int32 %7, %8
    %10 = binop "+", %6, %9
    storevar total, %10
    %11 = loadvar.int32 i
    %12 = const.int32 1
    %13 = binop "+", %11, %12
    storevar i, %13
    jmp L1

  L3:
    %14 = loadvar.int32[] values
    drop %14
    %15 = loadvar.int32 total
    ret %15
}

function @main() -> void {
  L0:
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = const.int32 3
    %3 = const.int32 4
    %4 = arrayconst.int32[4] [%0, %1, %2, %3]
    %5 = call.int32 @sumArray(%4 own)
    call @println(%5 borrow)
    %6 = const.int32 100
    %7 = const.int32 200
    %8 = const.int32 300
    %9 = arrayconst.int32[3] [%6, %7, %8]
    local named: int32[3] = %9
    %10 = const.int32 0
    local sum2: int32 = %10
    %11 = const.int32 0
    local __i_v: int32 = %11
    jmp L1

  L1:
    %12 = loadvar.int32 __i_v
    %13 = const.int32 3
    %14 = binop "<", %12, %13
    br %14, L2, L3

  L2:
    %15 = loadvar.int32[3] named
    %16 = loadvar.int32 __i_v
    %17 = indexarray.int32 %15, %16
    local v: int32 = %17
    %18 = loadvar.int32 sum2
    %19 = loadvar.int32 v
    %20 = binop "+", %18, %19
    storevar sum2, %20
    jmp L4

  L3:
    %21 = loadvar.int32[3] named
    drop %21
    %22 = loadvar.int32 sum2
    call @println(%22 borrow)
    ret

  L4:
    %23 = loadvar.int32 __i_v
    %24 = const.int32 1
    %25 = binop "+", %23, %24
    storevar __i_v, %25
    jmp L1
}

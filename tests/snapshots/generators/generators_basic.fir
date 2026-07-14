fir module generators_basic

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

generator @range(end: int32) -> generator<int32> {
  L0:
    %0 = const.int32 0
    local i: int32 = %0
    jmp L1

  L1:
    %1 = loadvar.int32 i
    %2 = loadvar.int32 end
    %3 = binop "<", %1, %2
    br %3, L2, L3

  L2:
    %4 = loadvar.int32 i
    yield %4
    %5 = loadvar.int32 i
    %6 = const.int32 1
    %7 = binop "+", %5, %6
    storevar i, %7
    jmp L1

  L3:
    ret
}

generator @rangeFrom(start: int32, end: int32) -> generator<int32> {
  L0:
    %0 = loadvar.int32 start
    local i: int32 = %0
    jmp L1

  L1:
    %1 = loadvar.int32 i
    %2 = loadvar.int32 end
    %3 = binop "<", %1, %2
    br %3, L2, L3

  L2:
    %4 = loadvar.int32 i
    yield %4
    %5 = loadvar.int32 i
    %6 = const.int32 1
    %7 = binop "+", %5, %6
    storevar i, %7
    jmp L1

  L3:
    ret
}

generator @rangeStep(start: int32, end: int32, step: int32) -> generator<int32> {
  L0:
    %0 = loadvar.int32 start
    local i: int32 = %0
    jmp L1

  L1:
    %1 = loadvar.int32 i
    %2 = loadvar.int32 end
    %3 = binop "<", %1, %2
    br %3, L2, L3

  L2:
    %4 = loadvar.int32 i
    yield %4
    %5 = loadvar.int32 i
    %6 = loadvar.int32 step
    %7 = binop "+", %5, %6
    storevar i, %7
    jmp L1

  L3:
    ret
}

generator @countdown(n: int32) -> generator<int32> {
  L0:
    %0 = loadvar.int32 n
    local i: int32 = %0
    jmp L1

  L1:
    %1 = loadvar.int32 i
    %2 = const.int32 0
    %3 = binop ">", %1, %2
    br %3, L2, L3

  L2:
    %4 = loadvar.int32 i
    yield %4
    %5 = loadvar.int32 i
    %6 = const.int32 1
    %7 = binop "-", %5, %6
    storevar i, %7
    jmp L1

  L3:
    ret
}

function @main() -> void {
  L0:
    %0 = const.int32 5
    %1 = gennew.generator<int32> @range(%0)
    local __gen_i: generator<int32> = %1
    jmp L1

  L1:
    %2 = loadvar.generator<int32> __gen_i
    %3 = gennext.bool %2
    br %3, L2, L3

  L2:
    %4 = loadvar.generator<int32> __gen_i
    %5 = genvalue.int32 %4
    local i: int32 = %5
    %6 = loadvar.int32 i
    call @println(%6 borrow)
    jmp L1

  L3:
    %7 = loadvar.generator<int32> __gen_i
    drop %7
    %8 = const.int32 2
    %9 = const.int32 6
    %10 = gennew.generator<int32> @rangeFrom(%8, %9)
    local __gen_i__2: generator<int32> = %10
    jmp L4

  L4:
    %11 = loadvar.generator<int32> __gen_i__2
    %12 = gennext.bool %11
    br %12, L5, L6

  L5:
    %13 = loadvar.generator<int32> __gen_i__2
    %14 = genvalue.int32 %13
    local i__2: int32 = %14
    %15 = loadvar.int32 i__2
    call @println(%15 borrow)
    jmp L4

  L6:
    %16 = loadvar.generator<int32> __gen_i__2
    drop %16
    %17 = const.int32 0
    %18 = const.int32 10
    %19 = const.int32 3
    %20 = gennew.generator<int32> @rangeStep(%17, %18, %19)
    local __gen_i__3: generator<int32> = %20
    jmp L7

  L7:
    %21 = loadvar.generator<int32> __gen_i__3
    %22 = gennext.bool %21
    br %22, L8, L9

  L8:
    %23 = loadvar.generator<int32> __gen_i__3
    %24 = genvalue.int32 %23
    local i__3: int32 = %24
    %25 = loadvar.int32 i__3
    call @println(%25 borrow)
    jmp L7

  L9:
    %26 = loadvar.generator<int32> __gen_i__3
    drop %26
    %27 = const.int32 3
    %28 = gennew.generator<int32> @countdown(%27)
    local __gen_v: generator<int32> = %28
    jmp L10

  L10:
    %29 = loadvar.generator<int32> __gen_v
    %30 = gennext.bool %29
    br %30, L11, L12

  L11:
    %31 = loadvar.generator<int32> __gen_v
    %32 = genvalue.int32 %31
    local v: int32 = %32
    %33 = loadvar.int32 v
    call @println(%33 borrow)
    jmp L10

  L12:
    %34 = loadvar.generator<int32> __gen_v
    drop %34
    ret
}

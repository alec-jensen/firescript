fir module generics_basic

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

function<T> @max(a: T, b: T) -> T {
  L0:
    %0 = loadvar.T a
    %1 = loadvar.T b
    %2 = binop ">", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.T b
    ret %3

  L2:
    %4 = loadvar.T a
    ret %4
}

function<T> @min(a: T, b: T) -> T {
  L0:
    %0 = loadvar.T a
    %1 = loadvar.T b
    %2 = binop "<", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.T b
    ret %3

  L2:
    %4 = loadvar.T a
    ret %4
}

function<T> @abs(x: T, zero: T) -> T {
  L0:
    %0 = loadvar.T x
    %1 = loadvar.T zero
    %2 = binop "<", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.T x
    ret %3

  L2:
    %4 = loadvar.T x
    %5 = unop "-", %4
    ret %5
}

function @main() -> void {
  L0:
    %0 = const.int32 10
    local a: int32 = %0
    %1 = const.int32 20
    local b: int32 = %1
    %2 = loadvar.int32 a
    %3 = loadvar.int32 b
    %4 = call.int32 @max(%2 own, %3 own)
    local maxVal: int32 = %4
    %5 = loadvar.int32 maxVal
    call @println(%5 borrow)
    %6 = loadvar.int32 a
    %7 = loadvar.int32 b
    %8 = call.int32 @min(%6 own, %7 own)
    local minVal: int32 = %8
    %9 = loadvar.int32 minVal
    call @println(%9 borrow)
    %10 = const.int64 100
    local c: int64 = %10
    %11 = const.int64 50
    local d: int64 = %11
    %12 = loadvar.int64 c
    %13 = loadvar.int64 d
    %14 = call.int64 @max(%12 own, %13 own)
    local maxVal64: int64 = %14
    %15 = loadvar.int64 maxVal64
    call @println(%15 borrow)
    %16 = fconst.float32 3.14
    local e: float32 = %16
    %17 = fconst.float32 2.71
    local f: float32 = %17
    %18 = loadvar.float32 e
    %19 = loadvar.float32 f
    %20 = call.float32 @max(%18 own, %19 own)
    local maxFloat: float32 = %20
    %21 = loadvar.float32 maxFloat
    call @println(%21 borrow)
    %22 = const.int32 42
    %23 = unop "-", %22
    local negInt: int32 = %23
    %24 = loadvar.int32 negInt
    %25 = const.int32 0
    %26 = call.int32 @abs(%24 own, %25 own)
    local absInt: int32 = %26
    %27 = loadvar.int32 absInt
    call @println(%27 borrow)
    %28 = const.int64 999
    %29 = unop "-", %28
    local negInt64: int64 = %29
    %30 = loadvar.int64 negInt64
    %31 = const.int64 0
    %32 = call.int64 @abs(%30 own, %31 own)
    local absInt64: int64 = %32
    %33 = loadvar.int64 absInt64
    call @println(%33 borrow)
    ret
}

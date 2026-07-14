fir module numeric_casts

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
    %0 = strconst "-- numeric casts --"
    call @println(%0 borrow)
    %1 = const.int16 127
    %2 = cast.int8 %1
    local i8: int8 = %2
    %3 = loadvar.int8 i8
    call @println(%3 borrow)
    %4 = const.int32 0
    %5 = const.int32 12345
    %6 = binop "-", %4, %5
    %7 = cast.int16 %6
    local i16: int16 = %7
    %8 = loadvar.int16 i16
    call @println(%8 borrow)
    %9 = const.int64 123456
    %10 = cast.int32 %9
    local i32: int32 = %10
    %11 = loadvar.int32 i32
    call @println(%11 borrow)
    %12 = const.int64 123456789
    %13 = cast.int64 %12
    local i64: int64 = %13
    %14 = loadvar.int64 i64
    call @println(%14 borrow)
    %15 = const.int16 255
    %16 = cast.uint8 %15
    local u8: uint8 = %16
    %17 = loadvar.uint8 u8
    call @println(%17 borrow)
    %18 = const.int32 65000
    %19 = cast.uint16 %18
    local u16: uint16 = %19
    %20 = loadvar.uint16 u16
    call @println(%20 borrow)
    %21 = const.uint64 4000000000
    %22 = cast.uint32 %21
    local u32: uint32 = %22
    %23 = loadvar.uint32 u32
    call @println(%23 borrow)
    %24 = const.uint64 9000000000
    %25 = cast.uint64 %24
    local u64: uint64 = %25
    %26 = loadvar.uint64 u64
    call @println(%26 borrow)
    %27 = fconst.float64 3.25
    %28 = cast.float32 %27
    local f32: float32 = %28
    %29 = loadvar.float32 f32
    call @println(%29 borrow)
    %30 = fconst.float64 3.25
    %31 = cast.float64 %30
    local f64: float64 = %31
    %32 = loadvar.float64 f64
    call @println(%32 borrow)
    %33 = fconst.float64 3.25
    %34 = cast.float128 %33
    local f128: float128 = %34
    %35 = loadvar.float128 f128
    call @println(%35 borrow)
    ret
}

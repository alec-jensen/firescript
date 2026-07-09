module numeric_casts

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    Call(stdout, [%1], ["own"])
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    Call(stdout, [%3], ["own"])
    Return()
}

function main() -> void {
  block_0:
    %0 = StringLiteral("-- numeric casts --", string)
    Call(println, [%0], ["borrow"])
    %1 = IntLiteral(127, int16)
    %2 = Cast(%1, int8)
    DeclareLocal("i8", int8, %2)
    %3 = LoadVar("i8") -> int8
    Call(println, [%3], ["borrow"])
    %4 = IntLiteral(0, int32)
    %5 = IntLiteral(12345, int32)
    %6 = BinaryOp("-", %4, %5)
    %7 = Cast(%6, int16)
    DeclareLocal("i16", int16, %7)
    %8 = LoadVar("i16") -> int16
    Call(println, [%8], ["borrow"])
    %9 = IntLiteral(123456, int64)
    %10 = Cast(%9, int32)
    DeclareLocal("i32", int32, %10)
    %11 = LoadVar("i32") -> int32
    Call(println, [%11], ["borrow"])
    %12 = IntLiteral(123456789, int64)
    %13 = Cast(%12, int64)
    DeclareLocal("i64", int64, %13)
    %14 = LoadVar("i64") -> int64
    Call(println, [%14], ["borrow"])
    %15 = IntLiteral(255, int16)
    %16 = Cast(%15, uint8)
    DeclareLocal("u8", uint8, %16)
    %17 = LoadVar("u8") -> uint8
    Call(println, [%17], ["borrow"])
    %18 = IntLiteral(65000, int32)
    %19 = Cast(%18, uint16)
    DeclareLocal("u16", uint16, %19)
    %20 = LoadVar("u16") -> uint16
    Call(println, [%20], ["borrow"])
    %21 = IntLiteral(4000000000, uint64)
    %22 = Cast(%21, uint32)
    DeclareLocal("u32", uint32, %22)
    %23 = LoadVar("u32") -> uint32
    Call(println, [%23], ["borrow"])
    %24 = IntLiteral(9000000000, uint64)
    %25 = Cast(%24, uint64)
    DeclareLocal("u64", uint64, %25)
    %26 = LoadVar("u64") -> uint64
    Call(println, [%26], ["borrow"])
    %27 = FloatLiteral(3.25, float64)
    %28 = Cast(%27, float32)
    DeclareLocal("f32", float32, %28)
    %29 = LoadVar("f32") -> float32
    Call(println, [%29], ["borrow"])
    %30 = FloatLiteral(3.25, float64)
    %31 = Cast(%30, float64)
    DeclareLocal("f64", float64, %31)
    %32 = LoadVar("f64") -> float64
    Call(println, [%32], ["borrow"])
    %33 = FloatLiteral(3.25, float64)
    %34 = Cast(%33, float128)
    DeclareLocal("f128", float128, %34)
    %35 = LoadVar("f128") -> float128
    Call(println, [%35], ["borrow"])
    Return()
}

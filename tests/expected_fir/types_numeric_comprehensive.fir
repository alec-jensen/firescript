module types_numeric_comprehensive

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
    %0 = StringLiteral("=== Numeric Type Tests ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- int8 ---", string)
    Call(println, [%1], ["borrow"])
    %2 = IntLiteral(128, int8)
    %3 = UnaryOp("-", %2)
    DeclareLocal("i8_min", int8, %3)
    %4 = IntLiteral(127, int8)
    DeclareLocal("i8_max", int8, %4)
    %5 = IntLiteral(0, int8)
    DeclareLocal("i8_zero", int8, %5)
    %6 = LoadVar("i8_min") -> int8
    Call(println, [%6], ["borrow"])
    %7 = LoadVar("i8_max") -> int8
    Call(println, [%7], ["borrow"])
    %8 = LoadVar("i8_zero") -> int8
    Call(println, [%8], ["borrow"])
    %9 = LoadVar("i8_max") -> int8
    %10 = IntLiteral(1, int8)
    %11 = BinaryOp("+", %9, %10)
    Call(println, [%11], ["borrow"])
    %12 = LoadVar("i8_min") -> int8
    %13 = IntLiteral(1, int8)
    %14 = BinaryOp("-", %12, %13)
    Call(println, [%14], ["borrow"])
    %15 = StringLiteral("--- int16 ---", string)
    Call(println, [%15], ["borrow"])
    %16 = IntLiteral(32768, int16)
    %17 = UnaryOp("-", %16)
    DeclareLocal("i16_min", int16, %17)
    %18 = IntLiteral(32767, int16)
    DeclareLocal("i16_max", int16, %18)
    %19 = IntLiteral(1000, int16)
    DeclareLocal("i16_test", int16, %19)
    %20 = LoadVar("i16_min") -> int16
    Call(println, [%20], ["borrow"])
    %21 = LoadVar("i16_max") -> int16
    Call(println, [%21], ["borrow"])
    %22 = LoadVar("i16_test") -> int16
    Call(println, [%22], ["borrow"])
    %23 = LoadVar("i16_test") -> int16
    %24 = IntLiteral(2, int16)
    %25 = BinaryOp("*", %23, %24)
    Call(println, [%25], ["borrow"])
    %26 = StringLiteral("--- int32 ---", string)
    Call(println, [%26], ["borrow"])
    %27 = IntLiteral(2147483648, int32)
    %28 = UnaryOp("-", %27)
    DeclareLocal("i32_min", int32, %28)
    %29 = IntLiteral(2147483647, int32)
    DeclareLocal("i32_max", int32, %29)
    %30 = IntLiteral(1000000, int32)
    DeclareLocal("i32_test", int32, %30)
    %31 = LoadVar("i32_min") -> int32
    Call(println, [%31], ["borrow"])
    %32 = LoadVar("i32_max") -> int32
    Call(println, [%32], ["borrow"])
    %33 = LoadVar("i32_test") -> int32
    Call(println, [%33], ["borrow"])
    %34 = LoadVar("i32_test") -> int32
    %35 = IntLiteral(500000, int32)
    %36 = BinaryOp("+", %34, %35)
    Call(println, [%36], ["borrow"])
    %37 = StringLiteral("--- int64 ---", string)
    Call(println, [%37], ["borrow"])
    %38 = IntLiteral(9223372036854775807, int64)
    DeclareLocal("i64_test", int64, %38)
    %39 = IntLiteral(9223372036854775808, int64)
    %40 = UnaryOp("-", %39)
    DeclareLocal("i64_negative", int64, %40)
    %41 = LoadVar("i64_test") -> int64
    Call(println, [%41], ["borrow"])
    %42 = LoadVar("i64_negative") -> int64
    Call(println, [%42], ["borrow"])
    %43 = LoadVar("i64_test") -> int64
    %44 = IntLiteral(1000, int64)
    %45 = BinaryOp("/", %43, %44)
    Call(println, [%45], ["borrow"])
    %46 = StringLiteral("--- uint8 ---", string)
    Call(println, [%46], ["borrow"])
    %47 = IntLiteral(0, uint8)
    DeclareLocal("u8_min", uint8, %47)
    %48 = IntLiteral(255, uint8)
    DeclareLocal("u8_max", uint8, %48)
    %49 = IntLiteral(128, uint8)
    DeclareLocal("u8_test", uint8, %49)
    %50 = LoadVar("u8_min") -> uint8
    Call(println, [%50], ["borrow"])
    %51 = LoadVar("u8_max") -> uint8
    Call(println, [%51], ["borrow"])
    %52 = LoadVar("u8_test") -> uint8
    Call(println, [%52], ["borrow"])
    %53 = LoadVar("u8_max") -> uint8
    %54 = IntLiteral(1, uint8)
    %55 = BinaryOp("+", %53, %54)
    Call(println, [%55], ["borrow"])
    %56 = StringLiteral("--- uint16 ---", string)
    Call(println, [%56], ["borrow"])
    %57 = IntLiteral(65535, uint16)
    DeclareLocal("u16_max", uint16, %57)
    %58 = IntLiteral(30000, uint16)
    DeclareLocal("u16_test", uint16, %58)
    %59 = LoadVar("u16_max") -> uint16
    Call(println, [%59], ["borrow"])
    %60 = LoadVar("u16_test") -> uint16
    Call(println, [%60], ["borrow"])
    %61 = LoadVar("u16_test") -> uint16
    %62 = IntLiteral(1000, uint16)
    %63 = BinaryOp("+", %61, %62)
    Call(println, [%63], ["borrow"])
    %64 = StringLiteral("--- uint32 ---", string)
    Call(println, [%64], ["borrow"])
    %65 = IntLiteral(4294967295, uint32)
    DeclareLocal("u32_max", uint32, %65)
    %66 = IntLiteral(1000000, uint32)
    DeclareLocal("u32_test", uint32, %66)
    %67 = LoadVar("u32_max") -> uint32
    Call(println, [%67], ["borrow"])
    %68 = LoadVar("u32_test") -> uint32
    Call(println, [%68], ["borrow"])
    %69 = LoadVar("u32_test") -> uint32
    %70 = IntLiteral(2, uint32)
    %71 = BinaryOp("*", %69, %70)
    Call(println, [%71], ["borrow"])
    %72 = StringLiteral("--- uint64 ---", string)
    Call(println, [%72], ["borrow"])
    %73 = IntLiteral(18446744073709551615, uint64)
    DeclareLocal("u64_max", uint64, %73)
    %74 = IntLiteral(1000000000, uint64)
    DeclareLocal("u64_test", uint64, %74)
    %75 = LoadVar("u64_max") -> uint64
    Call(println, [%75], ["borrow"])
    %76 = LoadVar("u64_test") -> uint64
    Call(println, [%76], ["borrow"])
    %77 = LoadVar("u64_test") -> uint64
    %78 = IntLiteral(10, uint64)
    %79 = BinaryOp("*", %77, %78)
    Call(println, [%79], ["borrow"])
    %80 = StringLiteral("--- float32 ---", string)
    Call(println, [%80], ["borrow"])
    %81 = FloatLiteral(3.14159, float32)
    DeclareLocal("f32_pi", float32, %81)
    %82 = FloatLiteral(2.71828, float32)
    DeclareLocal("f32_e", float32, %82)
    %83 = FloatLiteral(0.0, float32)
    DeclareLocal("f32_zero", float32, %83)
    %84 = FloatLiteral(42.5, float32)
    %85 = UnaryOp("-", %84)
    DeclareLocal("f32_negative", float32, %85)
    %86 = LoadVar("f32_pi") -> float32
    Call(println, [%86], ["borrow"])
    %87 = LoadVar("f32_e") -> float32
    Call(println, [%87], ["borrow"])
    %88 = LoadVar("f32_zero") -> float32
    Call(println, [%88], ["borrow"])
    %89 = LoadVar("f32_negative") -> float32
    Call(println, [%89], ["borrow"])
    %90 = LoadVar("f32_pi") -> float32
    %91 = FloatLiteral(2.0, float32)
    %92 = BinaryOp("*", %90, %91)
    Call(println, [%92], ["borrow"])
    %93 = LoadVar("f32_e") -> float32
    %94 = LoadVar("f32_pi") -> float32
    %95 = BinaryOp("+", %93, %94)
    Call(println, [%95], ["borrow"])
    %96 = StringLiteral("--- float64 ---", string)
    Call(println, [%96], ["borrow"])
    %97 = FloatLiteral(3.141592653589793, float64)
    DeclareLocal("f64_pi", float64, %97)
    %98 = FloatLiteral(2.718281828459045, float64)
    DeclareLocal("f64_e", float64, %98)
    %99 = FloatLiteral(1e100, float64)
    DeclareLocal("f64_large", float64, %99)
    %100 = FloatLiteral(1e-100, float64)
    DeclareLocal("f64_small", float64, %100)
    %101 = LoadVar("f64_pi") -> float64
    Call(println, [%101], ["borrow"])
    %102 = LoadVar("f64_e") -> float64
    Call(println, [%102], ["borrow"])
    %103 = LoadVar("f64_large") -> float64
    Call(println, [%103], ["borrow"])
    %104 = LoadVar("f64_small") -> float64
    Call(println, [%104], ["borrow"])
    %105 = LoadVar("f64_pi") -> float64
    %106 = LoadVar("f64_e") -> float64
    %107 = BinaryOp("*", %105, %106)
    Call(println, [%107], ["borrow"])
    %108 = StringLiteral("--- bool ---", string)
    Call(println, [%108], ["borrow"])
    %109 = BoolLiteral(true, bool)
    DeclareLocal("b_true", bool, %109)
    %110 = BoolLiteral(false, bool)
    DeclareLocal("b_false", bool, %110)
    %111 = LoadVar("b_true") -> bool
    Call(println, [%111], ["borrow"])
    %112 = LoadVar("b_false") -> bool
    Call(println, [%112], ["borrow"])
    %113 = StringLiteral("=== All numeric type tests passed ===", string)
    Call(println, [%113], ["borrow"])
    Return()
}

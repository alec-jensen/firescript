module array_operations_comprehensive

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

function sumArray(arr: int32[]) -> int32 {
  block_0:
    %0 = IntLiteral(0, int32)
    DeclareLocal("sum", int32, %0)
    %1 = LoadVar("arr") -> int32[]
    DeclareLocal("__arr_val", int32[], %1)
    %2 = IntLiteral(0, int32)
    DeclareLocal("__i_val", int32, %2)
    Jump(block_1)

  block_1:
    %3 = LoadVar("__i_val") -> int32
    %4 = LoadVar("__arr_val") -> int32[]
    %5 = Call(array_length, [%4], ["borrow"]) -> int32
    %6 = BinaryOp("<", %3, %5)
    Branch(%6, block_2, block_3)

  block_2:
    %7 = LoadVar("__arr_val") -> int32[]
    %8 = LoadVar("__i_val") -> int32
    %9 = IndexArray(%7, %8)
    DeclareLocal("val", int32, %9)
    %10 = LoadVar("sum") -> int32
    %11 = LoadVar("val") -> int32
    %12 = BinaryOp("+", %10, %11)
    StoreVar("sum", %12)
    Jump(block_4)

  block_3:
    %13 = LoadVar("sum") -> int32
    Return(%13)

  block_4:
    %14 = LoadVar("__i_val") -> int32
    %15 = IntLiteral(1, int32)
    %16 = BinaryOp("+", %14, %15)
    StoreVar("__i_val", %16)
    Jump(block_1)
}

function main() -> void {
  block_0:
    %0 = StringLiteral("=== Array Operation Tests ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- Array Basics ---", string)
    Call(println, [%1], ["borrow"])
    %2 = IntLiteral(1, int32)
    %3 = IntLiteral(2, int32)
    %4 = IntLiteral(3, int32)
    %5 = IntLiteral(4, int32)
    %6 = IntLiteral(5, int32)
    %7 = ArrayLiteral([%2, %3, %4, %5, %6], int32[5])
    DeclareLocal("arr1", int32[5], %7)
    %8 = LoadVar("arr1") -> int32[5]
    %9 = IntLiteral(0, int32)
    %10 = IndexArray(%8, %9)
    Call(println, [%10], ["borrow"])
    %11 = LoadVar("arr1") -> int32[5]
    %12 = IntLiteral(4, int32)
    %13 = IndexArray(%11, %12)
    Call(println, [%13], ["borrow"])
    %14 = IntLiteral(5, int32)
    Call(println, [%14], ["borrow"])
    %15 = LoadVar("arr1") -> int32[5]
    Drop(%15)
    %16 = StringLiteral("--- Empty Array ---", string)
    Call(println, [%16], ["borrow"])
    %17 = ArrayLiteral([], int32[0])
    DeclareLocal("empty", int32[0], %17)
    %18 = IntLiteral(0, int32)
    Call(println, [%18], ["borrow"])
    %19 = LoadVar("empty") -> int32[0]
    Drop(%19)
    %20 = StringLiteral("--- Different Type Arrays ---", string)
    Call(println, [%20], ["borrow"])
    %21 = IntLiteral(1, int8)
    %22 = IntLiteral(2, int8)
    %23 = IntLiteral(3, int8)
    %24 = ArrayLiteral([%21, %22, %23], int8[3])
    DeclareLocal("i8_arr", int8[3], %24)
    %25 = LoadVar("i8_arr") -> int8[3]
    %26 = IntLiteral(0, int32)
    %27 = IndexArray(%25, %26)
    Call(println, [%27], ["borrow"])
    %28 = IntLiteral(3, int32)
    Call(println, [%28], ["borrow"])
    %29 = LoadVar("i8_arr") -> int8[3]
    Drop(%29)
    %30 = IntLiteral(100, int64)
    %31 = IntLiteral(200, int64)
    %32 = IntLiteral(300, int64)
    %33 = ArrayLiteral([%30, %31, %32], int64[3])
    DeclareLocal("i64_arr", int64[3], %33)
    %34 = LoadVar("i64_arr") -> int64[3]
    %35 = IntLiteral(1, int32)
    %36 = IndexArray(%34, %35)
    Call(println, [%36], ["borrow"])
    %37 = LoadVar("i64_arr") -> int64[3]
    Drop(%37)
    %38 = FloatLiteral(1.1, float32)
    %39 = FloatLiteral(2.2, float32)
    %40 = FloatLiteral(3.3, float32)
    %41 = ArrayLiteral([%38, %39, %40], float32[3])
    DeclareLocal("f32_arr", float32[3], %41)
    %42 = LoadVar("f32_arr") -> float32[3]
    %43 = IntLiteral(0, int32)
    %44 = IndexArray(%42, %43)
    Call(println, [%44], ["borrow"])
    %45 = LoadVar("f32_arr") -> float32[3]
    %46 = IntLiteral(2, int32)
    %47 = IndexArray(%45, %46)
    Call(println, [%47], ["borrow"])
    %48 = LoadVar("f32_arr") -> float32[3]
    Drop(%48)
    %49 = FloatLiteral(1.111, float64)
    %50 = FloatLiteral(2.222, float64)
    %51 = FloatLiteral(3.333, float64)
    %52 = ArrayLiteral([%49, %50, %51], float64[3])
    DeclareLocal("f64_arr", float64[3], %52)
    %53 = LoadVar("f64_arr") -> float64[3]
    %54 = IntLiteral(1, int32)
    %55 = IndexArray(%53, %54)
    Call(println, [%55], ["borrow"])
    %56 = LoadVar("f64_arr") -> float64[3]
    Drop(%56)
    %57 = StringLiteral("hello", string)
    %58 = StringLiteral("world", string)
    %59 = StringLiteral("firescript", string)
    %60 = ArrayLiteral([%57, %58, %59], string[3])
    DeclareLocal("str_arr", string[3], %60)
    %61 = LoadVar("str_arr") -> string[3]
    %62 = IntLiteral(0, int32)
    %63 = IndexArray(%61, %62)
    Call(println, [%63], ["borrow"])
    %64 = LoadVar("str_arr") -> string[3]
    %65 = IntLiteral(2, int32)
    %66 = IndexArray(%64, %65)
    Call(println, [%66], ["borrow"])
    %67 = IntLiteral(3, int32)
    Call(println, [%67], ["borrow"])
    %68 = LoadVar("str_arr") -> string[3]
    Drop(%68)
    %69 = BoolLiteral(true, bool)
    %70 = BoolLiteral(false, bool)
    %71 = BoolLiteral(true, bool)
    %72 = BoolLiteral(true, bool)
    %73 = ArrayLiteral([%69, %70, %71, %72], bool[4])
    DeclareLocal("bool_arr", bool[4], %73)
    %74 = LoadVar("bool_arr") -> bool[4]
    %75 = IntLiteral(0, int32)
    %76 = IndexArray(%74, %75)
    Call(println, [%76], ["borrow"])
    %77 = LoadVar("bool_arr") -> bool[4]
    %78 = IntLiteral(1, int32)
    %79 = IndexArray(%77, %78)
    Call(println, [%79], ["borrow"])
    %80 = IntLiteral(4, int32)
    Call(println, [%80], ["borrow"])
    %81 = LoadVar("bool_arr") -> bool[4]
    Drop(%81)
    %82 = StringLiteral("--- Array Modification ---", string)
    Call(println, [%82], ["borrow"])
    %83 = IntLiteral(10, int32)
    %84 = IntLiteral(20, int32)
    %85 = IntLiteral(30, int32)
    %86 = ArrayLiteral([%83, %84, %85], int32[3])
    DeclareLocal("mutable", int32[3], %86)
    %87 = LoadVar("mutable") -> int32[3]
    %88 = IntLiteral(1, int32)
    %89 = IndexArray(%87, %88)
    Call(println, [%89], ["borrow"])
    %90 = IntLiteral(99, int32)
    %91 = LoadVar("mutable") -> int32[3]
    %92 = IntLiteral(1, int32)
    StoreArray(%91, %92, %90)
    %93 = LoadVar("mutable") -> int32[3]
    %94 = IntLiteral(1, int32)
    %95 = IndexArray(%93, %94)
    Call(println, [%95], ["borrow"])
    %96 = LoadVar("mutable") -> int32[3]
    Drop(%96)
    %97 = StringLiteral("--- Array Iteration (for-in) ---", string)
    Call(println, [%97], ["borrow"])
    %98 = IntLiteral(5, int32)
    %99 = IntLiteral(10, int32)
    %100 = IntLiteral(15, int32)
    %101 = IntLiteral(20, int32)
    %102 = ArrayLiteral([%98, %99, %100, %101], int32[4])
    DeclareLocal("nums", int32[4], %102)
    %103 = LoadVar("nums") -> int32[4]
    DeclareLocal("__arr_n", int32[4], %103)
    %104 = IntLiteral(0, int32)
    DeclareLocal("__i_n", int32, %104)
    Jump(block_1)

  block_1:
    %105 = LoadVar("__i_n") -> int32
    %106 = IntLiteral(4, int32)
    %107 = BinaryOp("<", %105, %106)
    Branch(%107, block_2, block_3)

  block_2:
    %108 = LoadVar("__arr_n") -> int32[4]
    %109 = LoadVar("__i_n") -> int32
    %110 = IndexArray(%108, %109)
    DeclareLocal("n", int32, %110)
    %111 = LoadVar("n") -> int32
    Call(println, [%111], ["borrow"])
    Jump(block_4)

  block_3:
    %112 = LoadVar("nums") -> int32[4]
    Drop(%112)
    %113 = StringLiteral("--- Array Iteration (C-style for) ---", string)
    Call(println, [%113], ["borrow"])
    %114 = IntLiteral(100, int32)
    %115 = IntLiteral(200, int32)
    %116 = IntLiteral(300, int32)
    %117 = ArrayLiteral([%114, %115, %116], int32[3])
    DeclareLocal("values", int32[3], %117)
    %118 = IntLiteral(0, int32)
    DeclareLocal("i", int32, %118)
    Jump(block_5)

  block_4:
    %119 = LoadVar("__i_n") -> int32
    %120 = IntLiteral(1, int32)
    %121 = BinaryOp("+", %119, %120)
    StoreVar("__i_n", %121)
    Jump(block_1)

  block_5:
    %122 = LoadVar("i") -> int32
    %123 = IntLiteral(3, int32)
    %124 = BinaryOp("<", %122, %123)
    Branch(%124, block_6, block_8)

  block_6:
    %125 = LoadVar("values") -> int32[3]
    %126 = LoadVar("i") -> int32
    %127 = IndexArray(%125, %126)
    Call(println, [%127], ["borrow"])
    Jump(block_7)

  block_7:
    %128 = LoadVar("i") -> int32
    %129 = IntLiteral(1, int32)
    %130 = BinaryOp("+", %128, %129)
    StoreVar("i", %130)
    Jump(block_5)

  block_8:
    %131 = LoadVar("values") -> int32[3]
    Drop(%131)
    %132 = StringLiteral("--- Array Iteration (while) ---", string)
    Call(println, [%132], ["borrow"])
    %133 = IntLiteral(7, int32)
    %134 = IntLiteral(14, int32)
    %135 = IntLiteral(21, int32)
    %136 = IntLiteral(28, int32)
    %137 = ArrayLiteral([%133, %134, %135, %136], int32[4])
    DeclareLocal("data", int32[4], %137)
    %138 = IntLiteral(0, int32)
    DeclareLocal("idx", int32, %138)
    Jump(block_9)

  block_9:
    %139 = LoadVar("idx") -> int32
    %140 = IntLiteral(4, int32)
    %141 = BinaryOp("<", %139, %140)
    Branch(%141, block_10, block_11)

  block_10:
    %142 = LoadVar("data") -> int32[4]
    %143 = LoadVar("idx") -> int32
    %144 = IndexArray(%142, %143)
    Call(println, [%144], ["borrow"])
    %145 = LoadVar("idx") -> int32
    %146 = IntLiteral(1, int32)
    %147 = BinaryOp("+", %145, %146)
    StoreVar("idx", %147)
    Jump(block_9)

  block_11:
    %148 = LoadVar("data") -> int32[4]
    Drop(%148)
    %149 = StringLiteral("--- Array in Function ---", string)
    Call(println, [%149], ["borrow"])
    %150 = IntLiteral(1, int32)
    %151 = IntLiteral(2, int32)
    %152 = IntLiteral(3, int32)
    %153 = IntLiteral(4, int32)
    %154 = IntLiteral(5, int32)
    %155 = ArrayLiteral([%150, %151, %152, %153, %154], int32[5])
    DeclareLocal("to_sum", int32[5], %155)
    %156 = LoadVar("to_sum") -> int32[5]
    %157 = Call(sumArray, [%156], ["own"]) -> int32
    DeclareLocal("total", int32, %157)
    %158 = LoadVar("total") -> int32
    Call(println, [%158], ["borrow"])
    %159 = StringLiteral("--- Large Array ---", string)
    Call(println, [%159], ["borrow"])
    %160 = IntLiteral(1, int32)
    %161 = IntLiteral(2, int32)
    %162 = IntLiteral(3, int32)
    %163 = IntLiteral(4, int32)
    %164 = IntLiteral(5, int32)
    %165 = IntLiteral(6, int32)
    %166 = IntLiteral(7, int32)
    %167 = IntLiteral(8, int32)
    %168 = IntLiteral(9, int32)
    %169 = IntLiteral(10, int32)
    %170 = IntLiteral(11, int32)
    %171 = IntLiteral(12, int32)
    %172 = IntLiteral(13, int32)
    %173 = IntLiteral(14, int32)
    %174 = IntLiteral(15, int32)
    %175 = IntLiteral(16, int32)
    %176 = IntLiteral(17, int32)
    %177 = IntLiteral(18, int32)
    %178 = IntLiteral(19, int32)
    %179 = IntLiteral(20, int32)
    %180 = ArrayLiteral([%160, %161, %162, %163, %164, %165, %166, %167, %168, %169, %170, %171, %172, %173, %174, %175, %176, %177, %178, %179], int32[20])
    DeclareLocal("large", int32[20], %180)
    %181 = IntLiteral(20, int32)
    Call(println, [%181], ["borrow"])
    %182 = LoadVar("large") -> int32[20]
    %183 = IntLiteral(0, int32)
    %184 = IndexArray(%182, %183)
    Call(println, [%184], ["borrow"])
    %185 = LoadVar("large") -> int32[20]
    %186 = IntLiteral(19, int32)
    %187 = IndexArray(%185, %186)
    Call(println, [%187], ["borrow"])
    %188 = LoadVar("large") -> int32[20]
    Drop(%188)
    %189 = StringLiteral("--- Array Bounds ---", string)
    Call(println, [%189], ["borrow"])
    %190 = IntLiteral(99, int32)
    %191 = IntLiteral(88, int32)
    %192 = IntLiteral(77, int32)
    %193 = ArrayLiteral([%190, %191, %192], int32[3])
    DeclareLocal("bounds_test", int32[3], %193)
    %194 = LoadVar("bounds_test") -> int32[3]
    %195 = IntLiteral(0, int32)
    %196 = IndexArray(%194, %195)
    Call(println, [%196], ["borrow"])
    %197 = LoadVar("bounds_test") -> int32[3]
    %198 = IntLiteral(3, int32)
    %199 = IntLiteral(1, int32)
    %200 = BinaryOp("-", %198, %199)
    %201 = IndexArray(%197, %200)
    Call(println, [%201], ["borrow"])
    %202 = LoadVar("bounds_test") -> int32[3]
    Drop(%202)
    %203 = StringLiteral("=== All array operation tests passed ===", string)
    Call(println, [%203], ["borrow"])
    Return()
}

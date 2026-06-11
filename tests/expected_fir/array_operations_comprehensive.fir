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
    DeclareLocal("empty", int32[], %17)
    %18 = LoadVar("empty") -> int32[]
    %19 = Call(array_length, [%18], ["borrow"]) -> int32
    Call(println, [%19], ["borrow"])
    %20 = LoadVar("empty") -> int32[]
    Drop(%20)
    %21 = StringLiteral("--- Different Type Arrays ---", string)
    Call(println, [%21], ["borrow"])
    %22 = IntLiteral(1, int8)
    %23 = IntLiteral(2, int8)
    %24 = IntLiteral(3, int8)
    %25 = ArrayLiteral([%22, %23, %24], int8[3])
    DeclareLocal("i8_arr", int8[3], %25)
    %26 = LoadVar("i8_arr") -> int8[3]
    %27 = IntLiteral(0, int32)
    %28 = IndexArray(%26, %27)
    Call(println, [%28], ["borrow"])
    %29 = IntLiteral(3, int32)
    Call(println, [%29], ["borrow"])
    %30 = LoadVar("i8_arr") -> int8[3]
    Drop(%30)
    %31 = IntLiteral(100, int64)
    %32 = IntLiteral(200, int64)
    %33 = IntLiteral(300, int64)
    %34 = ArrayLiteral([%31, %32, %33], int64[3])
    DeclareLocal("i64_arr", int64[3], %34)
    %35 = LoadVar("i64_arr") -> int64[3]
    %36 = IntLiteral(1, int32)
    %37 = IndexArray(%35, %36)
    Call(println, [%37], ["borrow"])
    %38 = LoadVar("i64_arr") -> int64[3]
    Drop(%38)
    %39 = FloatLiteral(1.1, float32)
    %40 = FloatLiteral(2.2, float32)
    %41 = FloatLiteral(3.3, float32)
    %42 = ArrayLiteral([%39, %40, %41], float32[3])
    DeclareLocal("f32_arr", float32[3], %42)
    %43 = LoadVar("f32_arr") -> float32[3]
    %44 = IntLiteral(0, int32)
    %45 = IndexArray(%43, %44)
    Call(println, [%45], ["borrow"])
    %46 = LoadVar("f32_arr") -> float32[3]
    %47 = IntLiteral(2, int32)
    %48 = IndexArray(%46, %47)
    Call(println, [%48], ["borrow"])
    %49 = LoadVar("f32_arr") -> float32[3]
    Drop(%49)
    %50 = FloatLiteral(1.111, float64)
    %51 = FloatLiteral(2.222, float64)
    %52 = FloatLiteral(3.333, float64)
    %53 = ArrayLiteral([%50, %51, %52], float64[3])
    DeclareLocal("f64_arr", float64[3], %53)
    %54 = LoadVar("f64_arr") -> float64[3]
    %55 = IntLiteral(1, int32)
    %56 = IndexArray(%54, %55)
    Call(println, [%56], ["borrow"])
    %57 = LoadVar("f64_arr") -> float64[3]
    Drop(%57)
    %58 = StringLiteral("hello", string)
    %59 = StringLiteral("world", string)
    %60 = StringLiteral("firescript", string)
    %61 = ArrayLiteral([%58, %59, %60], string[3])
    DeclareLocal("str_arr", string[3], %61)
    %62 = LoadVar("str_arr") -> string[3]
    %63 = IntLiteral(0, int32)
    %64 = IndexArray(%62, %63)
    Call(println, [%64], ["borrow"])
    %65 = LoadVar("str_arr") -> string[3]
    %66 = IntLiteral(2, int32)
    %67 = IndexArray(%65, %66)
    Call(println, [%67], ["borrow"])
    %68 = IntLiteral(3, int32)
    Call(println, [%68], ["borrow"])
    %69 = LoadVar("str_arr") -> string[3]
    Drop(%69)
    %70 = BoolLiteral(true, bool)
    %71 = BoolLiteral(false, bool)
    %72 = BoolLiteral(true, bool)
    %73 = BoolLiteral(true, bool)
    %74 = ArrayLiteral([%70, %71, %72, %73], bool[4])
    DeclareLocal("bool_arr", bool[4], %74)
    %75 = LoadVar("bool_arr") -> bool[4]
    %76 = IntLiteral(0, int32)
    %77 = IndexArray(%75, %76)
    Call(println, [%77], ["borrow"])
    %78 = LoadVar("bool_arr") -> bool[4]
    %79 = IntLiteral(1, int32)
    %80 = IndexArray(%78, %79)
    Call(println, [%80], ["borrow"])
    %81 = IntLiteral(4, int32)
    Call(println, [%81], ["borrow"])
    %82 = LoadVar("bool_arr") -> bool[4]
    Drop(%82)
    %83 = StringLiteral("--- Array Modification ---", string)
    Call(println, [%83], ["borrow"])
    %84 = IntLiteral(10, int32)
    %85 = IntLiteral(20, int32)
    %86 = IntLiteral(30, int32)
    %87 = ArrayLiteral([%84, %85, %86], int32[3])
    DeclareLocal("mutable", int32[3], %87)
    %88 = LoadVar("mutable") -> int32[3]
    %89 = IntLiteral(1, int32)
    %90 = IndexArray(%88, %89)
    Call(println, [%90], ["borrow"])
    %91 = IntLiteral(99, int32)
    %92 = LoadVar("mutable") -> int32[3]
    %93 = IntLiteral(1, int32)
    StoreArray(%92, %93, %91)
    %94 = LoadVar("mutable") -> int32[3]
    %95 = IntLiteral(1, int32)
    %96 = IndexArray(%94, %95)
    Call(println, [%96], ["borrow"])
    %97 = LoadVar("mutable") -> int32[3]
    Drop(%97)
    %98 = StringLiteral("--- Array Iteration (for-in) ---", string)
    Call(println, [%98], ["borrow"])
    %99 = IntLiteral(5, int32)
    %100 = IntLiteral(10, int32)
    %101 = IntLiteral(15, int32)
    %102 = IntLiteral(20, int32)
    %103 = ArrayLiteral([%99, %100, %101, %102], int32[4])
    DeclareLocal("nums", int32[4], %103)
    %104 = LoadVar("nums") -> int32[4]
    DeclareLocal("__arr_n", int32[4], %104)
    %105 = IntLiteral(0, int32)
    DeclareLocal("__i_n", int32, %105)
    Jump(block_1)

  block_1:
    %106 = LoadVar("__i_n") -> int32
    %107 = IntLiteral(4, int32)
    %108 = BinaryOp("<", %106, %107)
    Branch(%108, block_2, block_3)

  block_2:
    %109 = LoadVar("__arr_n") -> int32[4]
    %110 = LoadVar("__i_n") -> int32
    %111 = IndexArray(%109, %110)
    DeclareLocal("n", int32, %111)
    %112 = LoadVar("n") -> int32
    Call(println, [%112], ["borrow"])
    Jump(block_4)

  block_3:
    %113 = LoadVar("nums") -> int32[4]
    Drop(%113)
    %114 = StringLiteral("--- Array Iteration (C-style for) ---", string)
    Call(println, [%114], ["borrow"])
    %115 = IntLiteral(100, int32)
    %116 = IntLiteral(200, int32)
    %117 = IntLiteral(300, int32)
    %118 = ArrayLiteral([%115, %116, %117], int32[3])
    DeclareLocal("values", int32[3], %118)
    %119 = IntLiteral(0, int32)
    DeclareLocal("i", int32, %119)
    Jump(block_5)

  block_4:
    %120 = LoadVar("__i_n") -> int32
    %121 = IntLiteral(1, int32)
    %122 = BinaryOp("+", %120, %121)
    StoreVar("__i_n", %122)
    Jump(block_1)

  block_5:
    %123 = LoadVar("i") -> int32
    %124 = IntLiteral(3, int32)
    %125 = BinaryOp("<", %123, %124)
    Branch(%125, block_6, block_8)

  block_6:
    %126 = LoadVar("values") -> int32[3]
    %127 = LoadVar("i") -> int32
    %128 = IndexArray(%126, %127)
    Call(println, [%128], ["borrow"])
    Jump(block_7)

  block_7:
    %129 = LoadVar("i") -> int32
    %130 = IntLiteral(1, int32)
    %131 = BinaryOp("+", %129, %130)
    StoreVar("i", %131)
    Jump(block_5)

  block_8:
    %132 = LoadVar("values") -> int32[3]
    Drop(%132)
    %133 = StringLiteral("--- Array Iteration (while) ---", string)
    Call(println, [%133], ["borrow"])
    %134 = IntLiteral(7, int32)
    %135 = IntLiteral(14, int32)
    %136 = IntLiteral(21, int32)
    %137 = IntLiteral(28, int32)
    %138 = ArrayLiteral([%134, %135, %136, %137], int32[4])
    DeclareLocal("data", int32[4], %138)
    %139 = IntLiteral(0, int32)
    DeclareLocal("idx", int32, %139)
    Jump(block_9)

  block_9:
    %140 = LoadVar("idx") -> int32
    %141 = IntLiteral(4, int32)
    %142 = BinaryOp("<", %140, %141)
    Branch(%142, block_10, block_11)

  block_10:
    %143 = LoadVar("data") -> int32[4]
    %144 = LoadVar("idx") -> int32
    %145 = IndexArray(%143, %144)
    Call(println, [%145], ["borrow"])
    %146 = LoadVar("idx") -> int32
    %147 = IntLiteral(1, int32)
    %148 = BinaryOp("+", %146, %147)
    StoreVar("idx", %148)
    Jump(block_9)

  block_11:
    %149 = LoadVar("data") -> int32[4]
    Drop(%149)
    %150 = StringLiteral("--- Array in Function ---", string)
    Call(println, [%150], ["borrow"])
    %151 = IntLiteral(1, int32)
    %152 = IntLiteral(2, int32)
    %153 = IntLiteral(3, int32)
    %154 = IntLiteral(4, int32)
    %155 = IntLiteral(5, int32)
    %156 = ArrayLiteral([%151, %152, %153, %154, %155], int32[5])
    DeclareLocal("to_sum", int32[5], %156)
    %157 = LoadVar("to_sum") -> int32[5]
    %158 = Call(sumArray, [%157], ["own"]) -> int32
    DeclareLocal("total", int32, %158)
    %159 = LoadVar("total") -> int32
    Call(println, [%159], ["borrow"])
    %160 = StringLiteral("--- Large Array ---", string)
    Call(println, [%160], ["borrow"])
    %161 = IntLiteral(1, int32)
    %162 = IntLiteral(2, int32)
    %163 = IntLiteral(3, int32)
    %164 = IntLiteral(4, int32)
    %165 = IntLiteral(5, int32)
    %166 = IntLiteral(6, int32)
    %167 = IntLiteral(7, int32)
    %168 = IntLiteral(8, int32)
    %169 = IntLiteral(9, int32)
    %170 = IntLiteral(10, int32)
    %171 = IntLiteral(11, int32)
    %172 = IntLiteral(12, int32)
    %173 = IntLiteral(13, int32)
    %174 = IntLiteral(14, int32)
    %175 = IntLiteral(15, int32)
    %176 = IntLiteral(16, int32)
    %177 = IntLiteral(17, int32)
    %178 = IntLiteral(18, int32)
    %179 = IntLiteral(19, int32)
    %180 = IntLiteral(20, int32)
    %181 = ArrayLiteral([%161, %162, %163, %164, %165, %166, %167, %168, %169, %170, %171, %172, %173, %174, %175, %176, %177, %178, %179, %180], int32[20])
    DeclareLocal("large", int32[20], %181)
    %182 = IntLiteral(20, int32)
    Call(println, [%182], ["borrow"])
    %183 = LoadVar("large") -> int32[20]
    %184 = IntLiteral(0, int32)
    %185 = IndexArray(%183, %184)
    Call(println, [%185], ["borrow"])
    %186 = LoadVar("large") -> int32[20]
    %187 = IntLiteral(19, int32)
    %188 = IndexArray(%186, %187)
    Call(println, [%188], ["borrow"])
    %189 = LoadVar("large") -> int32[20]
    Drop(%189)
    %190 = StringLiteral("--- Array Bounds ---", string)
    Call(println, [%190], ["borrow"])
    %191 = IntLiteral(99, int32)
    %192 = IntLiteral(88, int32)
    %193 = IntLiteral(77, int32)
    %194 = ArrayLiteral([%191, %192, %193], int32[3])
    DeclareLocal("bounds_test", int32[3], %194)
    %195 = LoadVar("bounds_test") -> int32[3]
    %196 = IntLiteral(0, int32)
    %197 = IndexArray(%195, %196)
    Call(println, [%197], ["borrow"])
    %198 = LoadVar("bounds_test") -> int32[3]
    %199 = IntLiteral(3, int32)
    %200 = IntLiteral(1, int32)
    %201 = BinaryOp("-", %199, %200)
    %202 = IndexArray(%198, %201)
    Call(println, [%202], ["borrow"])
    %203 = LoadVar("bounds_test") -> int32[3]
    Drop(%203)
    %204 = StringLiteral("=== All array operation tests passed ===", string)
    Call(println, [%204], ["borrow"])
    Return()
}

module operator_precedence

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
    %0 = IntLiteral(2, int32)
    %1 = IntLiteral(3, int32)
    %2 = IntLiteral(4, int32)
    %3 = BinaryOp("*", %1, %2)
    %4 = BinaryOp("+", %0, %3)
    Call(println, [%4], ["borrow"])
    %5 = IntLiteral(10, int32)
    %6 = IntLiteral(2, int32)
    %7 = IntLiteral(3, int32)
    %8 = BinaryOp("*", %6, %7)
    %9 = BinaryOp("-", %5, %8)
    Call(println, [%9], ["borrow"])
    %10 = IntLiteral(10, int32)
    %11 = IntLiteral(2, int32)
    %12 = BinaryOp("/", %10, %11)
    %13 = IntLiteral(3, int32)
    %14 = BinaryOp("+", %12, %13)
    Call(println, [%14], ["borrow"])
    %15 = IntLiteral(10, int32)
    %16 = IntLiteral(3, int32)
    %17 = BinaryOp("%", %15, %16)
    %18 = IntLiteral(1, int32)
    %19 = BinaryOp("+", %17, %18)
    Call(println, [%19], ["borrow"])
    %20 = IntLiteral(2, int32)
    %21 = IntLiteral(3, int32)
    %22 = IntLiteral(2, int32)
    %23 = BinaryOp("**", %21, %22)
    %24 = BinaryOp("*", %20, %23)
    Call(println, [%24], ["borrow"])
    %25 = IntLiteral(4, int32)
    %26 = IntLiteral(2, int32)
    %27 = IntLiteral(2, int32)
    %28 = BinaryOp("**", %26, %27)
    %29 = BinaryOp("/", %25, %28)
    Call(println, [%29], ["borrow"])
    %30 = IntLiteral(10, int32)
    %31 = IntLiteral(2, int32)
    %32 = IntLiteral(3, int32)
    %33 = BinaryOp("**", %31, %32)
    %34 = BinaryOp("-", %30, %33)
    Call(println, [%34], ["borrow"])
    %35 = IntLiteral(2, int32)
    %36 = UnaryOp("-", %35)
    %37 = IntLiteral(5, int32)
    %38 = BinaryOp("+", %36, %37)
    Call(println, [%38], ["borrow"])
    %39 = IntLiteral(3, int32)
    %40 = UnaryOp("-", %39)
    %41 = IntLiteral(3, int32)
    %42 = UnaryOp("-", %41)
    %43 = BinaryOp("*", %40, %42)
    Call(println, [%43], ["borrow"])
    %44 = IntLiteral(2, int32)
    %45 = IntLiteral(3, int32)
    %46 = BinaryOp("+", %44, %45)
    %47 = IntLiteral(4, int32)
    %48 = BinaryOp(">", %46, %47)
    DeclareLocal("r1", bool, %48)
    %49 = IntLiteral(2, int32)
    %50 = IntLiteral(3, int32)
    %51 = BinaryOp("+", %49, %50)
    %52 = IntLiteral(4, int32)
    %53 = BinaryOp("<", %51, %52)
    DeclareLocal("r2", bool, %53)
    %54 = IntLiteral(2, int32)
    %55 = IntLiteral(3, int32)
    %56 = BinaryOp("*", %54, %55)
    %57 = IntLiteral(6, int32)
    %58 = BinaryOp("==", %56, %57)
    DeclareLocal("r3", bool, %58)
    %59 = IntLiteral(10, int32)
    %60 = IntLiteral(4, int32)
    %61 = BinaryOp("-", %59, %60)
    %62 = IntLiteral(7, int32)
    %63 = BinaryOp("!=", %61, %62)
    DeclareLocal("r4", bool, %63)
    %64 = LoadVar("r1") -> bool
    Call(println, [%64], ["borrow"])
    %65 = LoadVar("r2") -> bool
    Call(println, [%65], ["borrow"])
    %66 = LoadVar("r3") -> bool
    Call(println, [%66], ["borrow"])
    %67 = LoadVar("r4") -> bool
    Call(println, [%67], ["borrow"])
    %68 = BoolLiteral(true, bool)
    DeclareLocal("__sc_1_85", bool, %68)
    %69 = LoadVar("__sc_1_85") -> bool
    Branch(%69, block_2, block_1)

  block_1:
    %70 = BoolLiteral(false, bool)
    DeclareLocal("__sc_3_0", bool, %70)
    %71 = LoadVar("__sc_3_0") -> bool
    Branch(%71, block_3, block_4)

  block_2:
    %72 = LoadVar("__sc_1_85") -> bool
    DeclareLocal("r5", bool, %72)
    %73 = BoolLiteral(false, bool)
    DeclareLocal("__sc_5_2", bool, %73)
    %74 = LoadVar("__sc_5_2") -> bool
    Branch(%74, block_5, block_6)

  block_3:
    %75 = BoolLiteral(false, bool)
    StoreVar("__sc_3_0", %75)
    Jump(block_4)

  block_4:
    %76 = LoadVar("__sc_3_0") -> bool
    StoreVar("__sc_1_85", %76)
    Jump(block_2)

  block_5:
    %77 = BoolLiteral(true, bool)
    StoreVar("__sc_5_2", %77)
    Jump(block_6)

  block_6:
    %78 = LoadVar("__sc_5_2") -> bool
    DeclareLocal("__sc_5_2", bool, %78)
    %79 = LoadVar("__sc_5_2") -> bool
    Branch(%79, block_8, block_7)

  block_7:
    %80 = BoolLiteral(true, bool)
    StoreVar("__sc_5_2", %80)
    Jump(block_8)

  block_8:
    %81 = LoadVar("__sc_5_2") -> bool
    DeclareLocal("r6", bool, %81)
    %82 = BoolLiteral(false, bool)
    DeclareLocal("__sc_9_2", bool, %82)
    %83 = LoadVar("__sc_9_2") -> bool
    Branch(%83, block_9, block_10)

  block_9:
    %84 = BoolLiteral(false, bool)
    StoreVar("__sc_9_2", %84)
    Jump(block_10)

  block_10:
    %85 = LoadVar("__sc_9_2") -> bool
    DeclareLocal("__sc_9_2", bool, %85)
    %86 = LoadVar("__sc_9_2") -> bool
    Branch(%86, block_12, block_11)

  block_11:
    %87 = BoolLiteral(false, bool)
    StoreVar("__sc_9_2", %87)
    Jump(block_12)

  block_12:
    %88 = LoadVar("__sc_9_2") -> bool
    DeclareLocal("r7", bool, %88)
    %89 = LoadVar("r5") -> bool
    Call(println, [%89], ["borrow"])
    %90 = LoadVar("r6") -> bool
    Call(println, [%90], ["borrow"])
    %91 = LoadVar("r7") -> bool
    Call(println, [%91], ["borrow"])
    %92 = IntLiteral(4, int32)
    DeclareLocal("a", int32, %92)
    %93 = IntLiteral(2, int32)
    DeclareLocal("b", int32, %93)
    %94 = IntLiteral(3, int32)
    DeclareLocal("c", int32, %94)
    %95 = LoadVar("a") -> int32
    %96 = LoadVar("b") -> int32
    %97 = LoadVar("c") -> int32
    %98 = BinaryOp("*", %96, %97)
    %99 = BinaryOp("+", %95, %98)
    %100 = LoadVar("a") -> int32
    %101 = LoadVar("b") -> int32
    %102 = BinaryOp("*", %100, %101)
    %103 = LoadVar("c") -> int32
    %104 = BinaryOp("+", %102, %103)
    %105 = BinaryOp(">", %99, %104)
    DeclareLocal("r8", bool, %105)
    %106 = LoadVar("a") -> int32
    %107 = LoadVar("b") -> int32
    %108 = BinaryOp("*", %106, %107)
    %109 = LoadVar("c") -> int32
    %110 = BinaryOp("+", %108, %109)
    %111 = LoadVar("a") -> int32
    %112 = LoadVar("b") -> int32
    %113 = BinaryOp("+", %111, %112)
    %114 = LoadVar("c") -> int32
    %115 = BinaryOp("+", %113, %114)
    %116 = BinaryOp("==", %110, %115)
    DeclareLocal("r9", bool, %116)
    %117 = LoadVar("r8") -> bool
    Call(println, [%117], ["borrow"])
    %118 = LoadVar("r9") -> bool
    Call(println, [%118], ["borrow"])
    %119 = IntLiteral(2, int32)
    %120 = IntLiteral(3, int32)
    %121 = BinaryOp("+", %119, %120)
    %122 = IntLiteral(4, int32)
    %123 = BinaryOp("*", %121, %122)
    Call(println, [%123], ["borrow"])
    %124 = IntLiteral(2, int32)
    %125 = IntLiteral(3, int32)
    %126 = IntLiteral(4, int32)
    %127 = BinaryOp("+", %125, %126)
    %128 = BinaryOp("*", %124, %127)
    Call(println, [%128], ["borrow"])
    %129 = IntLiteral(10, int32)
    %130 = IntLiteral(2, int32)
    %131 = BinaryOp("-", %129, %130)
    %132 = IntLiteral(2, int32)
    %133 = BinaryOp("**", %131, %132)
    Call(println, [%133], ["borrow"])
    Return()
}

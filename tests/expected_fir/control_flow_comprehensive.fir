module control_flow_comprehensive

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
    %0 = StringLiteral("=== Control Flow Tests ===", string)
    Call(println, [%0], ["borrow"])
    %1 = StringLiteral("--- Simple if ---", string)
    Call(println, [%1], ["borrow"])
    %2 = IntLiteral(10, int32)
    DeclareLocal("x", int32, %2)
    %3 = LoadVar("x") -> int32
    %4 = IntLiteral(5, int32)
    %5 = BinaryOp(">", %3, %4)
    Branch(%5, block_2, block_1)

  block_1:
    %6 = StringLiteral("--- if-else ---", string)
    Call(println, [%6], ["borrow"])
    %7 = IntLiteral(75, int32)
    DeclareLocal("score", int32, %7)
    %8 = LoadVar("score") -> int32
    %9 = IntLiteral(70, int32)
    %10 = BinaryOp(">=", %8, %9)
    Branch(%10, block_4, block_5)

  block_2:
    %11 = StringLiteral("x is greater than 5", string)
    Call(println, [%11], ["borrow"])
    Jump(block_1)

  block_3:
    %12 = StringLiteral("--- if-else if-else ---", string)
    Call(println, [%12], ["borrow"])
    %13 = IntLiteral(85, int32)
    DeclareLocal("grade", int32, %13)
    %14 = LoadVar("grade") -> int32
    %15 = IntLiteral(90, int32)
    %16 = BinaryOp(">=", %14, %15)
    Branch(%16, block_7, block_8)

  block_4:
    %17 = StringLiteral("Pass", string)
    Call(println, [%17], ["borrow"])
    Jump(block_3)

  block_5:
    %18 = StringLiteral("Fail", string)
    Call(println, [%18], ["borrow"])
    Jump(block_3)

  block_6:
    %19 = StringLiteral("--- Nested if ---", string)
    Call(println, [%19], ["borrow"])
    %20 = IntLiteral(25, int32)
    DeclareLocal("age", int32, %20)
    %21 = BoolLiteral(true, bool)
    DeclareLocal("hasLicense", bool, %21)
    %22 = LoadVar("age") -> int32
    %23 = IntLiteral(18, int32)
    %24 = BinaryOp(">=", %22, %23)
    Branch(%24, block_19, block_20)

  block_7:
    %25 = StringLiteral("A", string)
    Call(println, [%25], ["borrow"])
    Jump(block_6)

  block_8:
    %26 = LoadVar("grade") -> int32
    %27 = IntLiteral(80, int32)
    %28 = BinaryOp(">=", %26, %27)
    Branch(%28, block_10, block_11)

  block_9:
    Jump(block_6)

  block_10:
    %29 = StringLiteral("B", string)
    Call(println, [%29], ["borrow"])
    Jump(block_9)

  block_11:
    %30 = LoadVar("grade") -> int32
    %31 = IntLiteral(70, int32)
    %32 = BinaryOp(">=", %30, %31)
    Branch(%32, block_13, block_14)

  block_12:
    Jump(block_9)

  block_13:
    %33 = StringLiteral("C", string)
    Call(println, [%33], ["borrow"])
    Jump(block_12)

  block_14:
    %34 = LoadVar("grade") -> int32
    %35 = IntLiteral(60, int32)
    %36 = BinaryOp(">=", %34, %35)
    Branch(%36, block_16, block_17)

  block_15:
    Jump(block_12)

  block_16:
    %37 = StringLiteral("D", string)
    Call(println, [%37], ["borrow"])
    Jump(block_15)

  block_17:
    %38 = StringLiteral("F", string)
    Call(println, [%38], ["borrow"])
    Jump(block_15)

  block_18:
    %39 = StringLiteral("--- While loop ---", string)
    Call(println, [%39], ["borrow"])
    %40 = IntLiteral(0, int32)
    DeclareLocal("count", int32, %40)
    Jump(block_24)

  block_19:
    %41 = LoadVar("hasLicense") -> bool
    Branch(%41, block_22, block_23)

  block_20:
    %42 = StringLiteral("Cannot drive - too young", string)
    Call(println, [%42], ["borrow"])
    Jump(block_18)

  block_21:
    Jump(block_18)

  block_22:
    %43 = StringLiteral("Can drive", string)
    Call(println, [%43], ["borrow"])
    Jump(block_21)

  block_23:
    %44 = StringLiteral("Cannot drive - no license", string)
    Call(println, [%44], ["borrow"])
    Jump(block_21)

  block_24:
    %45 = LoadVar("count") -> int32
    %46 = IntLiteral(5, int32)
    %47 = BinaryOp("<", %45, %46)
    Branch(%47, block_25, block_26)

  block_25:
    %48 = LoadVar("count") -> int32
    Call(println, [%48], ["borrow"])
    %49 = LoadVar("count") -> int32
    %50 = IntLiteral(1, int32)
    %51 = BinaryOp("+", %49, %50)
    StoreVar("count", %51)
    Jump(block_24)

  block_26:
    %52 = StringLiteral("--- While with break ---", string)
    Call(println, [%52], ["borrow"])
    %53 = IntLiteral(0, int32)
    DeclareLocal("i", int32, %53)
    Jump(block_27)

  block_27:
    %54 = LoadVar("i") -> int32
    %55 = IntLiteral(10, int32)
    %56 = BinaryOp("<", %54, %55)
    Branch(%56, block_28, block_29)

  block_28:
    %57 = LoadVar("i") -> int32
    %58 = IntLiteral(5, int32)
    %59 = BinaryOp("==", %57, %58)
    Branch(%59, block_31, block_30)

  block_29:
    %60 = StringLiteral("--- While with continue ---", string)
    Call(println, [%60], ["borrow"])
    %61 = IntLiteral(0, int32)
    DeclareLocal("j", int32, %61)
    Jump(block_32)

  block_30:
    %62 = LoadVar("i") -> int32
    Call(println, [%62], ["borrow"])
    %63 = LoadVar("i") -> int32
    %64 = IntLiteral(1, int32)
    %65 = BinaryOp("+", %63, %64)
    StoreVar("i", %65)
    Jump(block_27)

  block_31:
    Jump(block_29)

  block_32:
    %66 = LoadVar("j") -> int32
    %67 = IntLiteral(5, int32)
    %68 = BinaryOp("<", %66, %67)
    Branch(%68, block_33, block_34)

  block_33:
    %69 = LoadVar("j") -> int32
    %70 = IntLiteral(1, int32)
    %71 = BinaryOp("+", %69, %70)
    StoreVar("j", %71)
    %72 = LoadVar("j") -> int32
    %73 = IntLiteral(3, int32)
    %74 = BinaryOp("==", %72, %73)
    Branch(%74, block_36, block_35)

  block_34:
    %75 = StringLiteral("--- Nested while ---", string)
    Call(println, [%75], ["borrow"])
    %76 = IntLiteral(0, int32)
    DeclareLocal("outer", int32, %76)
    Jump(block_37)

  block_35:
    %77 = LoadVar("j") -> int32
    Call(println, [%77], ["borrow"])
    Jump(block_32)

  block_36:
    Jump(block_32)

  block_37:
    %78 = LoadVar("outer") -> int32
    %79 = IntLiteral(3, int32)
    %80 = BinaryOp("<", %78, %79)
    Branch(%80, block_38, block_39)

  block_38:
    %81 = IntLiteral(0, int32)
    DeclareLocal("inner", int32, %81)
    Jump(block_40)

  block_39:
    %82 = StringLiteral("--- C-style for ---", string)
    Call(println, [%82], ["borrow"])
    %83 = IntLiteral(0, int32)
    DeclareLocal("k", int32, %83)
    Jump(block_43)

  block_40:
    %84 = LoadVar("inner") -> int32
    %85 = IntLiteral(2, int32)
    %86 = BinaryOp("<", %84, %85)
    Branch(%86, block_41, block_42)

  block_41:
    %87 = LoadVar("outer") -> int32
    %88 = IntLiteral(10, int32)
    %89 = BinaryOp("*", %87, %88)
    %90 = LoadVar("inner") -> int32
    %91 = BinaryOp("+", %89, %90)
    Call(println, [%91], ["borrow"])
    %92 = LoadVar("inner") -> int32
    %93 = IntLiteral(1, int32)
    %94 = BinaryOp("+", %92, %93)
    StoreVar("inner", %94)
    Jump(block_40)

  block_42:
    %95 = LoadVar("outer") -> int32
    %96 = IntLiteral(1, int32)
    %97 = BinaryOp("+", %95, %96)
    StoreVar("outer", %97)
    Jump(block_37)

  block_43:
    %98 = LoadVar("k") -> int32
    %99 = IntLiteral(5, int32)
    %100 = BinaryOp("<", %98, %99)
    Branch(%100, block_44, block_46)

  block_44:
    %101 = LoadVar("k") -> int32
    Call(println, [%101], ["borrow"])
    Jump(block_45)

  block_45:
    %102 = LoadVar("k") -> int32
    %103 = IntLiteral(1, int32)
    %104 = BinaryOp("+", %102, %103)
    StoreVar("k", %104)
    Jump(block_43)

  block_46:
    %105 = StringLiteral("--- For with break ---", string)
    Call(println, [%105], ["borrow"])
    %106 = IntLiteral(0, int32)
    DeclareLocal("m", int32, %106)
    Jump(block_47)

  block_47:
    %107 = LoadVar("m") -> int32
    %108 = IntLiteral(10, int32)
    %109 = BinaryOp("<", %107, %108)
    Branch(%109, block_48, block_50)

  block_48:
    %110 = LoadVar("m") -> int32
    %111 = IntLiteral(5, int32)
    %112 = BinaryOp("==", %110, %111)
    Branch(%112, block_52, block_51)

  block_49:
    %113 = LoadVar("m") -> int32
    %114 = IntLiteral(1, int32)
    %115 = BinaryOp("+", %113, %114)
    StoreVar("m", %115)
    Jump(block_47)

  block_50:
    %116 = StringLiteral("--- For with continue ---", string)
    Call(println, [%116], ["borrow"])
    %117 = IntLiteral(0, int32)
    DeclareLocal("n", int32, %117)
    Jump(block_53)

  block_51:
    %118 = LoadVar("m") -> int32
    Call(println, [%118], ["borrow"])
    Jump(block_49)

  block_52:
    Jump(block_50)

  block_53:
    %119 = LoadVar("n") -> int32
    %120 = IntLiteral(5, int32)
    %121 = BinaryOp("<", %119, %120)
    Branch(%121, block_54, block_56)

  block_54:
    %122 = LoadVar("n") -> int32
    %123 = IntLiteral(2, int32)
    %124 = BinaryOp("==", %122, %123)
    Branch(%124, block_58, block_57)

  block_55:
    %125 = LoadVar("n") -> int32
    %126 = IntLiteral(1, int32)
    %127 = BinaryOp("+", %125, %126)
    StoreVar("n", %127)
    Jump(block_53)

  block_56:
    %128 = StringLiteral("--- For-in loop ---", string)
    Call(println, [%128], ["borrow"])
    %129 = IntLiteral(10, int32)
    %130 = IntLiteral(20, int32)
    %131 = IntLiteral(30, int32)
    %132 = IntLiteral(40, int32)
    %133 = IntLiteral(50, int32)
    %134 = ArrayLiteral([%129, %130, %131, %132, %133], int32[5])
    DeclareLocal("numbers", int32[5], %134)
    %135 = LoadVar("numbers") -> int32[5]
    DeclareLocal("__arr_num", int32[5], %135)
    %136 = IntLiteral(0, int32)
    DeclareLocal("__i_num", int32, %136)
    Jump(block_59)

  block_57:
    %137 = LoadVar("n") -> int32
    Call(println, [%137], ["borrow"])
    Jump(block_55)

  block_58:
    Jump(block_55)

  block_59:
    %138 = LoadVar("__i_num") -> int32
    %139 = IntLiteral(5, int32)
    %140 = BinaryOp("<", %138, %139)
    Branch(%140, block_60, block_61)

  block_60:
    %141 = LoadVar("__arr_num") -> int32[5]
    %142 = LoadVar("__i_num") -> int32
    %143 = IndexArray(%141, %142)
    DeclareLocal("num", int32, %143)
    %144 = LoadVar("num") -> int32
    Call(println, [%144], ["borrow"])
    Jump(block_62)

  block_61:
    %145 = LoadVar("numbers") -> int32[5]
    Drop(%145)
    %146 = StringLiteral("--- Nested for ---", string)
    Call(println, [%146], ["borrow"])
    %147 = IntLiteral(0, int32)
    DeclareLocal("row", int32, %147)
    Jump(block_63)

  block_62:
    %148 = LoadVar("__i_num") -> int32
    %149 = IntLiteral(1, int32)
    %150 = BinaryOp("+", %148, %149)
    StoreVar("__i_num", %150)
    Jump(block_59)

  block_63:
    %151 = LoadVar("row") -> int32
    %152 = IntLiteral(3, int32)
    %153 = BinaryOp("<", %151, %152)
    Branch(%153, block_64, block_66)

  block_64:
    %154 = IntLiteral(0, int32)
    DeclareLocal("col", int32, %154)
    Jump(block_67)

  block_65:
    %155 = LoadVar("row") -> int32
    %156 = IntLiteral(1, int32)
    %157 = BinaryOp("+", %155, %156)
    StoreVar("row", %157)
    Jump(block_63)

  block_66:
    %158 = StringLiteral("--- Mixed nested control flow ---", string)
    Call(println, [%158], ["borrow"])
    %159 = IntLiteral(0, int32)
    DeclareLocal("p", int32, %159)
    Jump(block_71)

  block_67:
    %160 = LoadVar("col") -> int32
    %161 = IntLiteral(3, int32)
    %162 = BinaryOp("<", %160, %161)
    Branch(%162, block_68, block_70)

  block_68:
    %163 = LoadVar("row") -> int32
    %164 = IntLiteral(10, int32)
    %165 = BinaryOp("*", %163, %164)
    %166 = LoadVar("col") -> int32
    %167 = BinaryOp("+", %165, %166)
    Call(println, [%167], ["borrow"])
    Jump(block_69)

  block_69:
    %168 = LoadVar("col") -> int32
    %169 = IntLiteral(1, int32)
    %170 = BinaryOp("+", %168, %169)
    StoreVar("col", %170)
    Jump(block_67)

  block_70:
    Jump(block_65)

  block_71:
    %171 = LoadVar("p") -> int32
    %172 = IntLiteral(3, int32)
    %173 = BinaryOp("<", %171, %172)
    Branch(%173, block_72, block_74)

  block_72:
    %174 = LoadVar("p") -> int32
    %175 = IntLiteral(1, int32)
    %176 = BinaryOp("==", %174, %175)
    Branch(%176, block_76, block_77)

  block_73:
    %177 = LoadVar("p") -> int32
    %178 = IntLiteral(1, int32)
    %179 = BinaryOp("+", %177, %178)
    StoreVar("p", %179)
    Jump(block_71)

  block_74:
    %180 = StringLiteral("=== All control flow tests passed ===", string)
    Call(println, [%180], ["borrow"])
    Return()

  block_75:
    Jump(block_73)

  block_76:
    %181 = IntLiteral(0, int32)
    DeclareLocal("q", int32, %181)
    Jump(block_78)

  block_77:
    %182 = LoadVar("p") -> int32
    %183 = IntLiteral(100, int32)
    %184 = BinaryOp("*", %182, %183)
    Call(println, [%184], ["borrow"])
    Jump(block_75)

  block_78:
    %185 = LoadVar("q") -> int32
    %186 = IntLiteral(2, int32)
    %187 = BinaryOp("<", %185, %186)
    Branch(%187, block_79, block_80)

  block_79:
    %188 = LoadVar("p") -> int32
    %189 = IntLiteral(100, int32)
    %190 = BinaryOp("*", %188, %189)
    %191 = LoadVar("q") -> int32
    %192 = BinaryOp("+", %190, %191)
    Call(println, [%192], ["borrow"])
    %193 = LoadVar("q") -> int32
    %194 = IntLiteral(1, int32)
    %195 = BinaryOp("+", %193, %194)
    StoreVar("q", %195)
    Jump(block_78)

  block_80:
    Jump(block_75)
}

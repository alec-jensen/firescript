module std_cli_args_basic

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("text", string, %1)
    %2 = LoadVar("text") -> string
    Call(stdout, [%2], ["borrow"])
    %3 = LoadVar("text") -> string
    Drop(%3)
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    DeclareLocal("text", string, %3)
    %4 = LoadVar("text") -> string
    Call(stdout, [%4], ["borrow"])
    %5 = LoadVar("text") -> string
    Drop(%5)
    Return()
}

function argc() -> int32 {
  block_0:
    %0 = Call(process_argc, [], []) -> int32
    Return(%0)
}

function argv_at(index: int32) -> string {
  block_0:
    %0 = LoadVar("index") -> int32
    %1 = Call(process_argv_at, [%0], ["borrow"]) -> string
    Return(%1)
}

function _starts_with(value: &string, prefix: &string) -> bool {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = LoadVar("prefix") -> string
    %2 = Call(str_index_of, [%0, %1], ["borrow", "borrow"]) -> int32
    %3 = IntLiteral(0, int32)
    %4 = BinaryOp("==", %2, %3)
    Return(%4)
}

function _str_len(value: &string) -> int32 {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = Call(str_length, [%0], ["borrow"]) -> int32
    Return(%1)
}

function _is_grouped_short_token(value: &string) -> bool {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = StringLiteral("-", string)
    %2 = Call(_starts_with, [%0, %1], ["borrow", "borrow"]) -> bool
    %3 = BoolLiteral(false, bool)
    %4 = BinaryOp("==", %2, %3)
    Branch(%4, block_2, block_1)

  block_1:
    %5 = LoadVar("value") -> string
    %6 = StringLiteral("--", string)
    %7 = Call(_starts_with, [%5, %6], ["borrow", "borrow"]) -> bool
    Branch(%7, block_4, block_3)

  block_2:
    %8 = BoolLiteral(false, bool)
    Return(%8)

  block_3:
    %9 = LoadVar("value") -> string
    %10 = Call(_str_len, [%9], ["borrow"]) -> int32
    %11 = IntLiteral(2, int32)
    %12 = BinaryOp("<=", %10, %11)
    Branch(%12, block_6, block_5)

  block_4:
    %13 = BoolLiteral(false, bool)
    Return(%13)

  block_5:
    %14 = LoadVar("value") -> string
    %15 = StringLiteral("=", string)
    %16 = Call(str_index_of, [%14, %15], ["borrow", "borrow"]) -> int32
    %17 = IntLiteral(0, int32)
    %18 = BinaryOp(">=", %16, %17)
    Branch(%18, block_8, block_7)

  block_6:
    %19 = BoolLiteral(false, bool)
    Return(%19)

  block_7:
    %20 = BoolLiteral(true, bool)
    Return(%20)

  block_8:
    %21 = BoolLiteral(false, bool)
    Return(%21)
}

function _group_has_short(token: &string, short_name: &string) -> bool {
  block_0:
    %0 = LoadVar("short_name") -> string
    %1 = Call(_str_len, [%0], ["borrow"]) -> int32
    %2 = IntLiteral(1, int32)
    %3 = BinaryOp("!=", %1, %2)
    Branch(%3, block_2, block_1)

  block_1:
    %4 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %4)
    Jump(block_3)

  block_2:
    %5 = BoolLiteral(false, bool)
    Return(%5)

  block_3:
    %6 = LoadVar("i") -> int32
    %7 = LoadVar("token") -> string
    %8 = Call(_str_len, [%7], ["borrow"]) -> int32
    %9 = BinaryOp("<", %6, %8)
    Branch(%9, block_4, block_5)

  block_4:
    %10 = LoadVar("token") -> string
    %11 = LoadVar("i") -> int32
    %12 = Call(str_char_at, [%10, %11], ["borrow", "borrow"]) -> string
    DeclareLocal("ch", string, %12)
    %13 = LoadVar("ch") -> string
    %14 = LoadVar("short_name") -> string
    %15 = BinaryOp("==", %13, %14)
    Branch(%15, block_7, block_6)

  block_5:
    %16 = BoolLiteral(false, bool)
    Return(%16)

  block_6:
    %17 = LoadVar("ch") -> string
    Drop(%17)
    %18 = LoadVar("i") -> int32
    %19 = IntLiteral(1, int32)
    %20 = BinaryOp("+", %18, %19)
    StoreVar("i", %20)
    Jump(block_3)

  block_7:
    %21 = LoadVar("ch") -> string
    Drop(%21)
    %22 = BoolLiteral(true, bool)
    Return(%22)
}

function has_flag(name: string) -> bool {
  block_0:
    %0 = StringLiteral("-", string)
    %1 = LoadVar("name") -> string
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("short_flag", string, %2)
    %3 = StringLiteral("--", string)
    %4 = LoadVar("name") -> string
    %5 = BinaryOp("+", %3, %4)
    DeclareLocal("long_flag", string, %5)
    %6 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %6)
    Jump(block_1)

  block_1:
    %7 = LoadVar("i") -> int32
    %8 = Call(argc, [], []) -> int32
    %9 = BinaryOp("<", %7, %8)
    Branch(%9, block_2, block_3)

  block_2:
    %10 = LoadVar("i") -> int32
    %11 = Call(argv_at, [%10], ["own"]) -> string
    DeclareLocal("arg", string, %11)
    %12 = LoadVar("arg") -> string
    %13 = StringLiteral("--", string)
    %14 = BinaryOp("==", %12, %13)
    Branch(%14, block_5, block_4)

  block_3:
    %15 = LoadVar("name") -> string
    Drop(%15)
    %16 = LoadVar("short_flag") -> string
    Drop(%16)
    %17 = LoadVar("long_flag") -> string
    Drop(%17)
    %18 = BoolLiteral(false, bool)
    Return(%18)

  block_4:
    %19 = LoadVar("arg") -> string
    %20 = LoadVar("short_flag") -> string
    %21 = BinaryOp("==", %19, %20)
    Branch(%21, block_7, block_6)

  block_5:
    %22 = LoadVar("name") -> string
    Drop(%22)
    %23 = LoadVar("short_flag") -> string
    Drop(%23)
    %24 = LoadVar("long_flag") -> string
    Drop(%24)
    %25 = LoadVar("arg") -> string
    Drop(%25)
    %26 = BoolLiteral(false, bool)
    Return(%26)

  block_6:
    %27 = LoadVar("arg") -> string
    %28 = LoadVar("long_flag") -> string
    %29 = BinaryOp("==", %27, %28)
    Branch(%29, block_9, block_8)

  block_7:
    %30 = LoadVar("name") -> string
    Drop(%30)
    %31 = LoadVar("short_flag") -> string
    Drop(%31)
    %32 = LoadVar("long_flag") -> string
    Drop(%32)
    %33 = LoadVar("arg") -> string
    Drop(%33)
    %34 = BoolLiteral(true, bool)
    Return(%34)

  block_8:
    %35 = LoadVar("arg") -> string
    %36 = Call(_is_grouped_short_token, [%35], ["borrow"]) -> bool
    Branch(%36, block_11, block_10)

  block_9:
    %37 = LoadVar("name") -> string
    Drop(%37)
    %38 = LoadVar("short_flag") -> string
    Drop(%38)
    %39 = LoadVar("long_flag") -> string
    Drop(%39)
    %40 = LoadVar("arg") -> string
    Drop(%40)
    %41 = BoolLiteral(true, bool)
    Return(%41)

  block_10:
    %42 = LoadVar("arg") -> string
    Drop(%42)
    %43 = LoadVar("i") -> int32
    %44 = IntLiteral(1, int32)
    %45 = BinaryOp("+", %43, %44)
    StoreVar("i", %45)
    Jump(block_1)

  block_11:
    %46 = LoadVar("arg") -> string
    %47 = LoadVar("name") -> string
    %48 = Call(_group_has_short, [%46, %47], ["borrow", "borrow"]) -> bool
    Branch(%48, block_13, block_12)

  block_12:
    Jump(block_10)

  block_13:
    %49 = LoadVar("name") -> string
    Drop(%49)
    %50 = LoadVar("short_flag") -> string
    Drop(%50)
    %51 = LoadVar("long_flag") -> string
    Drop(%51)
    %52 = LoadVar("arg") -> string
    Drop(%52)
    %53 = BoolLiteral(true, bool)
    Return(%53)
}

function has_flag_alias(long_name: string, short_name: string) -> bool {
  block_0:
    %0 = StringLiteral("-", string)
    %1 = LoadVar("short_name") -> string
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("short_flag", string, %2)
    %3 = StringLiteral("--", string)
    %4 = LoadVar("long_name") -> string
    %5 = BinaryOp("+", %3, %4)
    DeclareLocal("long_flag", string, %5)
    %6 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %6)
    Jump(block_1)

  block_1:
    %7 = LoadVar("i") -> int32
    %8 = Call(argc, [], []) -> int32
    %9 = BinaryOp("<", %7, %8)
    Branch(%9, block_2, block_3)

  block_2:
    %10 = LoadVar("i") -> int32
    %11 = Call(argv_at, [%10], ["own"]) -> string
    DeclareLocal("arg", string, %11)
    %12 = LoadVar("arg") -> string
    %13 = StringLiteral("--", string)
    %14 = BinaryOp("==", %12, %13)
    Branch(%14, block_5, block_4)

  block_3:
    %15 = LoadVar("long_name") -> string
    Drop(%15)
    %16 = LoadVar("short_name") -> string
    Drop(%16)
    %17 = LoadVar("short_flag") -> string
    Drop(%17)
    %18 = LoadVar("long_flag") -> string
    Drop(%18)
    %19 = BoolLiteral(false, bool)
    Return(%19)

  block_4:
    %20 = LoadVar("arg") -> string
    %21 = LoadVar("short_flag") -> string
    %22 = BinaryOp("==", %20, %21)
    Branch(%22, block_7, block_6)

  block_5:
    %23 = LoadVar("long_name") -> string
    Drop(%23)
    %24 = LoadVar("short_name") -> string
    Drop(%24)
    %25 = LoadVar("short_flag") -> string
    Drop(%25)
    %26 = LoadVar("long_flag") -> string
    Drop(%26)
    %27 = LoadVar("arg") -> string
    Drop(%27)
    %28 = BoolLiteral(false, bool)
    Return(%28)

  block_6:
    %29 = LoadVar("arg") -> string
    %30 = LoadVar("long_flag") -> string
    %31 = BinaryOp("==", %29, %30)
    Branch(%31, block_9, block_8)

  block_7:
    %32 = LoadVar("long_name") -> string
    Drop(%32)
    %33 = LoadVar("short_name") -> string
    Drop(%33)
    %34 = LoadVar("short_flag") -> string
    Drop(%34)
    %35 = LoadVar("long_flag") -> string
    Drop(%35)
    %36 = LoadVar("arg") -> string
    Drop(%36)
    %37 = BoolLiteral(true, bool)
    Return(%37)

  block_8:
    %38 = LoadVar("arg") -> string
    %39 = Call(_is_grouped_short_token, [%38], ["borrow"]) -> bool
    Branch(%39, block_11, block_10)

  block_9:
    %40 = LoadVar("long_name") -> string
    Drop(%40)
    %41 = LoadVar("short_name") -> string
    Drop(%41)
    %42 = LoadVar("short_flag") -> string
    Drop(%42)
    %43 = LoadVar("long_flag") -> string
    Drop(%43)
    %44 = LoadVar("arg") -> string
    Drop(%44)
    %45 = BoolLiteral(true, bool)
    Return(%45)

  block_10:
    %46 = LoadVar("arg") -> string
    Drop(%46)
    %47 = LoadVar("i") -> int32
    %48 = IntLiteral(1, int32)
    %49 = BinaryOp("+", %47, %48)
    StoreVar("i", %49)
    Jump(block_1)

  block_11:
    %50 = LoadVar("arg") -> string
    %51 = LoadVar("short_name") -> string
    %52 = Call(_group_has_short, [%50, %51], ["borrow", "borrow"]) -> bool
    Branch(%52, block_13, block_12)

  block_12:
    Jump(block_10)

  block_13:
    %53 = LoadVar("long_name") -> string
    Drop(%53)
    %54 = LoadVar("short_name") -> string
    Drop(%54)
    %55 = LoadVar("short_flag") -> string
    Drop(%55)
    %56 = LoadVar("long_flag") -> string
    Drop(%56)
    %57 = LoadVar("arg") -> string
    Drop(%57)
    %58 = BoolLiteral(true, bool)
    Return(%58)
}

function _looks_like_option_token(value: &string) -> bool {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = StringLiteral("-", string)
    %2 = BinaryOp("==", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = LoadVar("value") -> string
    %4 = StringLiteral("-", string)
    %5 = Call(_starts_with, [%3, %4], ["borrow", "borrow"]) -> bool
    %6 = BoolLiteral(true, bool)
    %7 = BinaryOp("==", %5, %6)
    Return(%7)

  block_2:
    %8 = BoolLiteral(false, bool)
    Return(%8)
}

function _value_after_equals(token: &string) -> string {
  block_0:
    %0 = LoadVar("token") -> string
    %1 = StringLiteral("=", string)
    %2 = Call(str_index_of, [%0, %1], ["borrow", "borrow"]) -> int32
    DeclareLocal("eq", int32, %2)
    %3 = LoadVar("eq") -> int32
    %4 = IntLiteral(0, int32)
    %5 = BinaryOp("<", %3, %4)
    Branch(%5, block_2, block_1)

  block_1:
    %6 = LoadVar("eq") -> int32
    %7 = IntLiteral(1, int32)
    %8 = BinaryOp("+", %6, %7)
    DeclareLocal("start", int32, %8)
    %9 = LoadVar("token") -> string
    %10 = LoadVar("start") -> int32
    %11 = LoadVar("token") -> string
    %12 = Call(_str_len, [%11], ["borrow"]) -> int32
    %13 = Call(str_slice, [%9, %10, %12], ["borrow", "borrow", "borrow"]) -> string
    Return(%13)

  block_2:
    %14 = StringLiteral("", string)
    Return(%14)
}

function option_value(name: string, fallback: string) -> string {
  block_0:
    %0 = StringLiteral("-", string)
    %1 = LoadVar("name") -> string
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("short_flag", string, %2)
    %3 = StringLiteral("--", string)
    %4 = LoadVar("name") -> string
    %5 = BinaryOp("+", %3, %4)
    DeclareLocal("long_flag", string, %5)
    %6 = LoadVar("short_flag") -> string
    %7 = StringLiteral("=", string)
    %8 = BinaryOp("+", %6, %7)
    DeclareLocal("short_eq", string, %8)
    %9 = LoadVar("long_flag") -> string
    %10 = StringLiteral("=", string)
    %11 = BinaryOp("+", %9, %10)
    DeclareLocal("long_eq", string, %11)
    %12 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %12)
    Jump(block_1)

  block_1:
    %13 = LoadVar("i") -> int32
    %14 = Call(argc, [], []) -> int32
    %15 = BinaryOp("<", %13, %14)
    Branch(%15, block_2, block_3)

  block_2:
    %16 = LoadVar("i") -> int32
    %17 = Call(argv_at, [%16], ["own"]) -> string
    DeclareLocal("arg", string, %17)
    %18 = LoadVar("arg") -> string
    %19 = StringLiteral("--", string)
    %20 = BinaryOp("==", %18, %19)
    Branch(%20, block_5, block_4)

  block_3:
    %21 = LoadVar("name") -> string
    Drop(%21)
    %22 = LoadVar("short_flag") -> string
    Drop(%22)
    %23 = LoadVar("long_flag") -> string
    Drop(%23)
    %24 = LoadVar("short_eq") -> string
    Drop(%24)
    %25 = LoadVar("long_eq") -> string
    Drop(%25)
    %26 = LoadVar("fallback") -> string
    Return(%26)

  block_4:
    %27 = LoadVar("arg") -> string
    %28 = LoadVar("short_flag") -> string
    %29 = BinaryOp("==", %27, %28)
    Branch(%29, block_7, block_6)

  block_5:
    %30 = LoadVar("name") -> string
    Drop(%30)
    %31 = LoadVar("short_flag") -> string
    Drop(%31)
    %32 = LoadVar("long_flag") -> string
    Drop(%32)
    %33 = LoadVar("short_eq") -> string
    Drop(%33)
    %34 = LoadVar("long_eq") -> string
    Drop(%34)
    %35 = LoadVar("arg") -> string
    Drop(%35)
    %36 = LoadVar("fallback") -> string
    Return(%36)

  block_6:
    %37 = LoadVar("arg") -> string
    %38 = LoadVar("long_flag") -> string
    %39 = BinaryOp("==", %37, %38)
    Branch(%39, block_13, block_12)

  block_7:
    %40 = LoadVar("i") -> int32
    %41 = IntLiteral(1, int32)
    %42 = BinaryOp("+", %40, %41)
    DeclareLocal("next", int32, %42)
    %43 = LoadVar("next") -> int32
    %44 = Call(argc, [], []) -> int32
    %45 = BinaryOp("<", %43, %44)
    Branch(%45, block_9, block_8)

  block_8:
    %46 = LoadVar("i") -> int32
    %47 = IntLiteral(1, int32)
    %48 = BinaryOp("+", %46, %47)
    StoreVar("i", %48)
    %49 = LoadVar("arg") -> string
    Drop(%49)
    Jump(block_1)

  block_9:
    %50 = LoadVar("next") -> int32
    %51 = Call(argv_at, [%50], ["own"]) -> string
    DeclareLocal("next_value", string, %51)
    %52 = LoadVar("next_value") -> string
    %53 = Call(_looks_like_option_token, [%52], ["borrow"]) -> bool
    %54 = BoolLiteral(false, bool)
    %55 = BinaryOp("==", %53, %54)
    Branch(%55, block_11, block_10)

  block_10:
    %56 = LoadVar("next_value") -> string
    Drop(%56)
    Jump(block_8)

  block_11:
    %57 = LoadVar("name") -> string
    Drop(%57)
    %58 = LoadVar("fallback") -> string
    Drop(%58)
    %59 = LoadVar("short_flag") -> string
    Drop(%59)
    %60 = LoadVar("long_flag") -> string
    Drop(%60)
    %61 = LoadVar("short_eq") -> string
    Drop(%61)
    %62 = LoadVar("long_eq") -> string
    Drop(%62)
    %63 = LoadVar("arg") -> string
    Drop(%63)
    %64 = LoadVar("next_value") -> string
    Return(%64)

  block_12:
    %65 = LoadVar("arg") -> string
    %66 = LoadVar("short_eq") -> string
    %67 = Call(_starts_with, [%65, %66], ["borrow", "borrow"]) -> bool
    Branch(%67, block_19, block_18)

  block_13:
    %68 = LoadVar("i") -> int32
    %69 = IntLiteral(1, int32)
    %70 = BinaryOp("+", %68, %69)
    DeclareLocal("next__2", int32, %70)
    %71 = LoadVar("next__2") -> int32
    %72 = Call(argc, [], []) -> int32
    %73 = BinaryOp("<", %71, %72)
    Branch(%73, block_15, block_14)

  block_14:
    %74 = LoadVar("i") -> int32
    %75 = IntLiteral(1, int32)
    %76 = BinaryOp("+", %74, %75)
    StoreVar("i", %76)
    %77 = LoadVar("arg") -> string
    Drop(%77)
    Jump(block_1)

  block_15:
    %78 = LoadVar("next__2") -> int32
    %79 = Call(argv_at, [%78], ["own"]) -> string
    DeclareLocal("next_value__2", string, %79)
    %80 = LoadVar("next_value__2") -> string
    %81 = Call(_looks_like_option_token, [%80], ["borrow"]) -> bool
    %82 = BoolLiteral(false, bool)
    %83 = BinaryOp("==", %81, %82)
    Branch(%83, block_17, block_16)

  block_16:
    %84 = LoadVar("next_value__2") -> string
    Drop(%84)
    Jump(block_14)

  block_17:
    %85 = LoadVar("name") -> string
    Drop(%85)
    %86 = LoadVar("fallback") -> string
    Drop(%86)
    %87 = LoadVar("short_flag") -> string
    Drop(%87)
    %88 = LoadVar("long_flag") -> string
    Drop(%88)
    %89 = LoadVar("short_eq") -> string
    Drop(%89)
    %90 = LoadVar("long_eq") -> string
    Drop(%90)
    %91 = LoadVar("arg") -> string
    Drop(%91)
    %92 = LoadVar("next_value__2") -> string
    Return(%92)

  block_18:
    %93 = LoadVar("arg") -> string
    %94 = LoadVar("long_eq") -> string
    %95 = Call(_starts_with, [%93, %94], ["borrow", "borrow"]) -> bool
    Branch(%95, block_21, block_20)

  block_19:
    %96 = LoadVar("arg") -> string
    %97 = Call(_value_after_equals, [%96], ["borrow"]) -> string
    DeclareLocal("result", string, %97)
    %98 = LoadVar("name") -> string
    Drop(%98)
    %99 = LoadVar("fallback") -> string
    Drop(%99)
    %100 = LoadVar("short_flag") -> string
    Drop(%100)
    %101 = LoadVar("long_flag") -> string
    Drop(%101)
    %102 = LoadVar("short_eq") -> string
    Drop(%102)
    %103 = LoadVar("long_eq") -> string
    Drop(%103)
    %104 = LoadVar("arg") -> string
    Drop(%104)
    %105 = LoadVar("result") -> string
    Return(%105)

  block_20:
    %106 = LoadVar("arg") -> string
    Drop(%106)
    %107 = LoadVar("i") -> int32
    %108 = IntLiteral(1, int32)
    %109 = BinaryOp("+", %107, %108)
    StoreVar("i", %109)
    Jump(block_1)

  block_21:
    %110 = LoadVar("arg") -> string
    %111 = Call(_value_after_equals, [%110], ["borrow"]) -> string
    DeclareLocal("result__2", string, %111)
    %112 = LoadVar("name") -> string
    Drop(%112)
    %113 = LoadVar("fallback") -> string
    Drop(%113)
    %114 = LoadVar("short_flag") -> string
    Drop(%114)
    %115 = LoadVar("long_flag") -> string
    Drop(%115)
    %116 = LoadVar("short_eq") -> string
    Drop(%116)
    %117 = LoadVar("long_eq") -> string
    Drop(%117)
    %118 = LoadVar("arg") -> string
    Drop(%118)
    %119 = LoadVar("result__2") -> string
    Return(%119)
}

function option_value_alias(long_name: string, short_name: string, fallback: string) -> string {
  block_0:
    %0 = StringLiteral("-", string)
    %1 = LoadVar("short_name") -> string
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("short_flag", string, %2)
    %3 = StringLiteral("--", string)
    %4 = LoadVar("long_name") -> string
    %5 = BinaryOp("+", %3, %4)
    DeclareLocal("long_flag", string, %5)
    %6 = LoadVar("short_flag") -> string
    %7 = StringLiteral("=", string)
    %8 = BinaryOp("+", %6, %7)
    DeclareLocal("short_eq", string, %8)
    %9 = LoadVar("long_flag") -> string
    %10 = StringLiteral("=", string)
    %11 = BinaryOp("+", %9, %10)
    DeclareLocal("long_eq", string, %11)
    %12 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %12)
    Jump(block_1)

  block_1:
    %13 = LoadVar("i") -> int32
    %14 = Call(argc, [], []) -> int32
    %15 = BinaryOp("<", %13, %14)
    Branch(%15, block_2, block_3)

  block_2:
    %16 = LoadVar("i") -> int32
    %17 = Call(argv_at, [%16], ["own"]) -> string
    DeclareLocal("arg", string, %17)
    %18 = LoadVar("arg") -> string
    %19 = StringLiteral("--", string)
    %20 = BinaryOp("==", %18, %19)
    Branch(%20, block_5, block_4)

  block_3:
    %21 = LoadVar("long_name") -> string
    Drop(%21)
    %22 = LoadVar("short_name") -> string
    Drop(%22)
    %23 = LoadVar("short_flag") -> string
    Drop(%23)
    %24 = LoadVar("long_flag") -> string
    Drop(%24)
    %25 = LoadVar("short_eq") -> string
    Drop(%25)
    %26 = LoadVar("long_eq") -> string
    Drop(%26)
    %27 = LoadVar("fallback") -> string
    Return(%27)

  block_4:
    %28 = LoadVar("arg") -> string
    %29 = LoadVar("short_flag") -> string
    %30 = BinaryOp("==", %28, %29)
    Branch(%30, block_7, block_6)

  block_5:
    %31 = LoadVar("long_name") -> string
    Drop(%31)
    %32 = LoadVar("short_name") -> string
    Drop(%32)
    %33 = LoadVar("short_flag") -> string
    Drop(%33)
    %34 = LoadVar("long_flag") -> string
    Drop(%34)
    %35 = LoadVar("short_eq") -> string
    Drop(%35)
    %36 = LoadVar("long_eq") -> string
    Drop(%36)
    %37 = LoadVar("arg") -> string
    Drop(%37)
    %38 = LoadVar("fallback") -> string
    Return(%38)

  block_6:
    %39 = LoadVar("arg") -> string
    %40 = LoadVar("long_flag") -> string
    %41 = BinaryOp("==", %39, %40)
    Branch(%41, block_13, block_12)

  block_7:
    %42 = LoadVar("i") -> int32
    %43 = IntLiteral(1, int32)
    %44 = BinaryOp("+", %42, %43)
    DeclareLocal("next", int32, %44)
    %45 = LoadVar("next") -> int32
    %46 = Call(argc, [], []) -> int32
    %47 = BinaryOp("<", %45, %46)
    Branch(%47, block_9, block_8)

  block_8:
    %48 = LoadVar("i") -> int32
    %49 = IntLiteral(1, int32)
    %50 = BinaryOp("+", %48, %49)
    StoreVar("i", %50)
    %51 = LoadVar("arg") -> string
    Drop(%51)
    Jump(block_1)

  block_9:
    %52 = LoadVar("next") -> int32
    %53 = Call(argv_at, [%52], ["own"]) -> string
    DeclareLocal("next_value", string, %53)
    %54 = LoadVar("next_value") -> string
    %55 = Call(_looks_like_option_token, [%54], ["borrow"]) -> bool
    %56 = BoolLiteral(false, bool)
    %57 = BinaryOp("==", %55, %56)
    Branch(%57, block_11, block_10)

  block_10:
    %58 = LoadVar("next_value") -> string
    Drop(%58)
    Jump(block_8)

  block_11:
    %59 = LoadVar("long_name") -> string
    Drop(%59)
    %60 = LoadVar("short_name") -> string
    Drop(%60)
    %61 = LoadVar("fallback") -> string
    Drop(%61)
    %62 = LoadVar("short_flag") -> string
    Drop(%62)
    %63 = LoadVar("long_flag") -> string
    Drop(%63)
    %64 = LoadVar("short_eq") -> string
    Drop(%64)
    %65 = LoadVar("long_eq") -> string
    Drop(%65)
    %66 = LoadVar("arg") -> string
    Drop(%66)
    %67 = LoadVar("next_value") -> string
    Return(%67)

  block_12:
    %68 = LoadVar("arg") -> string
    %69 = LoadVar("short_eq") -> string
    %70 = Call(_starts_with, [%68, %69], ["borrow", "borrow"]) -> bool
    Branch(%70, block_19, block_18)

  block_13:
    %71 = LoadVar("i") -> int32
    %72 = IntLiteral(1, int32)
    %73 = BinaryOp("+", %71, %72)
    DeclareLocal("next__2", int32, %73)
    %74 = LoadVar("next__2") -> int32
    %75 = Call(argc, [], []) -> int32
    %76 = BinaryOp("<", %74, %75)
    Branch(%76, block_15, block_14)

  block_14:
    %77 = LoadVar("i") -> int32
    %78 = IntLiteral(1, int32)
    %79 = BinaryOp("+", %77, %78)
    StoreVar("i", %79)
    %80 = LoadVar("arg") -> string
    Drop(%80)
    Jump(block_1)

  block_15:
    %81 = LoadVar("next__2") -> int32
    %82 = Call(argv_at, [%81], ["own"]) -> string
    DeclareLocal("next_value__2", string, %82)
    %83 = LoadVar("next_value__2") -> string
    %84 = Call(_looks_like_option_token, [%83], ["borrow"]) -> bool
    %85 = BoolLiteral(false, bool)
    %86 = BinaryOp("==", %84, %85)
    Branch(%86, block_17, block_16)

  block_16:
    %87 = LoadVar("next_value__2") -> string
    Drop(%87)
    Jump(block_14)

  block_17:
    %88 = LoadVar("long_name") -> string
    Drop(%88)
    %89 = LoadVar("short_name") -> string
    Drop(%89)
    %90 = LoadVar("fallback") -> string
    Drop(%90)
    %91 = LoadVar("short_flag") -> string
    Drop(%91)
    %92 = LoadVar("long_flag") -> string
    Drop(%92)
    %93 = LoadVar("short_eq") -> string
    Drop(%93)
    %94 = LoadVar("long_eq") -> string
    Drop(%94)
    %95 = LoadVar("arg") -> string
    Drop(%95)
    %96 = LoadVar("next_value__2") -> string
    Return(%96)

  block_18:
    %97 = LoadVar("arg") -> string
    %98 = LoadVar("long_eq") -> string
    %99 = Call(_starts_with, [%97, %98], ["borrow", "borrow"]) -> bool
    Branch(%99, block_21, block_20)

  block_19:
    %100 = LoadVar("arg") -> string
    %101 = Call(_value_after_equals, [%100], ["borrow"]) -> string
    DeclareLocal("result", string, %101)
    %102 = LoadVar("long_name") -> string
    Drop(%102)
    %103 = LoadVar("short_name") -> string
    Drop(%103)
    %104 = LoadVar("fallback") -> string
    Drop(%104)
    %105 = LoadVar("short_flag") -> string
    Drop(%105)
    %106 = LoadVar("long_flag") -> string
    Drop(%106)
    %107 = LoadVar("short_eq") -> string
    Drop(%107)
    %108 = LoadVar("long_eq") -> string
    Drop(%108)
    %109 = LoadVar("arg") -> string
    Drop(%109)
    %110 = LoadVar("result") -> string
    Return(%110)

  block_20:
    %111 = LoadVar("short_name") -> string
    %112 = Call(_str_len, [%111], ["borrow"]) -> int32
    %113 = IntLiteral(1, int32)
    %114 = BinaryOp("==", %112, %113)
    Branch(%114, block_23, block_22)

  block_21:
    %115 = LoadVar("arg") -> string
    %116 = Call(_value_after_equals, [%115], ["borrow"]) -> string
    DeclareLocal("result__2", string, %116)
    %117 = LoadVar("long_name") -> string
    Drop(%117)
    %118 = LoadVar("short_name") -> string
    Drop(%118)
    %119 = LoadVar("fallback") -> string
    Drop(%119)
    %120 = LoadVar("short_flag") -> string
    Drop(%120)
    %121 = LoadVar("long_flag") -> string
    Drop(%121)
    %122 = LoadVar("short_eq") -> string
    Drop(%122)
    %123 = LoadVar("long_eq") -> string
    Drop(%123)
    %124 = LoadVar("arg") -> string
    Drop(%124)
    %125 = LoadVar("result__2") -> string
    Return(%125)

  block_22:
    %126 = LoadVar("arg") -> string
    Drop(%126)
    %127 = LoadVar("i") -> int32
    %128 = IntLiteral(1, int32)
    %129 = BinaryOp("+", %127, %128)
    StoreVar("i", %129)
    Jump(block_1)

  block_23:
    %130 = LoadVar("arg") -> string
    %131 = LoadVar("short_flag") -> string
    %132 = Call(_starts_with, [%130, %131], ["borrow", "borrow"]) -> bool
    Branch(%132, block_25, block_24)

  block_24:
    Jump(block_22)

  block_25:
    %133 = LoadVar("arg") -> string
    %134 = Call(_str_len, [%133], ["borrow"]) -> int32
    %135 = IntLiteral(2, int32)
    %136 = BinaryOp(">", %134, %135)
    Branch(%136, block_27, block_26)

  block_26:
    Jump(block_24)

  block_27:
    %137 = LoadVar("arg") -> string
    %138 = IntLiteral(2, int32)
    %139 = LoadVar("arg") -> string
    %140 = Call(_str_len, [%139], ["borrow"]) -> int32
    %141 = Call(str_slice, [%137, %138, %140], ["borrow", "borrow", "borrow"]) -> string
    DeclareLocal("result__3", string, %141)
    %142 = LoadVar("long_name") -> string
    Drop(%142)
    %143 = LoadVar("short_name") -> string
    Drop(%143)
    %144 = LoadVar("fallback") -> string
    Drop(%144)
    %145 = LoadVar("short_flag") -> string
    Drop(%145)
    %146 = LoadVar("long_flag") -> string
    Drop(%146)
    %147 = LoadVar("short_eq") -> string
    Drop(%147)
    %148 = LoadVar("long_eq") -> string
    Drop(%148)
    %149 = LoadVar("arg") -> string
    Drop(%149)
    %150 = LoadVar("result__3") -> string
    Return(%150)
}

function positional(index: int32, fallback: string) -> string {
  block_0:
    %0 = LoadVar("index") -> int32
    %1 = IntLiteral(1, int32)
    %2 = BinaryOp("+", %0, %1)
    DeclareLocal("raw_index", int32, %2)
    %3 = LoadVar("raw_index") -> int32
    %4 = IntLiteral(1, int32)
    %5 = BinaryOp("<", %3, %4)
    Branch(%5, block_2, block_1)

  block_1:
    %6 = LoadVar("raw_index") -> int32
    %7 = Call(argc, [], []) -> int32
    %8 = BinaryOp(">=", %6, %7)
    Branch(%8, block_4, block_3)

  block_2:
    %9 = LoadVar("fallback") -> string
    Return(%9)

  block_3:
    %10 = LoadVar("fallback") -> string
    Drop(%10)
    %11 = LoadVar("raw_index") -> int32
    %12 = Call(argv_at, [%11], ["own"]) -> string
    Return(%12)

  block_4:
    %13 = LoadVar("fallback") -> string
    Return(%13)
}

function positional_value(index: int32, fallback: string) -> string {
  block_0:
    %0 = LoadVar("index") -> int32
    %1 = IntLiteral(0, int32)
    %2 = BinaryOp("<", %0, %1)
    Branch(%2, block_2, block_1)

  block_1:
    %3 = IntLiteral(0, int32)
    DeclareLocal("logical_pos", int32, %3)
    %4 = IntLiteral(1, int32)
    DeclareLocal("i", int32, %4)
    %5 = BoolLiteral(true, bool)
    DeclareLocal("parsing_options", bool, %5)
    Jump(block_3)

  block_2:
    %6 = LoadVar("fallback") -> string
    Return(%6)

  block_3:
    %7 = LoadVar("i") -> int32
    %8 = Call(argc, [], []) -> int32
    %9 = BinaryOp("<", %7, %8)
    Branch(%9, block_4, block_5)

  block_4:
    %10 = LoadVar("i") -> int32
    %11 = Call(argv_at, [%10], ["own"]) -> string
    DeclareLocal("arg", string, %11)
    %12 = LoadVar("parsing_options") -> bool
    Branch(%12, block_7, block_6)

  block_5:
    %13 = LoadVar("fallback") -> string
    Return(%13)

  block_6:
    %14 = LoadVar("logical_pos") -> int32
    %15 = LoadVar("index") -> int32
    %16 = BinaryOp("==", %14, %15)
    Branch(%16, block_33, block_32)

  block_7:
    %17 = LoadVar("arg") -> string
    %18 = StringLiteral("--", string)
    %19 = BinaryOp("==", %17, %18)
    Branch(%19, block_9, block_8)

  block_8:
    %20 = LoadVar("arg") -> string
    %21 = StringLiteral("--", string)
    %22 = Call(_starts_with, [%20, %21], ["borrow", "borrow"]) -> bool
    Branch(%22, block_11, block_10)

  block_9:
    %23 = BoolLiteral(false, bool)
    StoreVar("parsing_options", %23)
    %24 = LoadVar("i") -> int32
    %25 = IntLiteral(1, int32)
    %26 = BinaryOp("+", %24, %25)
    StoreVar("i", %26)
    %27 = LoadVar("arg") -> string
    Drop(%27)
    Jump(block_3)

  block_10:
    %28 = LoadVar("arg") -> string
    %29 = StringLiteral("-", string)
    %30 = Call(_starts_with, [%28, %29], ["borrow", "borrow"]) -> bool
    Branch(%30, block_19, block_18)

  block_11:
    %31 = LoadVar("arg") -> string
    %32 = StringLiteral("=", string)
    %33 = Call(str_index_of, [%31, %32], ["borrow", "borrow"]) -> int32
    %34 = IntLiteral(0, int32)
    %35 = BinaryOp(">=", %33, %34)
    Branch(%35, block_13, block_12)

  block_12:
    %36 = LoadVar("i") -> int32
    %37 = IntLiteral(1, int32)
    %38 = BinaryOp("+", %36, %37)
    DeclareLocal("next", int32, %38)
    %39 = LoadVar("next") -> int32
    %40 = Call(argc, [], []) -> int32
    %41 = BinaryOp("<", %39, %40)
    Branch(%41, block_15, block_14)

  block_13:
    %42 = LoadVar("i") -> int32
    %43 = IntLiteral(1, int32)
    %44 = BinaryOp("+", %42, %43)
    StoreVar("i", %44)
    %45 = LoadVar("arg") -> string
    Drop(%45)
    Jump(block_3)

  block_14:
    %46 = LoadVar("i") -> int32
    %47 = IntLiteral(1, int32)
    %48 = BinaryOp("+", %46, %47)
    StoreVar("i", %48)
    %49 = LoadVar("arg") -> string
    Drop(%49)
    Jump(block_3)

  block_15:
    %50 = LoadVar("next") -> int32
    %51 = Call(argv_at, [%50], ["own"]) -> string
    DeclareLocal("next_value", string, %51)
    %52 = LoadVar("next_value") -> string
    %53 = Call(_looks_like_option_token, [%52], ["borrow"]) -> bool
    %54 = BoolLiteral(false, bool)
    %55 = BinaryOp("==", %53, %54)
    Branch(%55, block_17, block_16)

  block_16:
    %56 = LoadVar("next_value") -> string
    Drop(%56)
    Jump(block_14)

  block_17:
    %57 = LoadVar("i") -> int32
    %58 = IntLiteral(2, int32)
    %59 = BinaryOp("+", %57, %58)
    StoreVar("i", %59)
    %60 = LoadVar("next_value") -> string
    Drop(%60)
    %61 = LoadVar("arg") -> string
    Drop(%61)
    Jump(block_3)

  block_18:
    Jump(block_6)

  block_19:
    %62 = LoadVar("arg") -> string
    %63 = Call(_str_len, [%62], ["borrow"]) -> int32
    DeclareLocal("n", int32, %63)
    %64 = LoadVar("n") -> int32
    %65 = IntLiteral(1, int32)
    %66 = BinaryOp("==", %64, %65)
    Branch(%66, block_21, block_20)

  block_20:
    %67 = LoadVar("arg") -> string
    %68 = StringLiteral("=", string)
    %69 = Call(str_index_of, [%67, %68], ["borrow", "borrow"]) -> int32
    %70 = IntLiteral(0, int32)
    %71 = BinaryOp(">=", %69, %70)
    Branch(%71, block_25, block_24)

  block_21:
    %72 = LoadVar("logical_pos") -> int32
    %73 = LoadVar("index") -> int32
    %74 = BinaryOp("==", %72, %73)
    Branch(%74, block_23, block_22)

  block_22:
    %75 = LoadVar("logical_pos") -> int32
    %76 = IntLiteral(1, int32)
    %77 = BinaryOp("+", %75, %76)
    StoreVar("logical_pos", %77)
    %78 = LoadVar("i") -> int32
    %79 = IntLiteral(1, int32)
    %80 = BinaryOp("+", %78, %79)
    StoreVar("i", %80)
    %81 = LoadVar("arg") -> string
    Drop(%81)
    Jump(block_3)

  block_23:
    %82 = LoadVar("fallback") -> string
    Drop(%82)
    %83 = LoadVar("arg") -> string
    Return(%83)

  block_24:
    %84 = LoadVar("n") -> int32
    %85 = IntLiteral(2, int32)
    %86 = BinaryOp("==", %84, %85)
    Branch(%86, block_27, block_26)

  block_25:
    %87 = LoadVar("i") -> int32
    %88 = IntLiteral(1, int32)
    %89 = BinaryOp("+", %87, %88)
    StoreVar("i", %89)
    %90 = LoadVar("arg") -> string
    Drop(%90)
    Jump(block_3)

  block_26:
    %91 = LoadVar("i") -> int32
    %92 = IntLiteral(1, int32)
    %93 = BinaryOp("+", %91, %92)
    StoreVar("i", %93)
    %94 = LoadVar("arg") -> string
    Drop(%94)
    Jump(block_3)

  block_27:
    %95 = LoadVar("i") -> int32
    %96 = IntLiteral(1, int32)
    %97 = BinaryOp("+", %95, %96)
    DeclareLocal("next__2", int32, %97)
    %98 = LoadVar("next__2") -> int32
    %99 = Call(argc, [], []) -> int32
    %100 = BinaryOp("<", %98, %99)
    Branch(%100, block_29, block_28)

  block_28:
    %101 = LoadVar("i") -> int32
    %102 = IntLiteral(1, int32)
    %103 = BinaryOp("+", %101, %102)
    StoreVar("i", %103)
    %104 = LoadVar("arg") -> string
    Drop(%104)
    Jump(block_3)

  block_29:
    %105 = LoadVar("next__2") -> int32
    %106 = Call(argv_at, [%105], ["own"]) -> string
    DeclareLocal("next_value__2", string, %106)
    %107 = LoadVar("next_value__2") -> string
    %108 = Call(_looks_like_option_token, [%107], ["borrow"]) -> bool
    %109 = BoolLiteral(false, bool)
    %110 = BinaryOp("==", %108, %109)
    Branch(%110, block_31, block_30)

  block_30:
    %111 = LoadVar("next_value__2") -> string
    Drop(%111)
    Jump(block_28)

  block_31:
    %112 = LoadVar("i") -> int32
    %113 = IntLiteral(2, int32)
    %114 = BinaryOp("+", %112, %113)
    StoreVar("i", %114)
    %115 = LoadVar("next_value__2") -> string
    Drop(%115)
    %116 = LoadVar("arg") -> string
    Drop(%116)
    Jump(block_3)

  block_32:
    %117 = LoadVar("arg") -> string
    Drop(%117)
    %118 = LoadVar("logical_pos") -> int32
    %119 = IntLiteral(1, int32)
    %120 = BinaryOp("+", %118, %119)
    StoreVar("logical_pos", %120)
    %121 = LoadVar("i") -> int32
    %122 = IntLiteral(1, int32)
    %123 = BinaryOp("+", %121, %122)
    StoreVar("i", %123)
    Jump(block_3)

  block_33:
    %124 = LoadVar("fallback") -> string
    Drop(%124)
    %125 = LoadVar("arg") -> string
    Return(%125)
}

function main() -> void {
  block_0:
    %0 = Call(argc, [], []) -> int32
    DeclareLocal("count", int32, %0)
    %1 = LoadVar("count") -> int32
    %2 = IntLiteral(1, int32)
    %3 = BinaryOp(">=", %1, %2)
    Call(println, [%3], ["borrow"])
    %4 = IntLiteral(0, int32)
    %5 = Call(argv_at, [%4], ["own"]) -> string
    %6 = StringLiteral("", string)
    %7 = BinaryOp("!=", %5, %6)
    Call(println, [%7], ["borrow"])
    %8 = IntLiteral(1, int32)
    %9 = UnaryOp("-", %8)
    %10 = Call(argv_at, [%9], ["own"]) -> string
    %11 = StringLiteral("", string)
    %12 = BinaryOp("==", %10, %11)
    Call(println, [%12], ["borrow"])
    %13 = IntLiteral(9999, int32)
    %14 = Call(argv_at, [%13], ["own"]) -> string
    %15 = StringLiteral("", string)
    %16 = BinaryOp("==", %14, %15)
    Call(println, [%16], ["borrow"])
    Return()
}

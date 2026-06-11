module std_cli_args_basic

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

function argc() -> int32 {
  block_0:
    %0 = Call(process_argc, [], []) -> int32
    Return(%0)
}

function argv_at(index: int32) -> string {
  block_0:
    %0 = LoadVar("index") -> int32
    %1 = Call(process_argv_at, [%0], ["own"]) -> string
    Return(%1)
}

function _starts_with(value: &string, prefix: &string) -> bool {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = LoadVar("prefix") -> string
    %2 = Call(str_index_of, [%0, %1], ["own", "own"]) -> int32
    %3 = IntLiteral(0, int32)
    %4 = BinaryOp("==", %2, %3)
    Return(%4)
}

function _str_len(value: &string) -> int32 {
  block_0:
    %0 = LoadVar("value") -> string
    %1 = Call(str_length, [%0], ["own"]) -> int32
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
    %16 = Call(str_index_of, [%14, %15], ["own", "own"]) -> int32
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
    %12 = Call(str_char_at, [%10, %11], ["own", "own"]) -> string
    DeclareLocal("ch", string, %12)
    %13 = LoadVar("ch") -> string
    %14 = LoadVar("short_name") -> string
    %15 = BinaryOp("==", %13, %14)
    Branch(%15, block_7, block_6)

  block_5:
    %16 = BoolLiteral(false, bool)
    Return(%16)

  block_6:
    %17 = LoadVar("i") -> int32
    %18 = IntLiteral(1, int32)
    %19 = BinaryOp("+", %17, %18)
    StoreVar("i", %19)
    Jump(block_3)

  block_7:
    %20 = LoadVar("ch") -> string
    Drop(%20)
    %21 = BoolLiteral(true, bool)
    Return(%21)
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
    %15 = BoolLiteral(false, bool)
    Return(%15)

  block_4:
    %16 = LoadVar("arg") -> string
    %17 = LoadVar("short_flag") -> string
    %18 = BinaryOp("==", %16, %17)
    Branch(%18, block_7, block_6)

  block_5:
    %19 = LoadVar("short_flag") -> string
    Drop(%19)
    %20 = LoadVar("long_flag") -> string
    Drop(%20)
    %21 = LoadVar("arg") -> string
    Drop(%21)
    %22 = BoolLiteral(false, bool)
    Return(%22)

  block_6:
    %23 = LoadVar("arg") -> string
    %24 = LoadVar("long_flag") -> string
    %25 = BinaryOp("==", %23, %24)
    Branch(%25, block_9, block_8)

  block_7:
    %26 = BoolLiteral(true, bool)
    Return(%26)

  block_8:
    %27 = LoadVar("arg") -> string
    %28 = Call(_is_grouped_short_token, [%27], ["borrow"]) -> bool
    Branch(%28, block_11, block_10)

  block_9:
    %29 = BoolLiteral(true, bool)
    Return(%29)

  block_10:
    %30 = LoadVar("i") -> int32
    %31 = IntLiteral(1, int32)
    %32 = BinaryOp("+", %30, %31)
    StoreVar("i", %32)
    Jump(block_1)

  block_11:
    %33 = LoadVar("arg") -> string
    %34 = LoadVar("name") -> string
    %35 = Call(_group_has_short, [%33, %34], ["borrow", "borrow"]) -> bool
    Branch(%35, block_13, block_12)

  block_12:
    Jump(block_10)

  block_13:
    %36 = BoolLiteral(true, bool)
    Return(%36)
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
    %15 = BoolLiteral(false, bool)
    Return(%15)

  block_4:
    %16 = LoadVar("arg") -> string
    %17 = LoadVar("short_flag") -> string
    %18 = BinaryOp("==", %16, %17)
    Branch(%18, block_7, block_6)

  block_5:
    %19 = LoadVar("short_flag") -> string
    Drop(%19)
    %20 = LoadVar("long_flag") -> string
    Drop(%20)
    %21 = LoadVar("arg") -> string
    Drop(%21)
    %22 = BoolLiteral(false, bool)
    Return(%22)

  block_6:
    %23 = LoadVar("arg") -> string
    %24 = LoadVar("long_flag") -> string
    %25 = BinaryOp("==", %23, %24)
    Branch(%25, block_9, block_8)

  block_7:
    %26 = BoolLiteral(true, bool)
    Return(%26)

  block_8:
    %27 = LoadVar("arg") -> string
    %28 = Call(_is_grouped_short_token, [%27], ["borrow"]) -> bool
    Branch(%28, block_11, block_10)

  block_9:
    %29 = BoolLiteral(true, bool)
    Return(%29)

  block_10:
    %30 = LoadVar("i") -> int32
    %31 = IntLiteral(1, int32)
    %32 = BinaryOp("+", %30, %31)
    StoreVar("i", %32)
    Jump(block_1)

  block_11:
    %33 = LoadVar("arg") -> string
    %34 = LoadVar("short_name") -> string
    %35 = Call(_group_has_short, [%33, %34], ["borrow", "borrow"]) -> bool
    Branch(%35, block_13, block_12)

  block_12:
    Jump(block_10)

  block_13:
    %36 = BoolLiteral(true, bool)
    Return(%36)
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
    %2 = Call(str_index_of, [%0, %1], ["own", "own"]) -> int32
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
    %13 = Call(str_slice, [%9, %10, %12], ["own", "own", "own"]) -> string
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
    %21 = LoadVar("fallback") -> string
    Return(%21)

  block_4:
    %22 = LoadVar("arg") -> string
    %23 = LoadVar("short_flag") -> string
    %24 = BinaryOp("==", %22, %23)
    Branch(%24, block_7, block_6)

  block_5:
    %25 = LoadVar("short_flag") -> string
    Drop(%25)
    %26 = LoadVar("long_flag") -> string
    Drop(%26)
    %27 = LoadVar("short_eq") -> string
    Drop(%27)
    %28 = LoadVar("long_eq") -> string
    Drop(%28)
    %29 = LoadVar("arg") -> string
    Drop(%29)
    %30 = LoadVar("fallback") -> string
    Return(%30)

  block_6:
    %31 = LoadVar("arg") -> string
    %32 = LoadVar("long_flag") -> string
    %33 = BinaryOp("==", %31, %32)
    Branch(%33, block_13, block_12)

  block_7:
    %34 = LoadVar("i") -> int32
    %35 = IntLiteral(1, int32)
    %36 = BinaryOp("+", %34, %35)
    DeclareLocal("next", int32, %36)
    %37 = LoadVar("next") -> int32
    %38 = Call(argc, [], []) -> int32
    %39 = BinaryOp("<", %37, %38)
    Branch(%39, block_9, block_8)

  block_8:
    %40 = LoadVar("i") -> int32
    %41 = IntLiteral(1, int32)
    %42 = BinaryOp("+", %40, %41)
    StoreVar("i", %42)
    Jump(block_1)

  block_9:
    %43 = LoadVar("next") -> int32
    %44 = Call(argv_at, [%43], ["own"]) -> string
    DeclareLocal("next_value", string, %44)
    %45 = LoadVar("next_value") -> string
    %46 = Call(_looks_like_option_token, [%45], ["borrow"]) -> bool
    %47 = BoolLiteral(false, bool)
    %48 = BinaryOp("==", %46, %47)
    Branch(%48, block_11, block_10)

  block_10:
    Jump(block_8)

  block_11:
    %49 = LoadVar("next_value") -> string
    Return(%49)

  block_12:
    %50 = LoadVar("arg") -> string
    %51 = LoadVar("short_eq") -> string
    %52 = Call(_starts_with, [%50, %51], ["borrow", "borrow"]) -> bool
    Branch(%52, block_19, block_18)

  block_13:
    %53 = LoadVar("i") -> int32
    %54 = IntLiteral(1, int32)
    %55 = BinaryOp("+", %53, %54)
    DeclareLocal("next__2", int32, %55)
    %56 = LoadVar("next__2") -> int32
    %57 = Call(argc, [], []) -> int32
    %58 = BinaryOp("<", %56, %57)
    Branch(%58, block_15, block_14)

  block_14:
    %59 = LoadVar("i") -> int32
    %60 = IntLiteral(1, int32)
    %61 = BinaryOp("+", %59, %60)
    StoreVar("i", %61)
    Jump(block_1)

  block_15:
    %62 = LoadVar("next__2") -> int32
    %63 = Call(argv_at, [%62], ["own"]) -> string
    DeclareLocal("next_value__2", string, %63)
    %64 = LoadVar("next_value__2") -> string
    %65 = Call(_looks_like_option_token, [%64], ["borrow"]) -> bool
    %66 = BoolLiteral(false, bool)
    %67 = BinaryOp("==", %65, %66)
    Branch(%67, block_17, block_16)

  block_16:
    Jump(block_14)

  block_17:
    %68 = LoadVar("next_value__2") -> string
    Return(%68)

  block_18:
    %69 = LoadVar("arg") -> string
    %70 = LoadVar("long_eq") -> string
    %71 = Call(_starts_with, [%69, %70], ["borrow", "borrow"]) -> bool
    Branch(%71, block_21, block_20)

  block_19:
    %72 = LoadVar("arg") -> string
    %73 = Call(_value_after_equals, [%72], ["borrow"]) -> string
    Return(%73)

  block_20:
    %74 = LoadVar("i") -> int32
    %75 = IntLiteral(1, int32)
    %76 = BinaryOp("+", %74, %75)
    StoreVar("i", %76)
    Jump(block_1)

  block_21:
    %77 = LoadVar("arg") -> string
    %78 = Call(_value_after_equals, [%77], ["borrow"]) -> string
    Return(%78)
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
    %21 = LoadVar("fallback") -> string
    Return(%21)

  block_4:
    %22 = LoadVar("arg") -> string
    %23 = LoadVar("short_flag") -> string
    %24 = BinaryOp("==", %22, %23)
    Branch(%24, block_7, block_6)

  block_5:
    %25 = LoadVar("short_flag") -> string
    Drop(%25)
    %26 = LoadVar("long_flag") -> string
    Drop(%26)
    %27 = LoadVar("short_eq") -> string
    Drop(%27)
    %28 = LoadVar("long_eq") -> string
    Drop(%28)
    %29 = LoadVar("arg") -> string
    Drop(%29)
    %30 = LoadVar("fallback") -> string
    Return(%30)

  block_6:
    %31 = LoadVar("arg") -> string
    %32 = LoadVar("long_flag") -> string
    %33 = BinaryOp("==", %31, %32)
    Branch(%33, block_13, block_12)

  block_7:
    %34 = LoadVar("i") -> int32
    %35 = IntLiteral(1, int32)
    %36 = BinaryOp("+", %34, %35)
    DeclareLocal("next", int32, %36)
    %37 = LoadVar("next") -> int32
    %38 = Call(argc, [], []) -> int32
    %39 = BinaryOp("<", %37, %38)
    Branch(%39, block_9, block_8)

  block_8:
    %40 = LoadVar("i") -> int32
    %41 = IntLiteral(1, int32)
    %42 = BinaryOp("+", %40, %41)
    StoreVar("i", %42)
    Jump(block_1)

  block_9:
    %43 = LoadVar("next") -> int32
    %44 = Call(argv_at, [%43], ["own"]) -> string
    DeclareLocal("next_value", string, %44)
    %45 = LoadVar("next_value") -> string
    %46 = Call(_looks_like_option_token, [%45], ["borrow"]) -> bool
    %47 = BoolLiteral(false, bool)
    %48 = BinaryOp("==", %46, %47)
    Branch(%48, block_11, block_10)

  block_10:
    Jump(block_8)

  block_11:
    %49 = LoadVar("next_value") -> string
    Return(%49)

  block_12:
    %50 = LoadVar("arg") -> string
    %51 = LoadVar("short_eq") -> string
    %52 = Call(_starts_with, [%50, %51], ["borrow", "borrow"]) -> bool
    Branch(%52, block_19, block_18)

  block_13:
    %53 = LoadVar("i") -> int32
    %54 = IntLiteral(1, int32)
    %55 = BinaryOp("+", %53, %54)
    DeclareLocal("next__2", int32, %55)
    %56 = LoadVar("next__2") -> int32
    %57 = Call(argc, [], []) -> int32
    %58 = BinaryOp("<", %56, %57)
    Branch(%58, block_15, block_14)

  block_14:
    %59 = LoadVar("i") -> int32
    %60 = IntLiteral(1, int32)
    %61 = BinaryOp("+", %59, %60)
    StoreVar("i", %61)
    Jump(block_1)

  block_15:
    %62 = LoadVar("next__2") -> int32
    %63 = Call(argv_at, [%62], ["own"]) -> string
    DeclareLocal("next_value__2", string, %63)
    %64 = LoadVar("next_value__2") -> string
    %65 = Call(_looks_like_option_token, [%64], ["borrow"]) -> bool
    %66 = BoolLiteral(false, bool)
    %67 = BinaryOp("==", %65, %66)
    Branch(%67, block_17, block_16)

  block_16:
    Jump(block_14)

  block_17:
    %68 = LoadVar("next_value__2") -> string
    Return(%68)

  block_18:
    %69 = LoadVar("arg") -> string
    %70 = LoadVar("long_eq") -> string
    %71 = Call(_starts_with, [%69, %70], ["borrow", "borrow"]) -> bool
    Branch(%71, block_21, block_20)

  block_19:
    %72 = LoadVar("arg") -> string
    %73 = Call(_value_after_equals, [%72], ["borrow"]) -> string
    Return(%73)

  block_20:
    %74 = LoadVar("short_name") -> string
    %75 = Call(_str_len, [%74], ["borrow"]) -> int32
    %76 = IntLiteral(1, int32)
    %77 = BinaryOp("==", %75, %76)
    Branch(%77, block_23, block_22)

  block_21:
    %78 = LoadVar("arg") -> string
    %79 = Call(_value_after_equals, [%78], ["borrow"]) -> string
    Return(%79)

  block_22:
    %80 = LoadVar("i") -> int32
    %81 = IntLiteral(1, int32)
    %82 = BinaryOp("+", %80, %81)
    StoreVar("i", %82)
    Jump(block_1)

  block_23:
    %83 = LoadVar("arg") -> string
    %84 = LoadVar("short_flag") -> string
    %85 = Call(_starts_with, [%83, %84], ["borrow", "borrow"]) -> bool
    Branch(%85, block_25, block_24)

  block_24:
    Jump(block_22)

  block_25:
    %86 = LoadVar("arg") -> string
    %87 = Call(_str_len, [%86], ["borrow"]) -> int32
    %88 = IntLiteral(2, int32)
    %89 = BinaryOp(">", %87, %88)
    Branch(%89, block_27, block_26)

  block_26:
    Jump(block_24)

  block_27:
    %90 = LoadVar("arg") -> string
    %91 = IntLiteral(2, int32)
    %92 = LoadVar("arg") -> string
    %93 = Call(_str_len, [%92], ["borrow"]) -> int32
    %94 = Call(str_slice, [%90, %91, %93], ["own", "own", "own"]) -> string
    Return(%94)
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
    %10 = LoadVar("raw_index") -> int32
    %11 = Call(argv_at, [%10], ["own"]) -> string
    Return(%11)

  block_4:
    %12 = LoadVar("fallback") -> string
    Return(%12)
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
    %33 = Call(str_index_of, [%31, %32], ["own", "own"]) -> int32
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
    %69 = Call(str_index_of, [%67, %68], ["own", "own"]) -> int32
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
    Jump(block_3)

  block_23:
    %81 = LoadVar("arg") -> string
    Return(%81)

  block_24:
    %82 = LoadVar("n") -> int32
    %83 = IntLiteral(2, int32)
    %84 = BinaryOp("==", %82, %83)
    Branch(%84, block_27, block_26)

  block_25:
    %85 = LoadVar("i") -> int32
    %86 = IntLiteral(1, int32)
    %87 = BinaryOp("+", %85, %86)
    StoreVar("i", %87)
    Jump(block_3)

  block_26:
    %88 = LoadVar("i") -> int32
    %89 = IntLiteral(1, int32)
    %90 = BinaryOp("+", %88, %89)
    StoreVar("i", %90)
    Jump(block_3)

  block_27:
    %91 = LoadVar("i") -> int32
    %92 = IntLiteral(1, int32)
    %93 = BinaryOp("+", %91, %92)
    DeclareLocal("next__2", int32, %93)
    %94 = LoadVar("next__2") -> int32
    %95 = Call(argc, [], []) -> int32
    %96 = BinaryOp("<", %94, %95)
    Branch(%96, block_29, block_28)

  block_28:
    %97 = LoadVar("i") -> int32
    %98 = IntLiteral(1, int32)
    %99 = BinaryOp("+", %97, %98)
    StoreVar("i", %99)
    Jump(block_3)

  block_29:
    %100 = LoadVar("next__2") -> int32
    %101 = Call(argv_at, [%100], ["own"]) -> string
    DeclareLocal("next_value__2", string, %101)
    %102 = LoadVar("next_value__2") -> string
    %103 = Call(_looks_like_option_token, [%102], ["borrow"]) -> bool
    %104 = BoolLiteral(false, bool)
    %105 = BinaryOp("==", %103, %104)
    Branch(%105, block_31, block_30)

  block_30:
    %106 = LoadVar("next_value__2") -> string
    Drop(%106)
    Jump(block_28)

  block_31:
    %107 = LoadVar("i") -> int32
    %108 = IntLiteral(2, int32)
    %109 = BinaryOp("+", %107, %108)
    StoreVar("i", %109)
    %110 = LoadVar("next_value__2") -> string
    Drop(%110)
    Jump(block_3)

  block_32:
    %111 = LoadVar("logical_pos") -> int32
    %112 = IntLiteral(1, int32)
    %113 = BinaryOp("+", %111, %112)
    StoreVar("logical_pos", %113)
    %114 = LoadVar("i") -> int32
    %115 = IntLiteral(1, int32)
    %116 = BinaryOp("+", %114, %115)
    StoreVar("i", %116)
    Jump(block_3)

  block_33:
    %117 = LoadVar("arg") -> string
    Return(%117)
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

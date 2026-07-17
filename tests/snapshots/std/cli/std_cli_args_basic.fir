fir module std_cli_args_basic

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

function @argc() -> int32 {
  L0:
    %0 = call.int32 @process_argc()
    ret %0
}

function @argv_at(index: int32) -> string {
  L0:
    %0 = loadvar.int32 index
    %1 = call.string @process_argv_at(%0 borrow)
    ret %1
}

function @_starts_with(value: &string, prefix: &string) -> bool {
  L0:
    %0 = loadvar.string value
    %1 = loadvar.string prefix
    %2 = call.int32 @str_index_of(%0 borrow, %1 borrow)
    %3 = const.int32 0
    %4 = binop "==", %2, %3
    ret %4
}

function @_str_len(value: &string) -> int32 {
  L0:
    %0 = loadvar.string value
    %1 = call.int32 @str_length(%0 borrow)
    ret %1
}

function @_is_grouped_short_token(value: &string) -> bool {
  L0:
    %0 = loadvar.string value
    %1 = strconst "-"
    %2 = call.bool @_starts_with(%0 borrow, %1 borrow)
    %3 = bconst false
    %4 = binop "==", %2, %3
    br %4, L2, L1

  L1:
    %5 = loadvar.string value
    %6 = strconst "--"
    %7 = call.bool @_starts_with(%5 borrow, %6 borrow)
    br %7, L4, L3

  L2:
    %8 = bconst false
    ret %8

  L3:
    %9 = loadvar.string value
    %10 = call.int32 @_str_len(%9 borrow)
    %11 = const.int32 2
    %12 = binop "<=", %10, %11
    br %12, L6, L5

  L4:
    %13 = bconst false
    ret %13

  L5:
    %14 = loadvar.string value
    %15 = strconst "="
    %16 = call.int32 @str_index_of(%14 borrow, %15 borrow)
    %17 = const.int32 0
    %18 = binop ">=", %16, %17
    br %18, L8, L7

  L6:
    %19 = bconst false
    ret %19

  L7:
    %20 = bconst true
    ret %20

  L8:
    %21 = bconst false
    ret %21
}

function @_group_has_short(token: &string, short_name: &string) -> bool {
  L0:
    %0 = loadvar.string short_name
    %1 = call.int32 @_str_len(%0 borrow)
    %2 = const.int32 1
    %3 = binop "!=", %1, %2
    br %3, L2, L1

  L1:
    %4 = const.int32 1
    local i: int32 = %4
    jmp L3

  L2:
    %5 = bconst false
    ret %5

  L3:
    %6 = loadvar.int32 i
    %7 = loadvar.string token
    %8 = call.int32 @_str_len(%7 borrow)
    %9 = binop "<", %6, %8
    br %9, L4, L5

  L4:
    %10 = loadvar.string token
    %11 = loadvar.int32 i
    %12 = call.string @str_char_at(%10 borrow, %11 borrow)
    local ch: string = %12
    %13 = loadvar.string ch
    %14 = loadvar.string short_name
    %15 = binop "==", %13, %14
    br %15, L7, L6

  L5:
    %16 = bconst false
    ret %16

  L6:
    %17 = loadvar.string ch
    drop %17
    %18 = loadvar.int32 i
    %19 = const.int32 1
    %20 = binop "+", %18, %19
    storevar i, %20
    jmp L3

  L7:
    %21 = loadvar.string ch
    drop %21
    %22 = bconst true
    ret %22
}

function @has_flag(name: string) -> bool {
  L0:
    %0 = strconst "-"
    %1 = loadvar.string name
    %2 = binop "+", %0, %1
    local short_flag: string = %2
    %3 = strconst "--"
    %4 = loadvar.string name
    %5 = binop "+", %3, %4
    local long_flag: string = %5
    %6 = const.int32 1
    local i: int32 = %6
    jmp L1

  L1:
    %7 = loadvar.int32 i
    %8 = call.int32 @argc()
    %9 = binop "<", %7, %8
    br %9, L2, L3

  L2:
    %10 = loadvar.int32 i
    %11 = call.string @argv_at(%10 own)
    local arg: string = %11
    %12 = loadvar.string arg
    %13 = strconst "--"
    %14 = binop "==", %12, %13
    br %14, L5, L4

  L3:
    %15 = loadvar.string name
    drop %15
    %16 = loadvar.string short_flag
    drop %16
    %17 = loadvar.string long_flag
    drop %17
    %18 = bconst false
    ret %18

  L4:
    %19 = loadvar.string arg
    %20 = loadvar.string short_flag
    %21 = binop "==", %19, %20
    br %21, L7, L6

  L5:
    %22 = loadvar.string name
    drop %22
    %23 = loadvar.string short_flag
    drop %23
    %24 = loadvar.string long_flag
    drop %24
    %25 = loadvar.string arg
    drop %25
    %26 = bconst false
    ret %26

  L6:
    %27 = loadvar.string arg
    %28 = loadvar.string long_flag
    %29 = binop "==", %27, %28
    br %29, L9, L8

  L7:
    %30 = loadvar.string name
    drop %30
    %31 = loadvar.string short_flag
    drop %31
    %32 = loadvar.string long_flag
    drop %32
    %33 = loadvar.string arg
    drop %33
    %34 = bconst true
    ret %34

  L8:
    %35 = loadvar.string arg
    %36 = call.bool @_is_grouped_short_token(%35 borrow)
    br %36, L11, L10

  L9:
    %37 = loadvar.string name
    drop %37
    %38 = loadvar.string short_flag
    drop %38
    %39 = loadvar.string long_flag
    drop %39
    %40 = loadvar.string arg
    drop %40
    %41 = bconst true
    ret %41

  L10:
    %42 = loadvar.string arg
    drop %42
    %43 = loadvar.int32 i
    %44 = const.int32 1
    %45 = binop "+", %43, %44
    storevar i, %45
    jmp L1

  L11:
    %46 = loadvar.string arg
    %47 = loadvar.string name
    %48 = call.bool @_group_has_short(%46 borrow, %47 borrow)
    br %48, L13, L12

  L12:
    jmp L10

  L13:
    %49 = loadvar.string name
    drop %49
    %50 = loadvar.string short_flag
    drop %50
    %51 = loadvar.string long_flag
    drop %51
    %52 = loadvar.string arg
    drop %52
    %53 = bconst true
    ret %53
}

function @has_flag_alias(long_name: string, short_name: string) -> bool {
  L0:
    %0 = strconst "-"
    %1 = loadvar.string short_name
    %2 = binop "+", %0, %1
    local short_flag: string = %2
    %3 = strconst "--"
    %4 = loadvar.string long_name
    %5 = binop "+", %3, %4
    local long_flag: string = %5
    %6 = const.int32 1
    local i: int32 = %6
    jmp L1

  L1:
    %7 = loadvar.int32 i
    %8 = call.int32 @argc()
    %9 = binop "<", %7, %8
    br %9, L2, L3

  L2:
    %10 = loadvar.int32 i
    %11 = call.string @argv_at(%10 own)
    local arg: string = %11
    %12 = loadvar.string arg
    %13 = strconst "--"
    %14 = binop "==", %12, %13
    br %14, L5, L4

  L3:
    %15 = loadvar.string long_name
    drop %15
    %16 = loadvar.string short_name
    drop %16
    %17 = loadvar.string short_flag
    drop %17
    %18 = loadvar.string long_flag
    drop %18
    %19 = bconst false
    ret %19

  L4:
    %20 = loadvar.string arg
    %21 = loadvar.string short_flag
    %22 = binop "==", %20, %21
    br %22, L7, L6

  L5:
    %23 = loadvar.string long_name
    drop %23
    %24 = loadvar.string short_name
    drop %24
    %25 = loadvar.string short_flag
    drop %25
    %26 = loadvar.string long_flag
    drop %26
    %27 = loadvar.string arg
    drop %27
    %28 = bconst false
    ret %28

  L6:
    %29 = loadvar.string arg
    %30 = loadvar.string long_flag
    %31 = binop "==", %29, %30
    br %31, L9, L8

  L7:
    %32 = loadvar.string long_name
    drop %32
    %33 = loadvar.string short_name
    drop %33
    %34 = loadvar.string short_flag
    drop %34
    %35 = loadvar.string long_flag
    drop %35
    %36 = loadvar.string arg
    drop %36
    %37 = bconst true
    ret %37

  L8:
    %38 = loadvar.string arg
    %39 = call.bool @_is_grouped_short_token(%38 borrow)
    br %39, L11, L10

  L9:
    %40 = loadvar.string long_name
    drop %40
    %41 = loadvar.string short_name
    drop %41
    %42 = loadvar.string short_flag
    drop %42
    %43 = loadvar.string long_flag
    drop %43
    %44 = loadvar.string arg
    drop %44
    %45 = bconst true
    ret %45

  L10:
    %46 = loadvar.string arg
    drop %46
    %47 = loadvar.int32 i
    %48 = const.int32 1
    %49 = binop "+", %47, %48
    storevar i, %49
    jmp L1

  L11:
    %50 = loadvar.string arg
    %51 = loadvar.string short_name
    %52 = call.bool @_group_has_short(%50 borrow, %51 borrow)
    br %52, L13, L12

  L12:
    jmp L10

  L13:
    %53 = loadvar.string long_name
    drop %53
    %54 = loadvar.string short_name
    drop %54
    %55 = loadvar.string short_flag
    drop %55
    %56 = loadvar.string long_flag
    drop %56
    %57 = loadvar.string arg
    drop %57
    %58 = bconst true
    ret %58
}

function @_looks_like_option_token(value: &string) -> bool {
  L0:
    %0 = loadvar.string value
    %1 = strconst "-"
    %2 = binop "==", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.string value
    %4 = strconst "-"
    %5 = call.bool @_starts_with(%3 borrow, %4 borrow)
    %6 = bconst true
    %7 = binop "==", %5, %6
    ret %7

  L2:
    %8 = bconst false
    ret %8
}

function @_value_after_equals(token: &string) -> string {
  L0:
    %0 = loadvar.string token
    %1 = strconst "="
    %2 = call.int32 @str_index_of(%0 borrow, %1 borrow)
    local eq: int32 = %2
    %3 = loadvar.int32 eq
    %4 = const.int32 0
    %5 = binop "<", %3, %4
    br %5, L2, L1

  L1:
    %6 = loadvar.int32 eq
    %7 = const.int32 1
    %8 = binop "+", %6, %7
    local start: int32 = %8
    %9 = loadvar.string token
    %10 = loadvar.int32 start
    %11 = loadvar.string token
    %12 = call.int32 @_str_len(%11 borrow)
    %13 = call.string @str_slice(%9 borrow, %10 borrow, %12 borrow)
    ret %13

  L2:
    %14 = strconst ""
    ret %14
}

function @option_value(name: string, fallback: string) -> string {
  L0:
    %0 = strconst "-"
    %1 = loadvar.string name
    %2 = binop "+", %0, %1
    local short_flag: string = %2
    %3 = strconst "--"
    %4 = loadvar.string name
    %5 = binop "+", %3, %4
    local long_flag: string = %5
    %6 = loadvar.string short_flag
    %7 = strconst "="
    %8 = binop "+", %6, %7
    local short_eq: string = %8
    %9 = loadvar.string long_flag
    %10 = strconst "="
    %11 = binop "+", %9, %10
    local long_eq: string = %11
    %12 = const.int32 1
    local i: int32 = %12
    jmp L1

  L1:
    %13 = loadvar.int32 i
    %14 = call.int32 @argc()
    %15 = binop "<", %13, %14
    br %15, L2, L3

  L2:
    %16 = loadvar.int32 i
    %17 = call.string @argv_at(%16 own)
    local arg: string = %17
    %18 = loadvar.string arg
    %19 = strconst "--"
    %20 = binop "==", %18, %19
    br %20, L5, L4

  L3:
    %21 = loadvar.string name
    drop %21
    %22 = loadvar.string short_flag
    drop %22
    %23 = loadvar.string long_flag
    drop %23
    %24 = loadvar.string short_eq
    drop %24
    %25 = loadvar.string long_eq
    drop %25
    %26 = loadvar.string fallback
    ret %26

  L4:
    %27 = loadvar.string arg
    %28 = loadvar.string short_flag
    %29 = binop "==", %27, %28
    br %29, L7, L6

  L5:
    %30 = loadvar.string name
    drop %30
    %31 = loadvar.string short_flag
    drop %31
    %32 = loadvar.string long_flag
    drop %32
    %33 = loadvar.string short_eq
    drop %33
    %34 = loadvar.string long_eq
    drop %34
    %35 = loadvar.string arg
    drop %35
    %36 = loadvar.string fallback
    ret %36

  L6:
    %37 = loadvar.string arg
    %38 = loadvar.string long_flag
    %39 = binop "==", %37, %38
    br %39, L13, L12

  L7:
    %40 = loadvar.int32 i
    %41 = const.int32 1
    %42 = binop "+", %40, %41
    local next: int32 = %42
    %43 = loadvar.int32 next
    %44 = call.int32 @argc()
    %45 = binop "<", %43, %44
    br %45, L9, L8

  L8:
    %46 = loadvar.int32 i
    %47 = const.int32 1
    %48 = binop "+", %46, %47
    storevar i, %48
    %49 = loadvar.string arg
    drop %49
    jmp L1

  L9:
    %50 = loadvar.int32 next
    %51 = call.string @argv_at(%50 own)
    local next_value: string = %51
    %52 = loadvar.string next_value
    %53 = call.bool @_looks_like_option_token(%52 borrow)
    %54 = bconst false
    %55 = binop "==", %53, %54
    br %55, L11, L10

  L10:
    %56 = loadvar.string next_value
    drop %56
    jmp L8

  L11:
    %57 = loadvar.string name
    drop %57
    %58 = loadvar.string fallback
    drop %58
    %59 = loadvar.string short_flag
    drop %59
    %60 = loadvar.string long_flag
    drop %60
    %61 = loadvar.string short_eq
    drop %61
    %62 = loadvar.string long_eq
    drop %62
    %63 = loadvar.string arg
    drop %63
    %64 = loadvar.string next_value
    ret %64

  L12:
    %65 = loadvar.string arg
    %66 = loadvar.string short_eq
    %67 = call.bool @_starts_with(%65 borrow, %66 borrow)
    br %67, L19, L18

  L13:
    %68 = loadvar.int32 i
    %69 = const.int32 1
    %70 = binop "+", %68, %69
    local next__2: int32 = %70
    %71 = loadvar.int32 next__2
    %72 = call.int32 @argc()
    %73 = binop "<", %71, %72
    br %73, L15, L14

  L14:
    %74 = loadvar.int32 i
    %75 = const.int32 1
    %76 = binop "+", %74, %75
    storevar i, %76
    %77 = loadvar.string arg
    drop %77
    jmp L1

  L15:
    %78 = loadvar.int32 next__2
    %79 = call.string @argv_at(%78 own)
    local next_value__2: string = %79
    %80 = loadvar.string next_value__2
    %81 = call.bool @_looks_like_option_token(%80 borrow)
    %82 = bconst false
    %83 = binop "==", %81, %82
    br %83, L17, L16

  L16:
    %84 = loadvar.string next_value__2
    drop %84
    jmp L14

  L17:
    %85 = loadvar.string name
    drop %85
    %86 = loadvar.string fallback
    drop %86
    %87 = loadvar.string short_flag
    drop %87
    %88 = loadvar.string long_flag
    drop %88
    %89 = loadvar.string short_eq
    drop %89
    %90 = loadvar.string long_eq
    drop %90
    %91 = loadvar.string arg
    drop %91
    %92 = loadvar.string next_value__2
    ret %92

  L18:
    %93 = loadvar.string arg
    %94 = loadvar.string long_eq
    %95 = call.bool @_starts_with(%93 borrow, %94 borrow)
    br %95, L21, L20

  L19:
    %96 = loadvar.string arg
    %97 = call.string @_value_after_equals(%96 borrow)
    local result: string = %97
    %98 = loadvar.string arg
    drop %98
    %99 = loadvar.string name
    drop %99
    %100 = loadvar.string fallback
    drop %100
    %101 = loadvar.string short_flag
    drop %101
    %102 = loadvar.string long_flag
    drop %102
    %103 = loadvar.string short_eq
    drop %103
    %104 = loadvar.string long_eq
    drop %104
    %105 = loadvar.string result
    ret %105

  L20:
    %106 = loadvar.string arg
    drop %106
    %107 = loadvar.int32 i
    %108 = const.int32 1
    %109 = binop "+", %107, %108
    storevar i, %109
    jmp L1

  L21:
    %110 = loadvar.string arg
    %111 = call.string @_value_after_equals(%110 borrow)
    local result__2: string = %111
    %112 = loadvar.string arg
    drop %112
    %113 = loadvar.string name
    drop %113
    %114 = loadvar.string fallback
    drop %114
    %115 = loadvar.string short_flag
    drop %115
    %116 = loadvar.string long_flag
    drop %116
    %117 = loadvar.string short_eq
    drop %117
    %118 = loadvar.string long_eq
    drop %118
    %119 = loadvar.string result__2
    ret %119
}

function @option_value_alias(long_name: string, short_name: string, fallback: string) -> string {
  L0:
    %0 = strconst "-"
    %1 = loadvar.string short_name
    %2 = binop "+", %0, %1
    local short_flag: string = %2
    %3 = strconst "--"
    %4 = loadvar.string long_name
    %5 = binop "+", %3, %4
    local long_flag: string = %5
    %6 = loadvar.string short_flag
    %7 = strconst "="
    %8 = binop "+", %6, %7
    local short_eq: string = %8
    %9 = loadvar.string long_flag
    %10 = strconst "="
    %11 = binop "+", %9, %10
    local long_eq: string = %11
    %12 = const.int32 1
    local i: int32 = %12
    jmp L1

  L1:
    %13 = loadvar.int32 i
    %14 = call.int32 @argc()
    %15 = binop "<", %13, %14
    br %15, L2, L3

  L2:
    %16 = loadvar.int32 i
    %17 = call.string @argv_at(%16 own)
    local arg: string = %17
    %18 = loadvar.string arg
    %19 = strconst "--"
    %20 = binop "==", %18, %19
    br %20, L5, L4

  L3:
    %21 = loadvar.string long_name
    drop %21
    %22 = loadvar.string short_name
    drop %22
    %23 = loadvar.string short_flag
    drop %23
    %24 = loadvar.string long_flag
    drop %24
    %25 = loadvar.string short_eq
    drop %25
    %26 = loadvar.string long_eq
    drop %26
    %27 = loadvar.string fallback
    ret %27

  L4:
    %28 = loadvar.string arg
    %29 = loadvar.string short_flag
    %30 = binop "==", %28, %29
    br %30, L7, L6

  L5:
    %31 = loadvar.string long_name
    drop %31
    %32 = loadvar.string short_name
    drop %32
    %33 = loadvar.string short_flag
    drop %33
    %34 = loadvar.string long_flag
    drop %34
    %35 = loadvar.string short_eq
    drop %35
    %36 = loadvar.string long_eq
    drop %36
    %37 = loadvar.string arg
    drop %37
    %38 = loadvar.string fallback
    ret %38

  L6:
    %39 = loadvar.string arg
    %40 = loadvar.string long_flag
    %41 = binop "==", %39, %40
    br %41, L13, L12

  L7:
    %42 = loadvar.int32 i
    %43 = const.int32 1
    %44 = binop "+", %42, %43
    local next: int32 = %44
    %45 = loadvar.int32 next
    %46 = call.int32 @argc()
    %47 = binop "<", %45, %46
    br %47, L9, L8

  L8:
    %48 = loadvar.int32 i
    %49 = const.int32 1
    %50 = binop "+", %48, %49
    storevar i, %50
    %51 = loadvar.string arg
    drop %51
    jmp L1

  L9:
    %52 = loadvar.int32 next
    %53 = call.string @argv_at(%52 own)
    local next_value: string = %53
    %54 = loadvar.string next_value
    %55 = call.bool @_looks_like_option_token(%54 borrow)
    %56 = bconst false
    %57 = binop "==", %55, %56
    br %57, L11, L10

  L10:
    %58 = loadvar.string next_value
    drop %58
    jmp L8

  L11:
    %59 = loadvar.string long_name
    drop %59
    %60 = loadvar.string short_name
    drop %60
    %61 = loadvar.string fallback
    drop %61
    %62 = loadvar.string short_flag
    drop %62
    %63 = loadvar.string long_flag
    drop %63
    %64 = loadvar.string short_eq
    drop %64
    %65 = loadvar.string long_eq
    drop %65
    %66 = loadvar.string arg
    drop %66
    %67 = loadvar.string next_value
    ret %67

  L12:
    %68 = loadvar.string arg
    %69 = loadvar.string short_eq
    %70 = call.bool @_starts_with(%68 borrow, %69 borrow)
    br %70, L19, L18

  L13:
    %71 = loadvar.int32 i
    %72 = const.int32 1
    %73 = binop "+", %71, %72
    local next__2: int32 = %73
    %74 = loadvar.int32 next__2
    %75 = call.int32 @argc()
    %76 = binop "<", %74, %75
    br %76, L15, L14

  L14:
    %77 = loadvar.int32 i
    %78 = const.int32 1
    %79 = binop "+", %77, %78
    storevar i, %79
    %80 = loadvar.string arg
    drop %80
    jmp L1

  L15:
    %81 = loadvar.int32 next__2
    %82 = call.string @argv_at(%81 own)
    local next_value__2: string = %82
    %83 = loadvar.string next_value__2
    %84 = call.bool @_looks_like_option_token(%83 borrow)
    %85 = bconst false
    %86 = binop "==", %84, %85
    br %86, L17, L16

  L16:
    %87 = loadvar.string next_value__2
    drop %87
    jmp L14

  L17:
    %88 = loadvar.string long_name
    drop %88
    %89 = loadvar.string short_name
    drop %89
    %90 = loadvar.string fallback
    drop %90
    %91 = loadvar.string short_flag
    drop %91
    %92 = loadvar.string long_flag
    drop %92
    %93 = loadvar.string short_eq
    drop %93
    %94 = loadvar.string long_eq
    drop %94
    %95 = loadvar.string arg
    drop %95
    %96 = loadvar.string next_value__2
    ret %96

  L18:
    %97 = loadvar.string arg
    %98 = loadvar.string long_eq
    %99 = call.bool @_starts_with(%97 borrow, %98 borrow)
    br %99, L21, L20

  L19:
    %100 = loadvar.string arg
    %101 = call.string @_value_after_equals(%100 borrow)
    local result: string = %101
    %102 = loadvar.string arg
    drop %102
    %103 = loadvar.string long_name
    drop %103
    %104 = loadvar.string short_name
    drop %104
    %105 = loadvar.string fallback
    drop %105
    %106 = loadvar.string short_flag
    drop %106
    %107 = loadvar.string long_flag
    drop %107
    %108 = loadvar.string short_eq
    drop %108
    %109 = loadvar.string long_eq
    drop %109
    %110 = loadvar.string result
    ret %110

  L20:
    %111 = loadvar.string short_name
    %112 = call.int32 @_str_len(%111 borrow)
    %113 = const.int32 1
    %114 = binop "==", %112, %113
    br %114, L23, L22

  L21:
    %115 = loadvar.string arg
    %116 = call.string @_value_after_equals(%115 borrow)
    local result__2: string = %116
    %117 = loadvar.string arg
    drop %117
    %118 = loadvar.string long_name
    drop %118
    %119 = loadvar.string short_name
    drop %119
    %120 = loadvar.string fallback
    drop %120
    %121 = loadvar.string short_flag
    drop %121
    %122 = loadvar.string long_flag
    drop %122
    %123 = loadvar.string short_eq
    drop %123
    %124 = loadvar.string long_eq
    drop %124
    %125 = loadvar.string result__2
    ret %125

  L22:
    %126 = loadvar.string arg
    drop %126
    %127 = loadvar.int32 i
    %128 = const.int32 1
    %129 = binop "+", %127, %128
    storevar i, %129
    jmp L1

  L23:
    %130 = loadvar.string arg
    %131 = loadvar.string short_flag
    %132 = call.bool @_starts_with(%130 borrow, %131 borrow)
    br %132, L25, L24

  L24:
    jmp L22

  L25:
    %133 = loadvar.string arg
    %134 = call.int32 @_str_len(%133 borrow)
    %135 = const.int32 2
    %136 = binop ">", %134, %135
    br %136, L27, L26

  L26:
    jmp L24

  L27:
    %137 = loadvar.string arg
    %138 = const.int32 2
    %139 = loadvar.string arg
    %140 = call.int32 @_str_len(%139 borrow)
    %141 = call.string @str_slice(%137 borrow, %138 borrow, %140 borrow)
    local result__3: string = %141
    %142 = loadvar.string arg
    drop %142
    %143 = loadvar.string long_name
    drop %143
    %144 = loadvar.string short_name
    drop %144
    %145 = loadvar.string fallback
    drop %145
    %146 = loadvar.string short_flag
    drop %146
    %147 = loadvar.string long_flag
    drop %147
    %148 = loadvar.string short_eq
    drop %148
    %149 = loadvar.string long_eq
    drop %149
    %150 = loadvar.string result__3
    ret %150
}

function @positional(index: int32, fallback: string) -> string {
  L0:
    %0 = loadvar.int32 index
    %1 = const.int32 1
    %2 = binop "+", %0, %1
    local raw_index: int32 = %2
    %3 = loadvar.int32 raw_index
    %4 = const.int32 1
    %5 = binop "<", %3, %4
    br %5, L2, L1

  L1:
    %6 = loadvar.int32 raw_index
    %7 = call.int32 @argc()
    %8 = binop ">=", %6, %7
    br %8, L4, L3

  L2:
    %9 = loadvar.string fallback
    ret %9

  L3:
    %10 = loadvar.string fallback
    drop %10
    %11 = loadvar.int32 raw_index
    %12 = call.string @argv_at(%11 own)
    ret %12

  L4:
    %13 = loadvar.string fallback
    ret %13
}

function @positional_value(index: int32, fallback: string) -> string {
  L0:
    %0 = loadvar.int32 index
    %1 = const.int32 0
    %2 = binop "<", %0, %1
    br %2, L2, L1

  L1:
    %3 = const.int32 0
    local logical_pos: int32 = %3
    %4 = const.int32 1
    local i: int32 = %4
    %5 = bconst true
    local parsing_options: bool = %5
    jmp L3

  L2:
    %6 = loadvar.string fallback
    ret %6

  L3:
    %7 = loadvar.int32 i
    %8 = call.int32 @argc()
    %9 = binop "<", %7, %8
    br %9, L4, L5

  L4:
    %10 = loadvar.int32 i
    %11 = call.string @argv_at(%10 own)
    local arg: string = %11
    %12 = loadvar.bool parsing_options
    br %12, L7, L6

  L5:
    %13 = loadvar.string fallback
    ret %13

  L6:
    %14 = loadvar.int32 logical_pos
    %15 = loadvar.int32 index
    %16 = binop "==", %14, %15
    br %16, L33, L32

  L7:
    %17 = loadvar.string arg
    %18 = strconst "--"
    %19 = binop "==", %17, %18
    br %19, L9, L8

  L8:
    %20 = loadvar.string arg
    %21 = strconst "--"
    %22 = call.bool @_starts_with(%20 borrow, %21 borrow)
    br %22, L11, L10

  L9:
    %23 = bconst false
    storevar parsing_options, %23
    %24 = loadvar.int32 i
    %25 = const.int32 1
    %26 = binop "+", %24, %25
    storevar i, %26
    %27 = loadvar.string arg
    drop %27
    jmp L3

  L10:
    %28 = loadvar.string arg
    %29 = strconst "-"
    %30 = call.bool @_starts_with(%28 borrow, %29 borrow)
    br %30, L19, L18

  L11:
    %31 = loadvar.string arg
    %32 = strconst "="
    %33 = call.int32 @str_index_of(%31 borrow, %32 borrow)
    %34 = const.int32 0
    %35 = binop ">=", %33, %34
    br %35, L13, L12

  L12:
    %36 = loadvar.int32 i
    %37 = const.int32 1
    %38 = binop "+", %36, %37
    local next: int32 = %38
    %39 = loadvar.int32 next
    %40 = call.int32 @argc()
    %41 = binop "<", %39, %40
    br %41, L15, L14

  L13:
    %42 = loadvar.int32 i
    %43 = const.int32 1
    %44 = binop "+", %42, %43
    storevar i, %44
    %45 = loadvar.string arg
    drop %45
    jmp L3

  L14:
    %46 = loadvar.int32 i
    %47 = const.int32 1
    %48 = binop "+", %46, %47
    storevar i, %48
    %49 = loadvar.string arg
    drop %49
    jmp L3

  L15:
    %50 = loadvar.int32 next
    %51 = call.string @argv_at(%50 own)
    local next_value: string = %51
    %52 = loadvar.string next_value
    %53 = call.bool @_looks_like_option_token(%52 borrow)
    %54 = bconst false
    %55 = binop "==", %53, %54
    br %55, L17, L16

  L16:
    %56 = loadvar.string next_value
    drop %56
    jmp L14

  L17:
    %57 = loadvar.int32 i
    %58 = const.int32 2
    %59 = binop "+", %57, %58
    storevar i, %59
    %60 = loadvar.string next_value
    drop %60
    %61 = loadvar.string arg
    drop %61
    jmp L3

  L18:
    jmp L6

  L19:
    %62 = loadvar.string arg
    %63 = call.int32 @_str_len(%62 borrow)
    local n: int32 = %63
    %64 = loadvar.int32 n
    %65 = const.int32 1
    %66 = binop "==", %64, %65
    br %66, L21, L20

  L20:
    %67 = loadvar.string arg
    %68 = strconst "="
    %69 = call.int32 @str_index_of(%67 borrow, %68 borrow)
    %70 = const.int32 0
    %71 = binop ">=", %69, %70
    br %71, L25, L24

  L21:
    %72 = loadvar.int32 logical_pos
    %73 = loadvar.int32 index
    %74 = binop "==", %72, %73
    br %74, L23, L22

  L22:
    %75 = loadvar.int32 logical_pos
    %76 = const.int32 1
    %77 = binop "+", %75, %76
    storevar logical_pos, %77
    %78 = loadvar.int32 i
    %79 = const.int32 1
    %80 = binop "+", %78, %79
    storevar i, %80
    %81 = loadvar.string arg
    drop %81
    jmp L3

  L23:
    %82 = loadvar.string fallback
    drop %82
    %83 = loadvar.string arg
    ret %83

  L24:
    %84 = loadvar.int32 n
    %85 = const.int32 2
    %86 = binop "==", %84, %85
    br %86, L27, L26

  L25:
    %87 = loadvar.int32 i
    %88 = const.int32 1
    %89 = binop "+", %87, %88
    storevar i, %89
    %90 = loadvar.string arg
    drop %90
    jmp L3

  L26:
    %91 = loadvar.int32 i
    %92 = const.int32 1
    %93 = binop "+", %91, %92
    storevar i, %93
    %94 = loadvar.string arg
    drop %94
    jmp L3

  L27:
    %95 = loadvar.int32 i
    %96 = const.int32 1
    %97 = binop "+", %95, %96
    local next__2: int32 = %97
    %98 = loadvar.int32 next__2
    %99 = call.int32 @argc()
    %100 = binop "<", %98, %99
    br %100, L29, L28

  L28:
    %101 = loadvar.int32 i
    %102 = const.int32 1
    %103 = binop "+", %101, %102
    storevar i, %103
    %104 = loadvar.string arg
    drop %104
    jmp L3

  L29:
    %105 = loadvar.int32 next__2
    %106 = call.string @argv_at(%105 own)
    local next_value__2: string = %106
    %107 = loadvar.string next_value__2
    %108 = call.bool @_looks_like_option_token(%107 borrow)
    %109 = bconst false
    %110 = binop "==", %108, %109
    br %110, L31, L30

  L30:
    %111 = loadvar.string next_value__2
    drop %111
    jmp L28

  L31:
    %112 = loadvar.int32 i
    %113 = const.int32 2
    %114 = binop "+", %112, %113
    storevar i, %114
    %115 = loadvar.string next_value__2
    drop %115
    %116 = loadvar.string arg
    drop %116
    jmp L3

  L32:
    %117 = loadvar.string arg
    drop %117
    %118 = loadvar.int32 logical_pos
    %119 = const.int32 1
    %120 = binop "+", %118, %119
    storevar logical_pos, %120
    %121 = loadvar.int32 i
    %122 = const.int32 1
    %123 = binop "+", %121, %122
    storevar i, %123
    jmp L3

  L33:
    %124 = loadvar.string fallback
    drop %124
    %125 = loadvar.string arg
    ret %125
}

function @main() -> void {
  L0:
    %0 = call.int32 @argc()
    local count: int32 = %0
    %1 = loadvar.int32 count
    %2 = const.int32 1
    %3 = binop ">=", %1, %2
    call @println(%3 borrow)
    %4 = const.int32 0
    %5 = call.string @argv_at(%4 own)
    %6 = strconst ""
    %7 = binop "!=", %5, %6
    call @println(%7 borrow)
    %8 = const.int32 1
    %9 = unop "-", %8
    %10 = call.string @argv_at(%9 own)
    %11 = strconst ""
    %12 = binop "==", %10, %11
    call @println(%12 borrow)
    %13 = const.int32 9999
    %14 = call.string @argv_at(%13 own)
    %15 = strconst ""
    %16 = binop "==", %14, %15
    call @println(%16 borrow)
    ret
}

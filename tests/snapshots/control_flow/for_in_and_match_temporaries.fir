fir module for_in_and_match_temporaries

type Status owned {
}

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

function @makeString() -> string {
  L0:
    %0 = strconst "abc"
    ret %0
}

function @makeStatus() -> Status {
  L0:
    %0 = const.int32 42
    %1 = ctorvariant.Status "Failed"(%0)
    ret %1
}

function @main() -> void {
  L0:
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = const.int32 3
    %3 = arrayconst.int32[3] [%0, %1, %2]
    local __arr_y: int32[3] = %3
    %4 = const.int32 0
    local __i_y: int32 = %4
    jmp L1

  L1:
    %5 = loadvar.int32 __i_y
    %6 = const.int32 3
    %7 = binop "<", %5, %6
    br %7, L2, L3

  L2:
    %8 = loadvar.int32[3] __arr_y
    %9 = loadvar.int32 __i_y
    %10 = indexarray.int32 %8, %9
    local y: int32 = %10
    %11 = loadvar.int32 y
    call @println(%11 borrow)
    jmp L4

  L3:
    %12 = loadvar.int32[3] __arr_y
    drop %12
    %13 = call.string @makeString()
    local __str_c: string = %13
    %14 = const.int32 0
    local __i_c: int32 = %14
    jmp L5

  L4:
    %15 = loadvar.int32 __i_y
    %16 = const.int32 1
    %17 = binop "+", %15, %16
    storevar __i_y, %17
    jmp L1

  L5:
    %18 = loadvar.int32 __i_c
    %19 = loadvar.string __str_c
    %20 = call.int32 @str_length(%19 borrow)
    %21 = binop "<", %18, %20
    br %21, L6, L7

  L6:
    %22 = loadvar.int32 __i_c
    %23 = loadvar.string __str_c
    %24 = call.string @str_char_at(%23 borrow, %22 own)
    local c: string = %24
    %25 = loadvar.string c
    call @println(%25 borrow)
    %26 = loadvar.string c
    drop %26
    jmp L8

  L7:
    %27 = loadvar.string __str_c
    drop %27
    %28 = call.Status @makeStatus()
    local __match_scrutinee_1: Status = %28
    local __match_result_1: int32
    %29 = loadvar.Status __match_scrutinee_1
    %30 = extracttag.int32 %29
    %31 = const.int32 0
    %32 = binop "==", %30, %31
    br %32, L10, L11

  L8:
    %33 = loadvar.int32 __i_c
    %34 = const.int32 1
    %35 = binop "+", %33, %34
    storevar __i_c, %35
    jmp L5

  L9:
    %36 = loadvar.Status __match_scrutinee_1
    drop %36
    %37 = loadvar.int32 __match_result_1
    local result: int32 = %37
    %38 = loadvar.int32 result
    call @println(%38 borrow)
    %39 = arrayconst.int32[4] []
    local uninitialized: int32[4] = %39
    %40 = loadvar.int32[4] uninitialized
    %41 = const.int32 0
    %42 = indexarray.int32 %40, %41
    call @println(%42 borrow)
    %43 = loadvar.int32[4] uninitialized
    drop %43
    %44 = const.int32 1
    %45 = const.int32 2
    %46 = const.int32 3
    %47 = arrayconst.int32[3] [%44, %45, %46]
    local src: int32[3] = %47
    %48 = loadvar.int32[3] src
    local fromExpr: int32[3] = %48
    %49 = loadvar.int32[3] fromExpr
    %50 = const.int32 2
    %51 = indexarray.int32 %49, %50
    call @println(%51 borrow)
    %52 = loadvar.int32[3] fromExpr
    drop %52
    ret

  L10:
    %53 = const.int32 0
    storevar __match_result_1, %53
    jmp L9

  L11:
    %54 = loadvar.Status __match_scrutinee_1
    %55 = extracttag.int32 %54
    %56 = const.int32 1
    %57 = binop "==", %55, %56
    br %57, L12, L13

  L12:
    %58 = loadvar.Status __match_scrutinee_1
    %59 = extractfield.int32 %58, "Failed", 0
    local code: int32 = %59
    %60 = loadvar.int32 code
    storevar __match_result_1, %60
    jmp L9

  L13:
    unreachable
}

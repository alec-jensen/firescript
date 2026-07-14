fir module operators_logical

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

function @main() -> void {
  L0:
    %0 = strconst "=== Logical Operators ==="
    call @println(%0 borrow)
    %1 = strconst "--- Boolean Basics ---"
    call @println(%1 borrow)
    %2 = bconst true
    local t: bool = %2
    %3 = bconst false
    local f: bool = %3
    %4 = loadvar.bool t
    call @println(%4 borrow)
    %5 = loadvar.bool f
    call @println(%5 borrow)
    %6 = loadvar.bool t
    %7 = bconst true
    %8 = binop "==", %6, %7
    call @println(%8 borrow)
    %9 = loadvar.bool f
    %10 = bconst false
    %11 = binop "==", %9, %10
    call @println(%11 borrow)
    %12 = loadvar.bool t
    %13 = loadvar.bool f
    %14 = binop "==", %12, %13
    call @println(%14 borrow)
    %15 = strconst "--- Logical Conditions ---"
    call @println(%15 borrow)
    %16 = const.int32 10
    local a: int32 = %16
    %17 = const.int32 5
    local b: int32 = %17
    %18 = const.int32 15
    local c: int32 = %18
    %19 = loadvar.int32 a
    %20 = loadvar.int32 b
    %21 = binop ">", %19, %20
    local __sc_1: bool = %21
    %22 = loadvar.bool __sc_1
    br %22, L2, L3

  L1:
    %23 = loadvar.int32 a
    %24 = loadvar.int32 b
    %25 = binop "<", %23, %24
    local __sc_2: bool = %25
    %26 = loadvar.bool __sc_2
    br %26, L7, L6

  L2:
    %27 = loadvar.int32 a
    %28 = loadvar.int32 c
    %29 = binop "<", %27, %28
    storevar __sc_1, %29
    jmp L3

  L3:
    %30 = loadvar.bool __sc_1
    br %30, L4, L1

  L4:
    %31 = strconst "a is between b and c"
    call @println(%31 borrow)
    jmp L1

  L5:
    %32 = loadvar.int32 a
    %33 = loadvar.int32 b
    %34 = binop "<", %32, %33
    local __sc_3: bool = %34
    %35 = loadvar.bool __sc_3
    br %35, L11, L10

  L6:
    %36 = loadvar.int32 a
    %37 = const.int32 0
    %38 = binop ">", %36, %37
    storevar __sc_2, %38
    jmp L7

  L7:
    %39 = loadvar.bool __sc_2
    br %39, L8, L5

  L8:
    %40 = strconst "a meets at least one condition"
    call @println(%40 borrow)
    jmp L5

  L9:
    %41 = loadvar.bool t
    local __sc_4: bool = %41
    %42 = loadvar.bool __sc_4
    br %42, L14, L15

  L10:
    %43 = loadvar.bool t
    %44 = unop "!", %43
    storevar __sc_3, %44
    jmp L11

  L11:
    %45 = loadvar.bool __sc_3
    %46 = unop "!", %45
    br %46, L12, L9

  L12:
    %47 = strconst "not/or combination works"
    call @println(%47 borrow)
    jmp L9

  L13:
    %48 = strconst "=== All logical operator tests passed ==="
    call @println(%48 borrow)
    ret

  L14:
    %49 = loadvar.bool f
    %50 = unop "!", %49
    storevar __sc_4, %50
    jmp L15

  L15:
    %51 = loadvar.bool __sc_4
    br %51, L16, L13

  L16:
    %52 = strconst "and/not combination works"
    call @println(%52 borrow)
    jmp L13
}

fir module control_flow_while

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
    %0 = const.int32 0
    local count: int32 = %0
    jmp L1

  L1:
    %1 = loadvar.int32 count
    %2 = const.int32 5
    %3 = binop "<", %1, %2
    br %3, L2, L3

  L2:
    %4 = loadvar.int32 count
    call @println(%4 borrow)
    %5 = loadvar.int32 count
    %6 = const.int32 1
    %7 = binop "+", %5, %6
    storevar count, %7
    jmp L1

  L3:
    %8 = const.int32 0
    local i: int32 = %8
    jmp L4

  L4:
    %9 = loadvar.int32 i
    %10 = const.int32 10
    %11 = binop "<", %9, %10
    br %11, L5, L6

  L5:
    %12 = loadvar.int32 i
    %13 = const.int32 5
    %14 = binop "==", %12, %13
    br %14, L8, L7

  L6:
    %15 = const.int32 0
    local j: int32 = %15
    jmp L9

  L7:
    %16 = loadvar.int32 i
    call @println(%16 borrow)
    %17 = loadvar.int32 i
    %18 = const.int32 1
    %19 = binop "+", %17, %18
    storevar i, %19
    jmp L4

  L8:
    jmp L6

  L9:
    %20 = loadvar.int32 j
    %21 = const.int32 5
    %22 = binop "<", %20, %21
    br %22, L10, L11

  L10:
    %23 = loadvar.int32 j
    %24 = const.int32 1
    %25 = binop "+", %23, %24
    storevar j, %25
    %26 = loadvar.int32 j
    %27 = const.int32 3
    %28 = binop "==", %26, %27
    br %28, L13, L12

  L11:
    %29 = const.int32 0
    local outer: int32 = %29
    jmp L14

  L12:
    %30 = loadvar.int32 j
    call @println(%30 borrow)
    jmp L9

  L13:
    jmp L9

  L14:
    %31 = loadvar.int32 outer
    %32 = const.int32 3
    %33 = binop "<", %31, %32
    br %33, L15, L16

  L15:
    %34 = const.int32 0
    local inner: int32 = %34
    jmp L17

  L16:
    ret

  L17:
    %35 = loadvar.int32 inner
    %36 = const.int32 2
    %37 = binop "<", %35, %36
    br %37, L18, L19

  L18:
    %38 = loadvar.int32 outer
    %39 = const.int32 10
    %40 = binop "*", %38, %39
    %41 = loadvar.int32 inner
    %42 = binop "+", %40, %41
    call @println(%42 borrow)
    %43 = loadvar.int32 inner
    %44 = const.int32 1
    %45 = binop "+", %43, %44
    storevar inner, %45
    jmp L17

  L19:
    %46 = loadvar.int32 outer
    %47 = const.int32 1
    %48 = binop "+", %46, %47
    storevar outer, %48
    jmp L14
}

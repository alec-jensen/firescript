fir module memory_branching

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

function @branching() -> void {
  L0:
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = arrayconst.int32[2] [%0, %1]
    local a: int32[2] = %2
    %3 = const.int32 1
    local cond: int32 = %3
    %4 = loadvar.int32 cond
    %5 = const.int32 1
    %6 = binop "==", %4, %5
    br %6, L2, L3

  L1:
    %7 = const.int32 2
    call @println(%7 borrow)
    %8 = loadvar.int32[2] a
    drop %8
    ret

  L2:
    %9 = const.int32 5
    %10 = arrayconst.int32[1] [%9]
    local b: int32[1] = %10
    %11 = const.int32 1
    call @println(%11 borrow)
    %12 = loadvar.int32[1] b
    drop %12
    jmp L1

  L3:
    %13 = const.int32 7
    %14 = const.int32 8
    %15 = const.int32 9
    %16 = arrayconst.int32[3] [%13, %14, %15]
    local c: int32[3] = %16
    %17 = const.int32 3
    call @println(%17 borrow)
    %18 = loadvar.int32[3] c
    drop %18
    jmp L1
}

function @scoped() -> void {
  L0:
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = const.int32 3
    %3 = arrayconst.int32[3] [%0, %1, %2]
    local a: int32[3] = %3
    %4 = const.int32 3
    call @println(%4 borrow)
    %5 = const.int32 10
    %6 = const.int32 20
    %7 = arrayconst.int32[2] [%5, %6]
    local b: int32[2] = %7
    %8 = const.int32 2
    call @println(%8 borrow)
    %9 = loadvar.int32[2] b
    drop %9
    %10 = const.int32 3
    call @println(%10 borrow)
    %11 = loadvar.int32[3] a
    drop %11
    ret
}

function @earlyReturn() -> int32 {
  L0:
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = const.int32 3
    %3 = arrayconst.int32[3] [%0, %1, %2]
    local temp: int32[3] = %3
    %4 = const.int32 3
    call @println(%4 borrow)
    %5 = loadvar.int32[3] temp
    drop %5
    %6 = const.int32 7
    ret %6
}

function @main() -> void {
  L0:
    call @branching()
    call @scoped()
    %0 = call.int32 @earlyReturn()
    call @println(%0 borrow)
    ret
}

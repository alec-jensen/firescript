fir module classes_static_methods

type Math owned {
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

function @Math.max(a: int32, b: int32) -> int32 {
  L0:
    %0 = loadvar.int32 a
    %1 = loadvar.int32 b
    %2 = binop ">", %0, %1
    br %2, L2, L1

  L1:
    %3 = loadvar.int32 b
    ret %3

  L2:
    %4 = loadvar.int32 a
    ret %4
}

function @Math.add(a: int32, b: int32) -> int32 {
  L0:
    %0 = loadvar.int32 a
    %1 = loadvar.int32 b
    %2 = binop "+", %0, %1
    ret %2
}

function @Math.twice(this: Math, x: int32) -> int32 {
  L0:
    %0 = loadvar.Math this
    drop %0
    %1 = loadvar.int32 x
    %2 = const.int32 2
    %3 = binop "*", %1, %2
    ret %3
}

function @main() -> void {
  L0:
    %0 = const.int32 3
    %1 = const.int32 7
    %2 = call.int32 @Math.max(%0 own, %1 own)
    call @println(%2 borrow)
    %3 = const.int32 8
    %4 = const.int32 5
    %5 = call.int32 @Math.add(%3 own, %4 own)
    call @println(%5 borrow)
    %6 = alloc.Math()
    local m: Math = %6
    %7 = loadvar.Math m
    %8 = const.int32 6
    %9 = mcall.int32 %7, "twice"(%8 own)
    call @println(%9 borrow)
    %10 = loadvar.Math m
    drop %10
    ret
}

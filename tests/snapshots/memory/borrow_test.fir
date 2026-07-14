fir module borrow_test

type Point owned {
  x: int32
  y: int32
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

function @getX(p: &Point) -> int32 {
  L0:
    %0 = loadvar.Point p
    %1 = loadfield.int32 %0, "x"
    ret %1
}

function @consumePoint(p: Point) -> void {
  L0:
    %0 = loadvar.Point p
    %1 = loadfield.int32 %0, "x"
    call @println(%1 borrow)
    %2 = loadvar.Point p
    drop %2
    ret
}

function @main() -> void {
  L0:
    %0 = const.int32 10
    %1 = const.int32 20
    %2 = alloc.Point(%0, %1)
    local p1: Point = %2
    %3 = loadvar.Point p1
    %4 = call.int32 @getX(%3 borrow)
    local x: int32 = %4
    %5 = loadvar.int32 x
    call @println(%5 borrow)
    %6 = loadvar.Point p1
    %7 = loadfield.int32 %6, "y"
    call @println(%7 borrow)
    %8 = loadvar.Point p1
    call @consumePoint(%8 own)
    ret
}

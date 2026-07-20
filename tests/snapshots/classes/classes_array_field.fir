fir module classes_array_field

type Buf owned {
  data: int32[]
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

function @make_data(arr: int32[]) -> int32[] {
  L0:
    %0 = loadvar.int32[] arr
    ret %0
}

function @Buf.Buf() -> Buf {
  L0:
    %0 = alloc.Buf()
    local this: Buf = %0
    %1 = const.int32 10
    %2 = const.int32 20
    %3 = const.int32 30
    %4 = arrayconst.int32[3] [%1, %2, %3]
    %5 = call.int32[] @make_data(%4 own)
    %6 = loadvar.Buf this
    storefield %6, "data", %5
    %7 = loadvar.Buf this
    ret %7
}

function @Buf.get(this: &Buf, i: int32) -> int32 {
  L0:
    %0 = loadvar.Buf this
    %1 = loadfield.int32[] %0, "data"
    %2 = loadvar.int32 i
    %3 = indexarray.int32 %1, %2
    ret %3
}

function @Buf.set(this: &mut Buf, i: int32, v: int32) -> void {
  L0:
    %0 = loadvar.int32 v
    %1 = loadvar.Buf this
    %2 = loadfield.int32[] %1, "data"
    %3 = loadvar.int32 i
    storearray %2, %3, %0
    ret
}

function @main() -> void {
  L0:
    %0 = call.Buf @Buf.Buf()
    local b: Buf = %0
    %1 = loadvar.Buf b
    %2 = const.int32 0
    %3 = mcall.int32 %1, "get"(%2 own)
    call @println(%3 borrow)
    %4 = loadvar.Buf b
    %5 = const.int32 1
    %6 = mcall.int32 %4, "get"(%5 own)
    call @println(%6 borrow)
    %7 = loadvar.Buf b
    %8 = const.int32 2
    %9 = mcall.int32 %7, "get"(%8 own)
    call @println(%9 borrow)
    %10 = loadvar.Buf b
    %11 = const.int32 1
    %12 = const.int32 99
    mcall %10, "set"(%11 own, %12 own)
    %13 = loadvar.Buf b
    %14 = const.int32 1
    %15 = mcall.int32 %13, "get"(%14 own)
    call @println(%15 borrow)
    %16 = loadvar.Buf b
    drop %16
    ret
}

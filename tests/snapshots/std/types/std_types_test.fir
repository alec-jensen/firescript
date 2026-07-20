fir module std_types_test

type Tuple<T, U> owned {
  first: T
  second: U
}

type CopyableTuple<T, U> copyable {
  first: T
  second: U
}

type Option<T> owned {
  value: T?
  value__hasval: bool
}

type CopyableOption<T> copyable {
  value: T?
  value__hasval: bool
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

function<T, U> @Tuple.Tuple(first: T, second: U) -> Tuple {
  L0:
    %0 = alloc.Tuple()
    local this: Tuple = %0
    %1 = loadvar.T first
    %2 = loadvar.Tuple this
    storefield %2, "first", %1
    %3 = loadvar.U second
    %4 = loadvar.Tuple this
    storefield %4, "second", %3
    %5 = loadvar.Tuple this
    ret %5
}

function<T, U> @CopyableTuple.CopyableTuple(first: T, second: U) -> CopyableTuple {
  L0:
    %0 = alloc.CopyableTuple()
    local this: CopyableTuple = %0
    %1 = loadvar.T first
    %2 = loadvar.CopyableTuple this
    storefield %2, "first", %1
    %3 = loadvar.U second
    %4 = loadvar.CopyableTuple this
    storefield %4, "second", %3
    %5 = loadvar.CopyableTuple this
    ret %5
}

function<T> @Option.Option(value: T?, value__hasval: bool) -> Option {
  L0:
    %0 = alloc.Option()
    local this: Option = %0
    %1 = loadvar.bool value__hasval
    %2 = loadvar.T? value
    %3 = loadvar.Option this
    storefield %3, "value", %2
    storefield %3, "value__hasval", %1
    %4 = loadvar.Option this
    ret %4
}

function<T> @Option.isSome(this: &Option) -> bool {
  L0:
    %0 = loadvar.Option this
    %1 = loadfield.bool %0, "value__hasval"
    ret %1
}

function<T> @Option.isNone(this: &Option) -> bool {
  L0:
    %0 = loadvar.Option this
    %1 = loadfield.bool %0, "value__hasval"
    %2 = unop "!", %1
    ret %2
}

function<T> @CopyableOption.CopyableOption(value: T?, value__hasval: bool) -> CopyableOption {
  L0:
    %0 = alloc.CopyableOption()
    local this: CopyableOption = %0
    %1 = loadvar.bool value__hasval
    %2 = loadvar.T? value
    %3 = loadvar.CopyableOption this
    storefield %3, "value", %2
    storefield %3, "value__hasval", %1
    %4 = loadvar.CopyableOption this
    ret %4
}

function<T> @CopyableOption.isSome(this: CopyableOption) -> bool {
  L0:
    %0 = loadvar.CopyableOption this
    %1 = loadfield.bool %0, "value__hasval"
    ret %1
}

function<T> @CopyableOption.isNone(this: CopyableOption) -> bool {
  L0:
    %0 = loadvar.CopyableOption this
    %1 = loadfield.bool %0, "value__hasval"
    %2 = unop "!", %1
    ret %2
}

function @main() -> void {
  L0:
    %0 = const.int32 42
    %1 = strconst "hello"
    %2 = call.Tuple<int32, string> @Tuple.Tuple(%0 own, %1 own)
    local t1: Tuple<int32, string> = %2
    %3 = loadvar.Tuple<int32, string> t1
    %4 = loadfield.int32 %3, "first"
    call @println(%4 borrow)
    %5 = loadvar.Tuple<int32, string> t1
    %6 = loadfield.string %5, "second"
    call @println(%6 borrow)
    %7 = loadvar.Tuple<int32, string> t1
    drop %7
    ret
}

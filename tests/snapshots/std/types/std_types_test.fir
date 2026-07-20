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

type Result<T, E> owned {
  value: T?
  value__hasval: bool
  error: E?
  error__hasval: bool
}

type CopyableResult<T, E> copyable {
  value: T?
  value__hasval: bool
  error: E?
  error__hasval: bool
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

function<T> @Option.Some(value: T) -> Option<T> {
  L0:
    %0 = loadvar.T value
    %1 = bconst true
    %2 = call.Option<T> @Option.Option(%0 own, %1 own)
    ret %2
}

function<T> @Option.None() -> Option<T> {
  L0:
    %0 = nullconst T?
    %1 = bconst false
    %2 = call.Option<T> @Option.Option(%0 own, %1 own)
    ret %2
}

function<T> @Option.unwrapOr(this: &mut Option, default: T) -> T {
  L0:
    %0 = loadvar.Option this
    %1 = mcall.bool %0, "isSome"()
    br %1, L2, L1

  L1:
    %2 = loadvar.T default
    ret %2

  L2:
    %3 = loadvar.Option this
    %4 = loadfield.T? %3, "value"
    local v: T = %4
    %5 = bconst false
    %6 = nullconst T?
    %7 = loadvar.Option this
    storefield %7, "value", %6
    storefield %7, "value__hasval", %5
    %8 = loadvar.T v
    ret %8
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

function<T> @CopyableOption.Some(value: T) -> CopyableOption<T> {
  L0:
    %0 = loadvar.T value
    %1 = bconst true
    %2 = call.CopyableOption<T> @CopyableOption.CopyableOption(%0 own, %1 own)
    ret %2
}

function<T> @CopyableOption.None() -> CopyableOption<T> {
  L0:
    %0 = nullconst T?
    %1 = bconst false
    %2 = call.CopyableOption<T> @CopyableOption.CopyableOption(%0 own, %1 own)
    ret %2
}

function<T> @CopyableOption.unwrapOr(this: CopyableOption, default: T) -> T {
  L0:
    %0 = loadvar.CopyableOption this
    %1 = mcall.bool %0, "isSome"()
    br %1, L2, L1

  L1:
    %2 = loadvar.T default
    ret %2

  L2:
    %3 = loadvar.CopyableOption this
    %4 = loadfield.T? %3, "value"
    local v: T = %4
    %5 = loadvar.T v
    ret %5
}

function<T, E> @Result.Result(value: T?, error: E?, value__hasval: bool, error__hasval: bool) -> Result {
  L0:
    %0 = alloc.Result()
    local this: Result = %0
    %1 = loadvar.bool value__hasval
    %2 = loadvar.T? value
    %3 = loadvar.Result this
    storefield %3, "value", %2
    storefield %3, "value__hasval", %1
    %4 = loadvar.bool error__hasval
    %5 = loadvar.E? error
    %6 = loadvar.Result this
    storefield %6, "error", %5
    storefield %6, "error__hasval", %4
    %7 = loadvar.Result this
    ret %7
}

function<T, E> @Result.isOk(this: &Result) -> bool {
  L0:
    %0 = loadvar.Result this
    %1 = loadfield.bool %0, "value__hasval"
    ret %1
}

function<T, E> @Result.isErr(this: &Result) -> bool {
  L0:
    %0 = loadvar.Result this
    %1 = loadfield.bool %0, "error__hasval"
    ret %1
}

function<T, E> @Result.Ok(value: T) -> Result<T, E> {
  L0:
    %0 = loadvar.T value
    %1 = nullconst E?
    %2 = bconst true
    %3 = bconst false
    %4 = call.Result<T, E> @Result.Result(%0 own, %1 own, %2 own, %3 own)
    ret %4
}

function<T, E> @Result.Err(error: E) -> Result<T, E> {
  L0:
    %0 = nullconst T?
    %1 = loadvar.E error
    %2 = bconst false
    %3 = bconst true
    %4 = call.Result<T, E> @Result.Result(%0 own, %1 own, %2 own, %3 own)
    ret %4
}

function<T, E> @Result.unwrapOr(this: &mut Result, default: T) -> T {
  L0:
    %0 = loadvar.Result this
    %1 = mcall.bool %0, "isOk"()
    br %1, L2, L1

  L1:
    %2 = loadvar.T default
    ret %2

  L2:
    %3 = loadvar.Result this
    %4 = loadfield.T? %3, "value"
    local v: T = %4
    %5 = bconst false
    %6 = nullconst T?
    %7 = loadvar.Result this
    storefield %7, "value", %6
    storefield %7, "value__hasval", %5
    %8 = loadvar.T v
    ret %8
}

function<T, E> @CopyableResult.CopyableResult(value: T?, error: E?, value__hasval: bool, error__hasval: bool) -> CopyableResult {
  L0:
    %0 = alloc.CopyableResult()
    local this: CopyableResult = %0
    %1 = loadvar.bool value__hasval
    %2 = loadvar.T? value
    %3 = loadvar.CopyableResult this
    storefield %3, "value", %2
    storefield %3, "value__hasval", %1
    %4 = loadvar.bool error__hasval
    %5 = loadvar.E? error
    %6 = loadvar.CopyableResult this
    storefield %6, "error", %5
    storefield %6, "error__hasval", %4
    %7 = loadvar.CopyableResult this
    ret %7
}

function<T, E> @CopyableResult.isOk(this: CopyableResult) -> bool {
  L0:
    %0 = loadvar.CopyableResult this
    %1 = loadfield.bool %0, "value__hasval"
    ret %1
}

function<T, E> @CopyableResult.isErr(this: CopyableResult) -> bool {
  L0:
    %0 = loadvar.CopyableResult this
    %1 = loadfield.bool %0, "error__hasval"
    ret %1
}

function<T, E> @CopyableResult.Ok(value: T) -> CopyableResult<T, E> {
  L0:
    %0 = loadvar.T value
    %1 = nullconst E?
    %2 = bconst true
    %3 = bconst false
    %4 = call.CopyableResult<T, E> @CopyableResult.CopyableResult(%0 own, %1 own, %2 own, %3 own)
    ret %4
}

function<T, E> @CopyableResult.Err(error: E) -> CopyableResult<T, E> {
  L0:
    %0 = nullconst T?
    %1 = loadvar.E error
    %2 = bconst false
    %3 = bconst true
    %4 = call.CopyableResult<T, E> @CopyableResult.CopyableResult(%0 own, %1 own, %2 own, %3 own)
    ret %4
}

function<T, E> @CopyableResult.unwrapOr(this: CopyableResult, default: T) -> T {
  L0:
    %0 = loadvar.CopyableResult this
    %1 = mcall.bool %0, "isOk"()
    br %1, L2, L1

  L1:
    %2 = loadvar.T default
    ret %2

  L2:
    %3 = loadvar.CopyableResult this
    %4 = loadfield.T? %3, "value"
    local v: T = %4
    %5 = loadvar.T v
    ret %5
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

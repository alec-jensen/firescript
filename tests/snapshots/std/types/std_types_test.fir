module std_types_test

type Tuple<T, U> owned {
  first: T
  second: U
}

type CopyableTuple<T, U> copyable {
  first: T
  second: U
}

type Option<T> owned {
  value: T
}

type CopyableOption<T> copyable {
  value: T
}

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("text", string, %1)
    %2 = LoadVar("text") -> string
    Call(stdout, [%2], ["borrow"])
    %3 = LoadVar("text") -> string
    Drop(%3)
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    DeclareLocal("cast_text", string, %1)
    %2 = LoadVar("cast_text") -> string
    %3 = StringLiteral("\n", string)
    %4 = BinaryOp("+", %2, %3)
    DeclareLocal("text", string, %4)
    %5 = LoadVar("cast_text") -> string
    Drop(%5)
    %6 = LoadVar("text") -> string
    Call(stdout, [%6], ["borrow"])
    %7 = LoadVar("text") -> string
    Drop(%7)
    Return()
}

function<T, U> Tuple.Tuple(first: T, second: U) -> Tuple {
  block_0:
    %0 = Allocate(Tuple, [])
    DeclareLocal("this", Tuple, %0)
    %1 = LoadVar("first") -> T
    %2 = LoadVar("this") -> Tuple
    StoreField(%2, "first", %1)
    %3 = LoadVar("second") -> U
    %4 = LoadVar("this") -> Tuple
    StoreField(%4, "second", %3)
    %5 = LoadVar("this") -> Tuple
    Return(%5)
}

function<T, U> CopyableTuple.CopyableTuple(first: T, second: U) -> CopyableTuple {
  block_0:
    %0 = Allocate(CopyableTuple, [])
    DeclareLocal("this", CopyableTuple, %0)
    %1 = LoadVar("first") -> T
    %2 = LoadVar("this") -> CopyableTuple
    StoreField(%2, "first", %1)
    %3 = LoadVar("second") -> U
    %4 = LoadVar("this") -> CopyableTuple
    StoreField(%4, "second", %3)
    %5 = LoadVar("this") -> CopyableTuple
    Return(%5)
}

function<T> Option.Option(value: T) -> Option {
  block_0:
    %0 = Allocate(Option, [])
    DeclareLocal("this", Option, %0)
    %1 = LoadVar("value") -> T
    %2 = LoadVar("this") -> Option
    StoreField(%2, "value", %1)
    %3 = LoadVar("this") -> Option
    Return(%3)
}

function<T> Option.isSome(this: Option) -> bool {
  block_0:
    %0 = LoadVar("this") -> Option
    %1 = LoadField(%0, "value")
    %2 = NullLiteral(string?)
    %3 = BinaryOp("!=", %1, %2)
    %4 = LoadVar("this") -> Option
    Drop(%4)
    Return(%3)
}

function<T> Option.isNone(this: Option) -> bool {
  block_0:
    %0 = LoadVar("this") -> Option
    %1 = LoadField(%0, "value")
    %2 = NullLiteral(string?)
    %3 = BinaryOp("==", %1, %2)
    %4 = LoadVar("this") -> Option
    Drop(%4)
    Return(%3)
}

function<T> CopyableOption.CopyableOption(value: T) -> CopyableOption {
  block_0:
    %0 = Allocate(CopyableOption, [])
    DeclareLocal("this", CopyableOption, %0)
    %1 = LoadVar("value") -> T
    %2 = LoadVar("this") -> CopyableOption
    StoreField(%2, "value", %1)
    %3 = LoadVar("this") -> CopyableOption
    Return(%3)
}

function<T> CopyableOption.isSome(this: CopyableOption) -> bool {
  block_0:
    %0 = LoadVar("this") -> CopyableOption
    %1 = LoadField(%0, "value")
    %2 = NullLiteral(string?)
    %3 = BinaryOp("!=", %1, %2)
    Return(%3)
}

function<T> CopyableOption.isNone(this: CopyableOption) -> bool {
  block_0:
    %0 = LoadVar("this") -> CopyableOption
    %1 = LoadField(%0, "value")
    %2 = NullLiteral(string?)
    %3 = BinaryOp("==", %1, %2)
    Return(%3)
}

function main() -> void {
  block_0:
    %0 = IntLiteral(42, int32)
    %1 = StringLiteral("hello", string)
    %2 = Call(Tuple.Tuple, [%0, %1], ["own", "own"]) -> Tuple<int32, string>
    DeclareLocal("t1", Tuple<int32, string>, %2)
    %3 = LoadVar("t1") -> Tuple<int32, string>
    %4 = LoadField(%3, "first")
    Call(println, [%4], ["borrow"])
    %5 = LoadVar("t1") -> Tuple<int32, string>
    %6 = LoadField(%5, "second")
    Call(println, [%6], ["borrow"])
    %7 = LoadVar("t1") -> Tuple<int32, string>
    Drop(%7)
    Return()
}

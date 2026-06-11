module syscall_basic

function<T> print(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    Call(stdout, [%1], ["own"])
    Return()
}

function<T> println(value: &T) -> void {
  block_0:
    %0 = LoadVar("value") -> T
    %1 = Cast(%0, string)
    %2 = StringLiteral("\n", string)
    %3 = BinaryOp("+", %1, %2)
    Call(stdout, [%3], ["own"])
    Return()
}

function main() -> void {
  block_0:
    %0 = StringLiteral("build/temp/syscall_test_data.txt", string)
    %1 = StringLiteral("w", string)
    %2 = Call(syscall_open, [%0, %1], ["own", "own"]) -> SyscallResult
    DeclareLocal("open_w", SyscallResult, %2)
    %3 = LoadVar("open_w") -> SyscallResult
    %4 = LoadField(%3, "status")
    %5 = IntLiteral(0, int32)
    %6 = BinaryOp(">=", %4, %5)
    Branch(%6, block_2, block_1)

  block_1:
    Return()

  block_2:
    %7 = LoadVar("open_w") -> SyscallResult
    %8 = LoadField(%7, "status")
    %9 = StringLiteral("hello syscall", string)
    %10 = Call(syscall_write, [%8, %9], ["own", "own"]) -> SyscallResult
    %11 = LoadVar("open_w") -> SyscallResult
    %12 = LoadField(%11, "status")
    %13 = Call(syscall_close, [%12], ["own"]) -> SyscallResult
    %14 = StringLiteral("build/temp/syscall_test_data.txt", string)
    %15 = StringLiteral("r", string)
    %16 = Call(syscall_open, [%14, %15], ["own", "own"]) -> SyscallResult
    DeclareLocal("open_r", SyscallResult, %16)
    %17 = LoadVar("open_r") -> SyscallResult
    %18 = LoadField(%17, "status")
    %19 = IntLiteral(0, int32)
    %20 = BinaryOp(">=", %18, %19)
    Branch(%20, block_4, block_3)

  block_3:
    Jump(block_1)

  block_4:
    %21 = LoadVar("open_r") -> SyscallResult
    %22 = LoadField(%21, "status")
    %23 = IntLiteral(64, int32)
    %24 = Call(syscall_read, [%22, %23], ["own", "own"]) -> SyscallResult
    DeclareLocal("read_result", SyscallResult, %24)
    %25 = LoadVar("open_r") -> SyscallResult
    %26 = LoadField(%25, "status")
    %27 = Call(syscall_close, [%26], ["own"]) -> SyscallResult
    %28 = LoadVar("read_result") -> SyscallResult
    %29 = LoadField(%28, "status")
    %30 = IntLiteral(0, int32)
    %31 = BinaryOp(">=", %29, %30)
    Branch(%31, block_6, block_5)

  block_5:
    Jump(block_3)

  block_6:
    %32 = LoadVar("read_result") -> SyscallResult
    %33 = LoadField(%32, "data")
    Call(println, [%33], ["borrow"])
    Jump(block_5)
}

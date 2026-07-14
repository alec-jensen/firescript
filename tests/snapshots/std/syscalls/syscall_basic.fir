fir module syscall_basic

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
    %0 = strconst "build/temp/syscall_test_data.txt"
    %1 = strconst "w"
    %2 = call.SyscallResult @syscall_open(%0 borrow, %1 borrow)
    local open_w: SyscallResult = %2
    %3 = loadvar.SyscallResult open_w
    %4 = loadfield.int32 %3, "status"
    %5 = const.int32 0
    %6 = binop ">=", %4, %5
    br %6, L2, L1

  L1:
    ret

  L2:
    %7 = loadvar.SyscallResult open_w
    %8 = loadfield.int32 %7, "status"
    %9 = strconst "hello syscall"
    %10 = call.SyscallResult @syscall_write(%8 borrow, %9 borrow)
    %11 = loadvar.SyscallResult open_w
    %12 = loadfield.int32 %11, "status"
    %13 = call.SyscallResult @syscall_close(%12 borrow)
    %14 = strconst "build/temp/syscall_test_data.txt"
    %15 = strconst "r"
    %16 = call.SyscallResult @syscall_open(%14 borrow, %15 borrow)
    local open_r: SyscallResult = %16
    %17 = loadvar.SyscallResult open_r
    %18 = loadfield.int32 %17, "status"
    %19 = const.int32 0
    %20 = binop ">=", %18, %19
    br %20, L4, L3

  L3:
    jmp L1

  L4:
    %21 = loadvar.SyscallResult open_r
    %22 = loadfield.int32 %21, "status"
    %23 = const.int32 64
    %24 = call.SyscallResult @syscall_read(%22 borrow, %23 borrow)
    local read_result: SyscallResult = %24
    %25 = loadvar.SyscallResult open_r
    %26 = loadfield.int32 %25, "status"
    %27 = call.SyscallResult @syscall_close(%26 borrow)
    %28 = loadvar.SyscallResult read_result
    %29 = loadfield.int32 %28, "status"
    %30 = const.int32 0
    %31 = binop ">=", %29, %30
    br %31, L6, L5

  L5:
    jmp L3

  L6:
    %32 = loadvar.SyscallResult read_result
    %33 = loadfield.string %32, "data"
    call @println(%33 borrow)
    jmp L5
}

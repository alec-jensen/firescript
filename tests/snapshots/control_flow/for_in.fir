fir module for_in

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
    %0 = const.int32 1
    %1 = const.int32 2
    %2 = const.int32 3
    %3 = const.int32 4
    %4 = const.int32 5
    %5 = arrayconst.int32[5] [%0, %1, %2, %3, %4]
    local __arr_num: int32[5] = %5
    %6 = const.int32 0
    local __i_num: int32 = %6
    jmp L1

  L1:
    %7 = loadvar.int32 __i_num
    %8 = const.int32 5
    %9 = binop "<", %7, %8
    br %9, L2, L3

  L2:
    %10 = loadvar.int32[5] __arr_num
    %11 = loadvar.int32 __i_num
    %12 = indexarray.int32 %10, %11
    local num: int32 = %12
    %13 = loadvar.int32 num
    call @println(%13 borrow)
    jmp L4

  L3:
    %14 = loadvar.int32[5] __arr_num
    drop %14
    %15 = const.int32 10
    %16 = const.int32 20
    %17 = const.int32 30
    %18 = const.int32 40
    %19 = const.int32 50
    %20 = arrayconst.int32[5] [%15, %16, %17, %18, %19]
    local numbers: int32[5] = %20
    %21 = const.int32 0
    local __i_n: int32 = %21
    jmp L5

  L4:
    %22 = loadvar.int32 __i_num
    %23 = const.int32 1
    %24 = binop "+", %22, %23
    storevar __i_num, %24
    jmp L1

  L5:
    %25 = loadvar.int32 __i_n
    %26 = const.int32 5
    %27 = binop "<", %25, %26
    br %27, L6, L7

  L6:
    %28 = loadvar.int32[5] numbers
    %29 = loadvar.int32 __i_n
    %30 = indexarray.int32 %28, %29
    local n: int32 = %30
    %31 = loadvar.int32 n
    call @println(%31 borrow)
    jmp L8

  L7:
    %32 = const.int32 1
    %33 = const.int32 2
    %34 = const.int32 3
    %35 = const.int32 4
    %36 = const.int32 5
    %37 = const.int32 6
    %38 = const.int32 7
    %39 = const.int32 8
    %40 = const.int32 9
    %41 = const.int32 10
    %42 = arrayconst.int32[10] [%32, %33, %34, %35, %36, %37, %38, %39, %40, %41]
    local __arr_num__2: int32[10] = %42
    %43 = const.int32 0
    local __i_num__2: int32 = %43
    jmp L9

  L8:
    %44 = loadvar.int32 __i_n
    %45 = const.int32 1
    %46 = binop "+", %44, %45
    storevar __i_n, %46
    jmp L5

  L9:
    %47 = loadvar.int32 __i_num__2
    %48 = const.int32 10
    %49 = binop "<", %47, %48
    br %49, L10, L11

  L10:
    %50 = loadvar.int32[10] __arr_num__2
    %51 = loadvar.int32 __i_num__2
    %52 = indexarray.int32 %50, %51
    local num__2: int32 = %52
    %53 = loadvar.int32 num__2
    %54 = const.int32 6
    %55 = binop "==", %53, %54
    br %55, L14, L13

  L11:
    %56 = loadvar.int32[10] __arr_num__2
    drop %56
    %57 = const.int32 1
    %58 = const.int32 2
    %59 = const.int32 3
    %60 = const.int32 4
    %61 = const.int32 5
    %62 = arrayconst.int32[5] [%57, %58, %59, %60, %61]
    local __arr_num__3: int32[5] = %62
    %63 = const.int32 0
    local __i_num__3: int32 = %63
    jmp L15

  L12:
    %64 = loadvar.int32 __i_num__2
    %65 = const.int32 1
    %66 = binop "+", %64, %65
    storevar __i_num__2, %66
    jmp L9

  L13:
    %67 = loadvar.int32 num__2
    call @println(%67 borrow)
    jmp L12

  L14:
    jmp L11

  L15:
    %68 = loadvar.int32 __i_num__3
    %69 = const.int32 5
    %70 = binop "<", %68, %69
    br %70, L16, L17

  L16:
    %71 = loadvar.int32[5] __arr_num__3
    %72 = loadvar.int32 __i_num__3
    %73 = indexarray.int32 %71, %72
    local num__3: int32 = %73
    %74 = loadvar.int32 num__3
    %75 = const.int32 3
    %76 = binop "==", %74, %75
    br %76, L20, L19

  L17:
    %77 = loadvar.int32[5] __arr_num__3
    drop %77
    %78 = loadvar.int32[5] numbers
    drop %78
    %79 = const.int32 0
    ret

  L18:
    %80 = loadvar.int32 __i_num__3
    %81 = const.int32 1
    %82 = binop "+", %80, %81
    storevar __i_num__3, %82
    jmp L15

  L19:
    %83 = loadvar.int32 num__3
    call @println(%83 borrow)
    jmp L18

  L20:
    jmp L18
}

fir module operator_precedence

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
    %0 = const.int32 2
    %1 = const.int32 3
    %2 = const.int32 4
    %3 = binop "*", %1, %2
    %4 = binop "+", %0, %3
    call @println(%4 borrow)
    %5 = const.int32 10
    %6 = const.int32 2
    %7 = const.int32 3
    %8 = binop "*", %6, %7
    %9 = binop "-", %5, %8
    call @println(%9 borrow)
    %10 = const.int32 10
    %11 = const.int32 2
    %12 = binop "/", %10, %11
    %13 = const.int32 3
    %14 = binop "+", %12, %13
    call @println(%14 borrow)
    %15 = const.int32 10
    %16 = const.int32 3
    %17 = binop "%", %15, %16
    %18 = const.int32 1
    %19 = binop "+", %17, %18
    call @println(%19 borrow)
    %20 = const.int32 2
    %21 = const.int32 3
    %22 = const.int32 2
    %23 = binop "**", %21, %22
    %24 = binop "*", %20, %23
    call @println(%24 borrow)
    %25 = const.int32 4
    %26 = const.int32 2
    %27 = const.int32 2
    %28 = binop "**", %26, %27
    %29 = binop "/", %25, %28
    call @println(%29 borrow)
    %30 = const.int32 10
    %31 = const.int32 2
    %32 = const.int32 3
    %33 = binop "**", %31, %32
    %34 = binop "-", %30, %33
    call @println(%34 borrow)
    %35 = const.int32 2
    %36 = unop "-", %35
    %37 = const.int32 5
    %38 = binop "+", %36, %37
    call @println(%38 borrow)
    %39 = const.int32 3
    %40 = unop "-", %39
    %41 = const.int32 3
    %42 = unop "-", %41
    %43 = binop "*", %40, %42
    call @println(%43 borrow)
    %44 = const.int32 2
    %45 = const.int32 3
    %46 = binop "+", %44, %45
    %47 = const.int32 4
    %48 = binop ">", %46, %47
    local r1: bool = %48
    %49 = const.int32 2
    %50 = const.int32 3
    %51 = binop "+", %49, %50
    %52 = const.int32 4
    %53 = binop "<", %51, %52
    local r2: bool = %53
    %54 = const.int32 2
    %55 = const.int32 3
    %56 = binop "*", %54, %55
    %57 = const.int32 6
    %58 = binop "==", %56, %57
    local r3: bool = %58
    %59 = const.int32 10
    %60 = const.int32 4
    %61 = binop "-", %59, %60
    %62 = const.int32 7
    %63 = binop "!=", %61, %62
    local r4: bool = %63
    %64 = loadvar.bool r1
    call @println(%64 borrow)
    %65 = loadvar.bool r2
    call @println(%65 borrow)
    %66 = loadvar.bool r3
    call @println(%66 borrow)
    %67 = loadvar.bool r4
    call @println(%67 borrow)
    %68 = bconst true
    local __sc_1: bool = %68
    %69 = loadvar.bool __sc_1
    br %69, L2, L1

  L1:
    %70 = bconst false
    local __sc_2: bool = %70
    %71 = loadvar.bool __sc_2
    br %71, L3, L4

  L2:
    %72 = loadvar.bool __sc_1
    local r5: bool = %72
    %73 = bconst false
    local __sc_4: bool = %73
    %74 = loadvar.bool __sc_4
    br %74, L5, L6

  L3:
    %75 = bconst false
    storevar __sc_2, %75
    jmp L4

  L4:
    %76 = loadvar.bool __sc_2
    storevar __sc_1, %76
    jmp L2

  L5:
    %77 = bconst true
    storevar __sc_4, %77
    jmp L6

  L6:
    %78 = loadvar.bool __sc_4
    local __sc_3: bool = %78
    %79 = loadvar.bool __sc_3
    br %79, L8, L7

  L7:
    %80 = bconst true
    storevar __sc_3, %80
    jmp L8

  L8:
    %81 = loadvar.bool __sc_3
    local r6: bool = %81
    %82 = bconst false
    local __sc_6: bool = %82
    %83 = loadvar.bool __sc_6
    br %83, L9, L10

  L9:
    %84 = bconst false
    storevar __sc_6, %84
    jmp L10

  L10:
    %85 = loadvar.bool __sc_6
    local __sc_5: bool = %85
    %86 = loadvar.bool __sc_5
    br %86, L12, L11

  L11:
    %87 = bconst false
    storevar __sc_5, %87
    jmp L12

  L12:
    %88 = loadvar.bool __sc_5
    local r7: bool = %88
    %89 = loadvar.bool r5
    call @println(%89 borrow)
    %90 = loadvar.bool r6
    call @println(%90 borrow)
    %91 = loadvar.bool r7
    call @println(%91 borrow)
    %92 = const.int32 4
    local a: int32 = %92
    %93 = const.int32 2
    local b: int32 = %93
    %94 = const.int32 3
    local c: int32 = %94
    %95 = loadvar.int32 a
    %96 = loadvar.int32 b
    %97 = loadvar.int32 c
    %98 = binop "*", %96, %97
    %99 = binop "+", %95, %98
    %100 = loadvar.int32 a
    %101 = loadvar.int32 b
    %102 = binop "*", %100, %101
    %103 = loadvar.int32 c
    %104 = binop "+", %102, %103
    %105 = binop ">", %99, %104
    local r8: bool = %105
    %106 = loadvar.int32 a
    %107 = loadvar.int32 b
    %108 = binop "*", %106, %107
    %109 = loadvar.int32 c
    %110 = binop "+", %108, %109
    %111 = loadvar.int32 a
    %112 = loadvar.int32 b
    %113 = binop "+", %111, %112
    %114 = loadvar.int32 c
    %115 = binop "+", %113, %114
    %116 = binop "==", %110, %115
    local r9: bool = %116
    %117 = loadvar.bool r8
    call @println(%117 borrow)
    %118 = loadvar.bool r9
    call @println(%118 borrow)
    %119 = const.int32 2
    %120 = const.int32 3
    %121 = binop "+", %119, %120
    %122 = const.int32 4
    %123 = binop "*", %121, %122
    call @println(%123 borrow)
    %124 = const.int32 2
    %125 = const.int32 3
    %126 = const.int32 4
    %127 = binop "+", %125, %126
    %128 = binop "*", %124, %127
    call @println(%128 borrow)
    %129 = const.int32 10
    %130 = const.int32 2
    %131 = binop "-", %129, %130
    %132 = const.int32 2
    %133 = binop "**", %131, %132
    call @println(%133 borrow)
    ret
}

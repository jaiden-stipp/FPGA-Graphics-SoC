// Freestanding compiler ABI helper for toolchains that lower C integer
// multiplication to a runtime call. Baseline RV32I only; no M extension.
// Kept in an archive so programs that do not need it are unchanged.
.section .text.__mulsi3,"ax",@progbits
.globl __mulsi3
.type __mulsi3,@function
__mulsi3:
    mv t0, a0
    li a0, 0
1:  beqz a1, 3f
    andi t1, a1, 1
    beqz t1, 2f
    add a0, a0, t0
2:  slli t0, t0, 1
    srli a1, a1, 1
    j 1b
3:  ret
.size __mulsi3, .-__mulsi3

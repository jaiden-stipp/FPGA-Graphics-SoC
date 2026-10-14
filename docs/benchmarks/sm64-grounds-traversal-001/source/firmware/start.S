.section .text.start
.globl _start
_start:
    .option norelax
    la sp, _stack_top
#ifdef SOC_SDRAM_EXEC
    // Fail locally on incompatible hardware rather than fetching unmapped code.
    li t0, 0x4000009c
    lw t1, 0(t0)
    andi t1, t1, 4
    bnez t1, 4f
    li t0, 0x40000018
    li t1, 0xdead00c3
    sw t1, 0(t0)
5:  j 5b
4:  la t0, _local_bss_start
    la t1, _local_bss_end
6:  bgeu t0, t1, 7f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 6b
7:
#endif
    la t0, _bss_start
    la t1, _bss_end
1:
    bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:
#ifdef SOC_STACK_CANARY
    // Opt-in engine experiment: paint unused local RAM before any stack use.
    la t0, _local_bss_end
    la t1, _stack_top
    li t2, 0xa55a3cc3
8:  bgeu t0, t1, 9f
    sw t2, 0(t0)
    addi t0, t0, 4
    j 8b
9:
#endif
    call main
3:
    j 3b

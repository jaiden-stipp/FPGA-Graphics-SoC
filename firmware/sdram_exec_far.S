// Real executed instructions beyond a 64 KiB code footprint.
.option norvc
.section .text.far,"ax"
.balign 65536
.global far_step
far_step:
    li t0,0x40000000
    .rept 5
    nop
    .endr
    // Deliberately cross cold instruction lines while MEM owns FIFO writes.
    sw a0,0(t0)
    addi a0,a0,1
    .rept 6
    nop
    .endr
    sw a0,0(t0)
    addi a0,a0,1
    .rept 6
    nop
    .endr
    sw a0,0(t0)
    addi a0,a0,1
    .rept 6
    nop
    .endr
    sw a0,0(t0)
    addi a0,a0,1
    ret

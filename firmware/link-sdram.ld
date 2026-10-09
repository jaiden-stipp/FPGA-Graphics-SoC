OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
    RAM (rwx) : ORIGIN = 0, LENGTH = 64K
    SDRAM (rw) : ORIGIN = 0x80000000, LENGTH = 128M
}
SECTIONS {
    .text : { KEEP(*(.text.start)) *(.text .text.*) } > RAM
    .game_assets : {
        . = ALIGN(4); _assets_start = .;
        KEEP(*(.game_assets))
        . = ALIGN(4); _assets_end = .;
    } > SDRAM
    .rodata : { *(.rodata .rodata.*) } > RAM
    .data : { *(.data .data.* .sdata .sdata.*) } > RAM
    .bss (NOLOAD) : {
        . = ALIGN(4); _bss_start = .;
        *(.bss .bss.* .sbss .sbss.*) *(COMMON)
        . = ALIGN(4); _bss_end = .;
    } > RAM
    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(_bss_end <= _stack_top - 4096, "Firmware leaves less than 4 KiB stack")
    ASSERT(_assets_end < 0x87fff000, "Assets overlap SDRAM self-test scratch page")
}

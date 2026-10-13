OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
    RAM (rwx) : ORIGIN = 0, LENGTH = 64K
    EXEC (rx) : ORIGIN = 0x80000000, LENGTH = 16M
    DATA (rw) : ORIGIN = 0x81000000, LENGTH = 112M - 4K
}
PHDRS { boot PT_LOAD; code PT_LOAD; localdata PT_LOAD; state PT_LOAD; assets PT_LOAD; }
SECTIONS {
    .boot : {
        KEEP(*(.text.start)) *(.text.local .text.local.*)
        *(.text.gfx_* .text.crc_byte .text.send_byte .text.send_packed)
    } > RAM :boot
    .local_data : { . = ALIGN(4); *(.local_data .local_data.*) } > RAM :localdata
    .local_bss (NOLOAD) : {
        . = ALIGN(4); _local_bss_start = .; *(.local_bss .local_bss.*)
        . = ALIGN(4); _local_bss_end = .;
    } > RAM :localdata
    .text : { _code_start = .; *(.text .text.*) } > EXEC :code
    .rodata : { *(.rodata .rodata.*) . = ALIGN(4); _code_end = .; } > EXEC :code
    .data : {
        _data_start = .; *(.data .data.* .sdata .sdata.*)
        . = ALIGN(4); _data_end = .;
    } > DATA :state
    .bss (NOLOAD) : {
        . = ALIGN(4); _bss_start = .;
        *(.bss .bss.* .sbss .sbss.*) *(COMMON)
        . = ALIGN(4); _bss_end = .;
    } > DATA :state
    .game_assets ALIGN(32) : {
        _assets_start = .; KEEP(*(.game_assets))
        . = ALIGN(4); _assets_end = .;
    } > DATA :assets
    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
    ASSERT(_local_bss_end <= _stack_top - 4096, "Local boot/data leave less than 4 KiB stack")
    ASSERT(_code_end <= 0x81000000, "Executable exceeds immutable 16 MiB window")
    ASSERT(_assets_end <= 0x87fff000, "Writable state/assets overlap self-test scratch")
}

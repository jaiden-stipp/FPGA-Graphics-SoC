#include "soc.h"
#include "gfx_protocol.h"
#include "cpu_profile.h"

#ifdef SOC_PROFILE
volatile uint32_t gfx_profile_command_cycles, gfx_profile_fifo_cycles;
volatile uint32_t gfx_profile_bytes, gfx_profile_commands;
#endif
static uint16_t crc_byte(uint16_t crc, uint8_t byte) {
    FINE_START(crc_start);
    // Two nibble lookups preserve CCITT-FALSE exactly. A 32-byte software
    // table avoids eight bit iterations per byte on the unchanged RV32I CPU.
    static const uint16_t table[16]={0x0000,0x1021,0x2042,0x3063,
        0x4084,0x50a5,0x60c6,0x70e7,0x8108,0x9129,0xa14a,0xb16b,
        0xc18c,0xd1ad,0xe1ce,0xf1ef};
    uint16_t mixed=(uint16_t)(crc^((uint16_t)byte<<8));
    mixed=(uint16_t)((mixed<<4)^table[mixed>>12]);
    uint16_t result=(uint16_t)((mixed<<4)^table[mixed>>12]);
    FINE_END(PROFILE_CRC,crc_start);
    return result;
}

#ifdef GFX_DMA
#if defined(GFX_PACKED) || defined(GFX_BATCHED)
#error Choose one graphics transport
#endif
#ifndef GFX_DMA_BUFFER_BYTES
#define GFX_DMA_BUFFER_BYTES 1024u
#endif
#ifndef GFX_DMA_BUFFER
#define GFX_DMA_BUFFER(index) ((volatile uint32_t *)(uintptr_t)(0x87fe0000u+(index)*GFX_DMA_BUFFER_BYTES))
#endif
static uint32_t dma_checked,dma_buffer,dma_size,dma_word,dma_count,dma_words,dma_sequence,dma_active;
// Local command state avoids persistent-state loads/stores on every byte.
typedef struct { uint32_t word,count,size,words,buffer; } dma_builder_t;
static void dma_save(const dma_builder_t *tx) {
    dma_word=tx->word;dma_count=tx->count;dma_size=tx->size;
    dma_words=tx->words;dma_buffer=tx->buffer;
}
static int dma_check(void) {
    if(dma_checked)return 0;
    if(!(SOC_CPU_FEATURES&SOC_FEATURE_GPU_REGS) || !(SOC_GPU_FEATURES&SOC_GPU_FEATURE_DMA) || GFX_DMA_ABI!=0x444d0101u)return -1;
    dma_checked=1;return 0;
}
static int dma_wait(void) {
#ifdef SOC_PROFILE
    uint32_t wait_start=SOC_CYCLES;
#endif
    for(uint32_t tries=0;tries<20000000u;++tries) {
        uint32_t status=GFX_DMA_STATUS;
        if(((status&2u) && dma_active) || GFX_ERRORS)return -1;
        if(!(status&1u)) {
            // Loader reset can leave a previous descriptor error/completion.
            // Only our active descriptor owns these fields; valid START clears it.
            if(dma_active && GFX_DMA_COMPLETED!=dma_sequence)return -1;
            dma_active=0;
#ifdef SOC_PROFILE
            gfx_profile_fifo_cycles+=SOC_CYCLES-wait_start;
#endif
            return 0;
        }
    }
    return -1;
}
static int dma_publish(void) {
    if(!dma_size)return 0;
    if(dma_count)GFX_DMA_BUFFER(dma_buffer)[dma_words++]=dma_word;
    // CPU stores complete at the write-through SDRAM acknowledgement. Publish
    // only after every staged word is committed and the old descriptor finishes.
    if(dma_wait())return -1;
    GFX_DMA_SOURCE=0x87fe0000u+dma_buffer*GFX_DMA_BUFFER_BYTES;
    GFX_DMA_LENGTH=dma_size;
    ++dma_sequence;
    GFX_DMA_ID=dma_sequence;
    GFX_DMA_START=1u;
    dma_active=1;
    dma_buffer^=1u;dma_size=0;dma_word=0;dma_count=0;dma_words=0;
    return 0;
}
#endif
#if defined(GFX_BATCHED) || defined(GFX_PACKED)
static uint32_t tx_budget;
#endif
#ifdef GFX_PACKED
static uint32_t tx_word,tx_count,packed_checked;
static int send_packed(uint32_t word,uint32_t count) {
#ifdef SOC_PROFILE
    uint32_t waiting=0,wait_start=0;
#endif
    for(uint32_t tries=0;tries<20000000u;++tries) {
        FINE_START(check_start);
        if(tx_budget<count) {
            if(GFX_ERRORS) {FINE_END(PROFILE_TX_CHECK,check_start);return -1;}
            tx_budget=GFX_FREE;
        }
        uint32_t ready=tx_budget>=count;
        FINE_END(PROFILE_TX_CHECK,check_start);
        if(ready) {
            tx_budget-=count;
#ifdef SOC_PROFILE
            if(waiting)gfx_profile_fifo_cycles+=SOC_CYCLES-wait_start;
#endif
            FINE_START(write_start);
            GFX_PACKED_DATA(count)=word;
            FINE_END(PROFILE_TX_WRITE,write_start);
            return 0;
        }
#ifdef SOC_PROFILE
        if(!waiting){waiting=1;wait_start=SOC_CYCLES;}
#endif
    }
    return -1;
}
#endif
#ifdef GFX_DMA
#define GFX_SEND(byte) send_byte(byte,&builder)
static int send_byte(uint8_t byte,dma_builder_t *tx) {
#else
#define GFX_SEND(byte) send_byte(byte)
static int send_byte(uint8_t byte) {
#endif
#ifdef GFX_DMA
    tx->word|=(uint32_t)byte<<(tx->count<<3);
    ++tx->count;++tx->size;
    if(tx->count==4) {
        GFX_DMA_BUFFER(tx->buffer)[tx->words++]=tx->word;
        tx->word=0;tx->count=0;
    }
    if(tx->size==GFX_DMA_BUFFER_BYTES) {
        dma_save(tx);
        if(dma_publish())return -1;
        tx->word=0;tx->count=0;tx->size=0;tx->words=0;tx->buffer^=1u;
    }
    return 0;
#elif defined(GFX_PACKED)
    tx_word|=(uint32_t)byte<<(tx_count<<3);
    ++tx_count;
    if(tx_count==4) {
        int result=send_packed(tx_word,4);
        tx_word=0;tx_count=0;
        return result;
    }
    return 0;
#else
#ifdef SOC_PROFILE
    uint32_t waiting=0, wait_start=0;
#endif
    for (uint32_t tries = 0; tries < 20000000u; ++tries) {
        FINE_START(check_start);
#ifdef GFX_BATCHED
        if (!tx_budget && GFX_ERRORS) { FINE_END(PROFILE_TX_CHECK,check_start); return -1; }
#else
        if (GFX_ERRORS) { FINE_END(PROFILE_TX_CHECK,check_start); return -1; }
#endif
#ifdef GFX_BATCHED
        // Only this CPU produces bytes. Consumer pops can only increase free space.
        if (!tx_budget) tx_budget=GFX_FREE;
        uint32_t ready=tx_budget;
#else
        uint32_t ready=GFX_STATUS & GFX_TX_READY;
#endif
        FINE_END(PROFILE_TX_CHECK,check_start);
        if (ready) {
#ifdef GFX_BATCHED
            --tx_budget;
#endif
#ifdef SOC_PROFILE
            if (waiting) gfx_profile_fifo_cycles += SOC_CYCLES-wait_start;
#endif
            FINE_START(write_start);
            GFX_DATA = byte;
            FINE_END(PROFILE_TX_WRITE,write_start);
            return 0;
        }
#ifdef SOC_PROFILE
        if (!waiting) { waiting=1; wait_start=SOC_CYCLES; }
#endif
    }
    return -1;
#endif
}

int gfx_command(uint8_t opcode, const uint8_t *payload, uint8_t length) {
#ifdef SOC_PROFILE
    uint32_t start=SOC_CYCLES;
#endif
#ifdef GFX_DMA
    if(dma_check())return -1;
    dma_builder_t builder={dma_word,dma_count,dma_size,dma_words,dma_buffer};
#endif
#ifdef GFX_PACKED
    if(!packed_checked) {
        if(!(SOC_CPU_FEATURES&SOC_FEATURE_GPU_REGS) || !(SOC_GPU_FEATURES&SOC_GPU_FEATURE_PACKED))return -1;
        packed_checked=1;
    }
    tx_word=0;tx_count=0;
#endif
#if defined(GFX_BATCHED) || defined(GFX_PACKED)
    tx_budget=0; // Refresh reservation for each command; bounded by FIFO free count.
#endif
    uint8_t header[5] = {GFX_MAGIC_0, GFX_MAGIC_1, GFX_VERSION, opcode, length};
    uint16_t crc = 0xffffu;
    for (unsigned i = 0; i < 5; ++i) {
        crc = crc_byte(crc, header[i]);
        if (GFX_SEND(header[i])) return -1;
    }
    for (unsigned i = 0; i < length; ++i) {
        crc = crc_byte(crc, payload[i]);
        if (GFX_SEND(payload[i])) return -1;
    }
    if (GFX_SEND((uint8_t)(crc >> 8))) return -1;
    int result=GFX_SEND((uint8_t)crc);
#ifdef GFX_PACKED
    if(!result && tx_count)result=send_packed(tx_word,tx_count);
#endif
#if defined(GFX_BATCHED) || defined(GFX_PACKED)
    if (GFX_ERRORS) result=-1;
#endif
#ifdef GFX_DMA
    dma_save(&builder);
    // Frame boundary publishes the exact tail; commands may span buffers.
    if(!result && opcode==GFX_OP_END_FRAME)result=dma_publish();
#endif
#ifdef SOC_PROFILE
    gfx_profile_command_cycles += SOC_CYCLES-start;
    gfx_profile_bytes += (uint32_t)length+7u;
    ++gfx_profile_commands;
#endif
    return result;
}

int gfx_wait_frame(uint32_t frame_id) {
#ifdef GFX_DMA
    if(dma_check() || dma_publish() || dma_wait())return -1;
#endif
    for (uint32_t tries = 0; tries < 20000000u; ++tries) {
        if (GFX_ERRORS) return -1;
        if ((GFX_STATUS & GFX_FRAME_DONE) && GFX_FRAME_ID == frame_id) {
            GFX_ACK = 1u;
            return 0;
        }
    }
    return -1;
}

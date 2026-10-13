// Explicit freestanding C memory services. Volatile byte access prevents the
// compiler from replacing these loops with recursive libc helper calls.
#include <stddef.h>
#include <stdint.h>
void *memset(void *destination,int value,size_t count) {
    volatile uint8_t *out=(volatile uint8_t *)destination;
    for(size_t i=0;i<count;++i)out[i]=(uint8_t)value;
    return destination;
}
void *memcpy(void *destination,const void *source,size_t count) {
    volatile uint8_t *out=(volatile uint8_t *)destination;
    const volatile uint8_t *in=(const volatile uint8_t *)source;
    for(size_t i=0;i<count;++i)out[i]=in[i];
    return destination;
}
void *memmove(void *destination,const void *source,size_t count) {
    volatile uint8_t *out=(volatile uint8_t *)destination;
    const volatile uint8_t *in=(const volatile uint8_t *)source;
    if((uintptr_t)destination<(uintptr_t)source){for(size_t i=0;i<count;++i)out[i]=in[i];}
    else {while(count){--count;out[count]=in[count];}}
    return destination;
}

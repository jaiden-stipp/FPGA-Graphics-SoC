#include "soc.h"
#include "sdram.h"
int main(void) {
    SOC_SCRATCH=0x5dad0000u;
    SOC_SCRATCH=sdram_self_test();
    for (;;) { }
}

#ifndef GAME_PORT_H
#define GAME_PORT_H
#include <stdint.h>
// Direct calls keep game modules independent of the freestanding entry point.
// init: initialize game state. update: one 30 Hz tick. render: submit a complete
// frame (view, begin, draws, end); the common entry point waits for presentation.
int game_port_init(void);
void game_port_update(uint32_t buttons);
int game_port_render(uint32_t frame);
#endif

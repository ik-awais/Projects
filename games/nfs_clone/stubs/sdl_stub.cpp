// sdl_stub.cpp - fake SDL2 implementation, for end-to-end testing of
// main.cpp's logic only. Creates no real window; runs the game loop for a
// handful of frames (simulating the W key held down) then delivers
// SDL_QUIT.
#include "SDL.h"
#include <cstdio>

void* fakeGetProcAddress(const char* name); // from gl_stub.cpp

extern "C" {

int SDL_Init(Uint32) { return 0; }
void SDL_Quit() {}
const char* SDL_GetError() { return "(stub) no error"; }

int SDL_GL_SetAttribute(SDL_GLattr, int) { return 0; }
int SDL_GL_SetSwapInterval(int) { return 0; }
void* SDL_GL_GetProcAddress(const char* proc) { return fakeGetProcAddress(proc); }
SDL_GLContext SDL_GL_CreateContext(SDL_Window*) { return reinterpret_cast<SDL_GLContext>(1); }
void SDL_GL_DeleteContext(SDL_GLContext) {}
void SDL_GL_SwapWindow(SDL_Window*) {}

SDL_Window* SDL_CreateWindow(const char*, int, int, int, int, Uint32) {
    return reinterpret_cast<SDL_Window*>(1);
}
void SDL_DestroyWindow(SDL_Window*) {}
void SDL_GetWindowSize(SDL_Window*, int* w, int* h) { *w = 1280; *h = 720; }

static int pollCount = 0;
static bool quitDelivered = false;
int SDL_PollEvent(SDL_Event* event) {
    if (quitDelivered) return 0; // queue empty
    ++pollCount;
    if (pollCount >= 240) { // ~4 seconds of simulated frames at 60fps
        event->type = SDL_QUIT;
        quitDelivered = true;
        return 1;
    }
    return 0;
}

static Uint64 perfCounter = 0;
Uint64 SDL_GetPerformanceCounter() { perfCounter += 16667; return perfCounter; }
Uint64 SDL_GetPerformanceFrequency() { return 1000000; }

static Uint8 keyState[512] = {0};
const Uint8* SDL_GetKeyboardState(int* numkeys) {
    if (numkeys) *numkeys = 512;
    keyState[SDL_SCANCODE_W] = 1;     // hold throttle
    keyState[SDL_SCANCODE_D] = 1;     // and steer right, to exercise turning + collisions
    return keyState;
}

} // extern "C"

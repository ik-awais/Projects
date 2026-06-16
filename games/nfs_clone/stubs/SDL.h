// STUB for syntax-checking only - mimics the subset of the SDL2 API that
// this project uses. NOT a real SDL2 header.
#pragma once

extern "C" {

typedef unsigned char Uint8;
typedef unsigned int Uint32;
typedef unsigned long long Uint64;

struct SDL_Window;
typedef void* SDL_GLContext;

// ---- init / shutdown ----
#define SDL_INIT_VIDEO 0x00000020
int SDL_Init(Uint32 flags);
void SDL_Quit();
const char* SDL_GetError();

// ---- GL attributes ----
typedef enum {
    SDL_GL_CONTEXT_MAJOR_VERSION,
    SDL_GL_CONTEXT_MINOR_VERSION,
    SDL_GL_CONTEXT_PROFILE_MASK,
    SDL_GL_CONTEXT_FLAGS,
    SDL_GL_DOUBLEBUFFER,
    SDL_GL_DEPTH_SIZE,
    SDL_GL_MULTISAMPLEBUFFERS,
    SDL_GL_MULTISAMPLESAMPLES
} SDL_GLattr;

#define SDL_GL_CONTEXT_PROFILE_CORE 0x0001
#define SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG 0x0002

int SDL_GL_SetAttribute(SDL_GLattr attr, int value);
int SDL_GL_SetSwapInterval(int interval);
void* SDL_GL_GetProcAddress(const char* proc);
SDL_GLContext SDL_GL_CreateContext(SDL_Window* window);
void SDL_GL_DeleteContext(SDL_GLContext context);
void SDL_GL_SwapWindow(SDL_Window* window);

// ---- window ----
#define SDL_WINDOWPOS_CENTERED 0x2FFF0000
#define SDL_WINDOW_OPENGL 0x00000002
#define SDL_WINDOW_RESIZABLE 0x00000020

SDL_Window* SDL_CreateWindow(const char* title, int x, int y, int w, int h, Uint32 flags);
void SDL_DestroyWindow(SDL_Window* window);
void SDL_GetWindowSize(SDL_Window* window, int* w, int* h);

// ---- events ----
#define SDL_QUIT 0x100
#define SDL_KEYDOWN 0x300

typedef int SDL_Keycode;
#define SDLK_ESCAPE 27
#define SDLK_r 'r'

struct SDL_Keysym { SDL_Keycode sym; };
struct SDL_KeyboardEvent { Uint32 type; SDL_Keysym keysym; };

union SDL_Event {
    Uint32 type;
    SDL_KeyboardEvent key;
};

int SDL_PollEvent(SDL_Event* event);

// ---- timing ----
Uint64 SDL_GetPerformanceCounter();
Uint64 SDL_GetPerformanceFrequency();

// ---- keyboard ----
typedef enum {
    SDL_SCANCODE_W = 26, SDL_SCANCODE_A = 4, SDL_SCANCODE_S = 22, SDL_SCANCODE_D = 7,
    SDL_SCANCODE_UP = 82, SDL_SCANCODE_DOWN = 81, SDL_SCANCODE_LEFT = 80, SDL_SCANCODE_RIGHT = 79,
    SDL_SCANCODE_SPACE = 44, SDL_SCANCODE_ESCAPE = 41
} SDL_Scancode;

const Uint8* SDL_GetKeyboardState(int* numkeys);

} // extern "C"

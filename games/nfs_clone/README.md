# C++ Racer — a small 3D arcade racing prototype

A real, working 3D driving prototype in C++17 using **SDL2 + raw OpenGL 3.3
core profile** (no GLEW/GLAD/GLM — a ~30-function GL loader is included).
Drive a car around a wavy closed-loop track against one AI opponent, with
arcade-style acceleration/braking/steering, a handbrake drift mechanic,
guard-rail collisions, a chase camera, basic directional lighting + fog, and
an in-HUD speedometer/lap tracker.

This is an honest **starting point**, not a finished commercial game — see
[Scope & roadmap](#scope--roadmap) at the bottom for what's deliberately
left out and how you could extend it.

## Controls

| Key            | Action                  |
|----------------|-------------------------|
| W / Up         | Throttle                |
| S / Down       | Brake / reverse         |
| A / D, Left/Right | Steer left / right   |
| Space          | Handbrake (drift)       |
| R              | Reset to start line     |
| Esc            | Quit                    |

The HUD shows a speedometer (bottom-left, green→yellow→red), a drift
indicator next to it (lights up orange while drifting), and lap progress
squares (top-left, fills in as you complete laps). First to 3 laps wins —
the result is printed to the console.

## Building

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install build-essential cmake libsdl2-dev libgl1-mesa-dev

cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

./build/cpp_racer
```

### Windows (vcpkg + Visual Studio)

```powershell
git clone https://github.com/microsoft/vcpkg
.\vcpkg\bootstrap-vcpkg.bat
.\vcpkg\vcpkg install sdl2:x64-windows

cmake -B build -DCMAKE_TOOLCHAIN_FILE=<path-to-vcpkg>/scripts/buildsystems/vcpkg.cmake -A x64
cmake --build build --config Release

.\build\Release\cpp_racer.exe
```

(MSYS2/MinGW also works: `pacman -S mingw-w64-x86_64-SDL2 mingw-w64-x86_64-cmake mingw-w64-x86_64-toolchain`,
then the same `cmake -B build && cmake --build build`.)

### macOS (Homebrew)

```bash
brew install sdl2 cmake

cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

./build/cpp_racer
```

OpenGL is deprecated-but-present on macOS up to OpenGL 4.1 core profile,
which is enough for this project (we only require 3.3).

## Project layout

```
include/        headers (math, physics, geometry, track, AI, camera, HUD, GL/shader/mesh wrappers)
src/            implementation files + main.cpp (game loop)
tests/          standalone console tests for the non-GL logic (see below)
stubs/          fake SDL2/GL headers + implementations used only to test-build main.cpp here
CMakeLists.txt  cross-platform build
```

Architecture, file by file:

- **`math3d.h`** — header-only Vec2/Vec3/Vec4/Mat4 (column-major, OpenGL-compatible). No dependencies.
- **`car.h`/`car.cpp`** — arcade car physics: engine force, drag, rolling resistance, speed-sensitive steering, and a handbrake-based grip/drift model. Pure logic, no rendering.
- **`geometry.h`** — CPU-side mesh generation: boxes, checkerboard ground, road "ribbon" along a centerline, striped guard-rail barriers.
- **`track.h`/`track.cpp`** — generates the closed-loop track centerline, checkpoints, and meshes; `resolveTrackCollision()` keeps cars inside the guard rails.
- **`ai.h`/`ai.cpp`** — waypoint-following AI driver (steers toward the next checkpoint, throttles down and drifts through sharp corners) + `LapTracker` for the player's lap count.
- **`camera.h`** — smoothed third-person chase camera.
- **`hud.h`** — builds the speedometer/drift/lap-progress quads as plain mesh data.
- **`gl_core.h`/`gl_core.cpp`** — minimal OpenGL 3.3 function loader (via `SDL_GL_GetProcAddress`); on macOS this is a no-op since `<OpenGL/gl3.h>` declares everything directly.
- **`shader.h`/`shader.cpp`**, **`shaders.h`** — GLSL program wrapper + the two shaders used (3D lit scene with fog, 2D HUD overlay).
- **`mesh.h`/`mesh.cpp`** — VAO/VBO/EBO wrapper.
- **`main.cpp`** — SDL2 window/context setup, fixed-timestep game loop, input, rendering.

## Testing

The physics, track generation, AI, camera, and HUD logic are all pure C++
with no SDL/OpenGL dependency, so they're covered by standalone tests in
`tests/`:

```bash
g++ -std=c++17 -O2 -o test_car      tests/test_car.cpp      src/car.cpp
g++ -std=c++17 -O2 -o test_track    tests/test_track.cpp    src/track.cpp src/ai.cpp src/car.cpp
g++ -std=c++17 -O2 -o test_camera_hud tests/test_camera_hud.cpp src/car.cpp
g++ -std=c++17 -O2 -o test_math3d   tests/test_math3d.cpp

./test_car
./test_track
./test_camera_hud
./test_math3d
```

`tests/test_track.cpp` runs a 90-second AI driving simulation and checks
that it completes full laps while staying within the track boundary —
useful if you tune the physics/track constants and want to sanity-check the
result without opening a window.

The `stubs/` directory contains fake SDL2/OpenGL implementations used only
to compile-and-run `main.cpp` in environments without real SDL2/GL dev
headers (e.g. this prototype was built and smoke-tested that way). They are
**not** needed for a normal build — `CMakeLists.txt` links against the real
SDL2/OpenGL on your system.

## Scope & roadmap

What's here: a genuinely playable, cross-platform 3D driving loop with real
(if simple) physics, one AI opponent, track collisions, lighting/fog, and a
HUD. What's deliberately **not** here, and how you'd add it:

- **Visuals**: cars/track are boxes/ribbons with flat colors — no textured
  models. You could load `.obj` models (e.g. with a small custom loader or
  `tinyobjloader`) and extend `Mesh`/the shaders with UVs + texture sampling.
- **Car-vs-car collision**: only car-vs-barrier collision is implemented.
  Add a simple circle/box overlap check between `playerCar` and `aiCar` in
  `main.cpp`'s fixed-step loop.
- **More AI opponents / better AI**: `AIDriver` is a single-waypoint
  follower. Multiple instances work as-is; smarter racing lines, rubber-
  banding, or avoidance would build on top of `computeInput()`.
- **On-screen text** (lap times, "You win!", main menu): the HUD currently
  uses colored quads only (to avoid a font-rendering dependency). Adding a
  bitmap-font texture + textured quads is the natural next step.
- **Sound**: not included; SDL2's `SDL_mixer` is the simplest addition.
- **More interesting track**: the centerline is a single perturbed ellipse.
  `geometry.h`'s `makeRibbon`/`makeBarriers` work with any closed-loop point
  list, so you can hand-author or procedurally generate more elaborate
  tracks (chicanes, elevation changes, branching).

// main.cpp - SDL2 + OpenGL 3.3 core profile racing prototype
#include <SDL.h>

#include "../include/gl_core.h"
#include "../include/math3d.h"
#include "../include/geometry.h"
#include "../include/car.h"
#include "../include/track.h"
#include "../include/ai.h"
#include "../include/camera.h"
#include "../include/hud.h"
#include "../include/shader.h"
#include "../include/mesh.h"
#include "../include/shaders.h"

#include <cstdio>
#include <cmath>
#include <string>

using namespace m3d;

static const int TOTAL_LAPS = 3;
static const float TOP_SPEED_MS = 70.0f; // used to scale the HUD speedometer
static const float FIXED_DT = 1.0f / 60.0f;

int main(int /*argc*/, char** /*argv*/) {
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        std::fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }

    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
#ifdef __APPLE__
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG);
#endif
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1);
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 4);

    int windowW = 1280, windowH = 720;
    SDL_Window* window = SDL_CreateWindow(
        "C++ Racer - WASD/Arrows to drive, Space to drift, R to reset, Esc to quit",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        windowW, windowH, SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
    if (!window) {
        std::fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    SDL_GLContext glContext = SDL_GL_CreateContext(window);
    if (!glContext) {
        std::fprintf(stderr, "SDL_GL_CreateContext failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    SDL_GL_SetSwapInterval(1); // vsync

    if (!gl_core_load(SDL_GL_GetProcAddress)) {
        std::fprintf(stderr, "Failed to load required OpenGL 3.3 functions.\n");
        std::fprintf(stderr, "Make sure your GPU driver supports OpenGL 3.3 core profile.\n");
        SDL_GL_DeleteContext(glContext);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_MULTISAMPLE);

    // ------------------------------------------------------------------
    // World geometry
    // ------------------------------------------------------------------
    Track track;
    track.generate();

    Mesh groundMesh, roadMesh, barrierMesh;
    groundMesh.upload(track.groundMesh);
    roadMesh.upload(track.roadMesh);
    barrierMesh.upload(track.barrierMesh);

    const Vec3 bodyHalf(0.9f, 0.45f, 2.0f);
    const Vec3 wheelHalf(0.35f, 0.35f, 0.25f);

    Mesh playerBodyMesh, aiBodyMesh, wheelMesh;
    playerBodyMesh.upload(makeBox(bodyHalf, Vec3(0.15f, 0.35f, 0.95f))); // blue
    aiBodyMesh.upload(makeBox(bodyHalf, Vec3(0.90f, 0.15f, 0.15f)));     // red
    wheelMesh.upload(makeBox(wheelHalf, Vec3(0.05f, 0.05f, 0.05f)));     // near-black

    const Vec3 wheelOffsets[4] = {
        Vec3(-0.95f, -0.35f,  1.4f), // front-left
        Vec3( 0.95f, -0.35f,  1.4f), // front-right
        Vec3(-0.95f, -0.35f, -1.4f), // rear-left
        Vec3( 0.95f, -0.35f, -1.4f), // rear-right
    };

    // ------------------------------------------------------------------
    // Shaders
    // ------------------------------------------------------------------
    Shader sceneShader, hudShader;
    std::string err;
    if (!sceneShader.compile(kSceneVertexShader, kSceneFragmentShader, err)) {
        std::fprintf(stderr, "Scene shader error: %s\n", err.c_str());
        return 1;
    }
    if (!hudShader.compile(kHudVertexShader, kHudFragmentShader, err)) {
        std::fprintf(stderr, "HUD shader error: %s\n", err.c_str());
        return 1;
    }

    Mesh hudMesh;

    // ------------------------------------------------------------------
    // Cars, AI, camera
    // ------------------------------------------------------------------
    Car playerCar, aiCar;
    playerCar.reset(track.spawnPosition(0), track.spawnHeading());
    aiCar.reset(track.spawnPosition(1), track.spawnHeading());

    AIDriver ai;
    LapTracker playerLap;
    ChaseCamera camera;
    camera.update(0.0f, playerCar);

    bool playerWon = false, aiWon = false;

    double accumulator = 0.0;
    Uint64 lastCounter = SDL_GetPerformanceCounter();
    const Uint64 freq = SDL_GetPerformanceFrequency();

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) {
                running = false;
            } else if (e.type == SDL_KEYDOWN) {
                if (e.key.keysym.sym == SDLK_ESCAPE) {
                    running = false;
                } else if (e.key.keysym.sym == SDLK_r) {
                    playerCar.reset(track.spawnPosition(0), track.spawnHeading());
                    aiCar.reset(track.spawnPosition(1), track.spawnHeading());
                    ai = AIDriver();
                    playerLap = LapTracker();
                    playerWon = aiWon = false;
                    camera.initialized = false;
                    camera.update(0.0f, playerCar);
                }
            }
        }

        Uint64 now = SDL_GetPerformanceCounter();
        double frameTime = double(now - lastCounter) / double(freq);
        lastCounter = now;
        if (frameTime > 0.25) frameTime = 0.25; // clamp to avoid spiral-of-death on hitches
        accumulator += frameTime;

        const Uint8* keys = SDL_GetKeyboardState(nullptr);
        bool handbrakeHeld = keys[SDL_SCANCODE_SPACE] != 0;

        while (accumulator >= FIXED_DT) {
            CarInput playerInput;
            if (keys[SDL_SCANCODE_W] || keys[SDL_SCANCODE_UP]) playerInput.throttle = 1.0f;
            else if (keys[SDL_SCANCODE_S] || keys[SDL_SCANCODE_DOWN]) playerInput.throttle = -1.0f;

            float steer = 0.0f;
            if (keys[SDL_SCANCODE_D] || keys[SDL_SCANCODE_RIGHT]) steer += 1.0f;
            if (keys[SDL_SCANCODE_A] || keys[SDL_SCANCODE_LEFT])  steer -= 1.0f;
            playerInput.steer = steer;
            playerInput.handbrake = handbrakeHeld;

            if (!playerWon && !aiWon) {
                playerCar.update(FIXED_DT, playerInput);
                resolveTrackCollision(playerCar, track);
                playerLap.update(playerCar.position, track);

                CarInput aiInput = ai.computeInput(aiCar, track);
                aiCar.update(FIXED_DT, aiInput);
                resolveTrackCollision(aiCar, track);

                if (playerLap.lapCount >= TOTAL_LAPS && !playerWon) {
                    playerWon = true;
                    std::printf("\n*** You win! Press R to race again. ***\n");
                }
                if (ai.lapCount >= TOTAL_LAPS && !aiWon) {
                    aiWon = true;
                    std::printf("\n*** AI wins! Press R to race again. ***\n");
                }
            }

            camera.update(FIXED_DT, playerCar);
            accumulator -= FIXED_DT;
        }

        // --------------------------------------------------------------
        // Render
        // --------------------------------------------------------------
        SDL_GetWindowSize(window, &windowW, &windowH);
        if (windowW <= 0) windowW = 1;
        if (windowH <= 0) windowH = 1;
        glViewport(0, 0, windowW, windowH);

        const Vec3 skyColor(0.55f, 0.70f, 0.92f);
        glClearColor(skyColor.x, skyColor.y, skyColor.z, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        glEnable(GL_DEPTH_TEST);
        sceneShader.use();

        float aspect = float(windowW) / float(windowH);
        Mat4 proj = Mat4::perspective(toRadians(60.0f), aspect, 0.1f, 1000.0f);
        Mat4 view = camera.viewMatrix();

        sceneShader.setMat4("uProj", proj);
        sceneShader.setMat4("uView", view);
        sceneShader.setVec3("uLightDir", Vec3(0.4f, 1.0f, 0.3f).normalized());
        sceneShader.setVec3("uViewPos", camera.position);
        sceneShader.setVec3("uFogColor", skyColor);
        sceneShader.setFloat("uFogDensity", 0.0025f);

        Mat4 identity = Mat4::identity();
        sceneShader.setMat4("uModel", identity);
        groundMesh.draw();
        roadMesh.draw();
        barrierMesh.draw();

        auto drawCar = [&](const Car& car, Mesh& bodyMesh) {
            Mat4 model = car.modelMatrix();
            sceneShader.setMat4("uModel", model);
            bodyMesh.draw();
            for (int i = 0; i < 4; ++i) {
                float yaw = (i < 2) ? car.steerVisual : 0.0f; // front wheels steer
                Mat4 wheelModel = model * Mat4::translate(wheelOffsets[i]) * Mat4::rotateY(yaw);
                sceneShader.setMat4("uModel", wheelModel);
                wheelMesh.draw();
            }
        };
        drawCar(playerCar, playerBodyMesh);
        drawCar(aiCar, aiBodyMesh);

        // ---- HUD overlay ----
        glDisable(GL_DEPTH_TEST);
        hudShader.use();
        Mat4 ortho = Mat4::ortho(0.0f, float(windowW), 0.0f, float(windowH), -1.0f, 1.0f);
        hudShader.setMat4("uProj", ortho);

        float speedFrac = playerCar.speed() / TOP_SPEED_MS;
        bool drifting = handbrakeHeld && std::fabs(playerCar.lateralSpeed()) > 2.0f;
        MeshData hudData = buildHUD(speedFrac, playerLap.lapCount, TOTAL_LAPS, drifting,
                                     float(windowW), float(windowH));
        hudMesh.upload(hudData, /*dynamic=*/true);
        hudMesh.draw();

        SDL_GL_SwapWindow(window);
    }

    SDL_GL_DeleteContext(glContext);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}

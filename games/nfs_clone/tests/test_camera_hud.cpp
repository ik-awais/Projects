#include "../include/camera.h"
#include "../include/hud.h"
#include "../include/car.h"
#include <cstdio>

using namespace m3d;

int main() {
    // --- Camera follow test ---
    printf("=== Camera ===\n");
    Car car;
    car.reset(Vec3(0, 0, 0), 0.0f);
    ChaseCamera cam;
    cam.update(1.0f / 60.0f, car); // first call snaps to position
    printf("initial cam pos=(%.2f,%.2f,%.2f) target=(%.2f,%.2f,%.2f)\n",
           cam.position.x, cam.position.y, cam.position.z, cam.target.x, cam.target.y, cam.target.z);

    // Move the car forward suddenly; camera should smoothly follow, not teleport.
    car.position = Vec3(0, 0, 50);
    for (int i = 0; i < 60; ++i) cam.update(1.0f / 60.0f, car);
    printf("after 1s following: cam pos=(%.2f,%.2f,%.2f) target=(%.2f,%.2f,%.2f)\n",
           cam.position.x, cam.position.y, cam.position.z, cam.target.x, cam.target.y, cam.target.z);
    // Camera should be behind the car (car forward = +Z at heading 0, so camera should be at lower Z)
    if (cam.position.z < car.position.z && cam.position.y > 0)
        printf("[OK] camera trails behind and above the car\n");
    else
        printf("[FAIL] camera position looks wrong\n");

    // --- HUD test ---
    printf("\n=== HUD ===\n");
    MeshData hud0 = buildHUD(0.0f, 0, 3, false, 1280, 720);
    MeshData hud50 = buildHUD(0.5f, 1, 3, true, 1280, 720);
    MeshData hud100 = buildHUD(1.0f, 3, 3, false, 1280, 720);

    printf("hud0:   %zu verts, %zu indices\n", hud0.vertices.size(), hud0.indices.size());
    printf("hud50:  %zu verts, %zu indices\n", hud50.vertices.size(), hud50.indices.size());
    printf("hud100: %zu verts, %zu indices\n", hud100.vertices.size(), hud100.indices.size());

    // Expect: 2 quads (speedo bg+fill) + 1 drift quad + totalLaps(3) lap quads = 6 quads = 24 verts, 36 idx
    bool ok = (hud0.vertices.size() == 24 && hud0.indices.size() == 36);
    printf("%s vertex/index counts (24 verts, 36 idx expected)\n", ok ? "[OK]" : "[FAIL]");

    // Fill bar width at speed=0 should be ~0, at speed=1 should be near full width (220-6=214)
    // The fill quad is the 2nd quad => vertices 4..7, vertex[1].x - vertex[0].x = width
    float fillW0 = hud0.vertices[5].pos.x - hud0.vertices[4].pos.x;
    float fillW100 = hud100.vertices[5].pos.x - hud100.vertices[4].pos.x;
    printf("fill width at speed=0:   %.2f (expect ~0)\n", fillW0);
    printf("fill width at speed=100: %.2f (expect ~214)\n", fillW100);

    // Drift indicator color is the 3rd quad => vertices 8..11
    Vec3 driftColorOff = hud0.vertices[8].color;
    Vec3 driftColorOn  = hud50.vertices[8].color;
    printf("drift color (off)=(%.2f,%.2f,%.2f)  (on)=(%.2f,%.2f,%.2f)\n",
           driftColorOff.x, driftColorOff.y, driftColorOff.z, driftColorOn.x, driftColorOn.y, driftColorOn.z);

    // Lap indicators start at vertex 12 (4th quad), each quad = 4 verts
    // hud0: lapCount=0 -> all dim. hud100: lapCount=3 -> all bright.
    Vec3 lap0_hud0 = hud0.vertices[12].color;
    Vec3 lap0_hud100 = hud100.vertices[12].color;
    printf("lap0 color: hud0(lapCount=0)=(%.2f,%.2f,%.2f)  hud100(lapCount=3)=(%.2f,%.2f,%.2f)\n",
           lap0_hud0.x, lap0_hud0.y, lap0_hud0.z, lap0_hud100.x, lap0_hud100.y, lap0_hud100.z);

    return 0;
}

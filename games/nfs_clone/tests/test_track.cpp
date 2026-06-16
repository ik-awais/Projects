#include "../include/track.h"
#include "../include/ai.h"
#include "../include/car.h"
#include <cstdio>
#include <cmath>

using namespace m3d;

int main() {
    Track track;
    track.generate();

    printf("=== Track ===\n");
    printf("centerline points: %zu\n", track.centerline.size());
    printf("checkpoints: %zu\n", track.numCheckpoints());
    printf("groundMesh: %zu verts, %zu idx\n", track.groundMesh.vertices.size(), track.groundMesh.indices.size());
    printf("roadMesh:   %zu verts, %zu idx\n", track.roadMesh.vertices.size(), track.roadMesh.indices.size());
    printf("barrierMesh:%zu verts, %zu idx\n", track.barrierMesh.vertices.size(), track.barrierMesh.indices.size());

    // Check consecutive centerline segment lengths are reasonable (smooth curve)
    float maxSeg = 0, minSeg = 1e9f, totalLen = 0;
    size_t n = track.centerline.size();
    for (size_t i = 0; i < n; ++i) {
        Vec3 a = track.centerline[i];
        Vec3 b = track.centerline[(i + 1) % n];
        float len = (b - a).length();
        maxSeg = std::max(maxSeg, len);
        minSeg = std::min(minSeg, len);
        totalLen += len;
    }
    printf("segment length: min=%.2f max=%.2f  total loop length=%.1f m\n", minSeg, maxSeg, totalLen);

    // Spawn positions
    Vec3 p0 = track.spawnPosition(0);
    Vec3 p1 = track.spawnPosition(1);
    float h = track.spawnHeading();
    printf("spawn0=(%.2f,%.2f,%.2f) spawn1=(%.2f,%.2f,%.2f) heading=%.2f deg\n",
           p0.x, p0.y, p0.z, p1.x, p1.y, p1.z, toDegrees(h));

    // --- AI driving simulation ---
    printf("\n=== AI driving simulation (90 seconds) ===\n");
    Car car;
    car.reset(p1, h);
    AIDriver ai;

    const float dt = 1.0f / 60.0f;
    const int steps = 90 * 60;
    float maxDistFromOrigin = 0.0f;
    for (int i = 0; i < steps; ++i) {
        CarInput in = ai.computeInput(car, track);
        car.update(dt, in);
        resolveTrackCollision(car, track);
        float d = std::sqrt(car.position.x * car.position.x + car.position.z * car.position.z);
        maxDistFromOrigin = std::max(maxDistFromOrigin, d);

        if (i % (5 * 60) == 0) {
            printf("t=%5.1fs  pos=(%7.2f,%7.2f)  speed=%5.1f km/h  laps=%d  nextCP=%zu\n",
                   i * dt, car.position.x, car.position.z, car.speed() * 3.6f, ai.lapCount, ai.targetCheckpoint);
        }
    }
    printf("\nFinal lap count: %d\n", ai.lapCount);
    printf("Max distance from origin: %.2f (track radius ~ 140-160)\n", maxDistFromOrigin);

    if (ai.lapCount >= 1) printf("[OK] AI completed at least one full lap\n");
    else printf("[FAIL] AI did not complete a lap\n");

    if (maxDistFromOrigin < 250.0f) printf("[OK] AI stayed within plausible track bounds\n");
    else printf("[FAIL] AI flew off the track (maxDist=%.1f)\n", maxDistFromOrigin);

    return 0;
}

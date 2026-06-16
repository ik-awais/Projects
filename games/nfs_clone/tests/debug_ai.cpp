#include "../include/track.h"
#include "../include/ai.h"
#include "../include/car.h"
#include <cstdio>

using namespace m3d;

int main() {
    Track track;
    track.generate();

    Car car;
    car.reset(track.spawnPosition(1), track.spawnHeading());
    AIDriver ai;

    const float dt = 1.0f / 60.0f;
    for (int i = 0; i < 300; ++i) {
        CarInput in = ai.computeInput(car, track);
        size_t idx = track.nearestCenterlineIndex(car.position);
        Vec3 c = track.centerline[idx];
        float distToCenter = std::sqrt((car.position.x-c.x)*(car.position.x-c.x) + (car.position.z-c.z)*(car.position.z-c.z));

        car.update(dt, in);
        bool hit = false;
        Vec3 beforePos = car.position;
        resolveTrackCollision(car, track);
        if ((car.position - beforePos).length() > 1e-4f) hit = true;

        if (i % 10 == 0 || hit) {
            printf("i=%3d t=%5.2f pos=(%6.2f,%6.2f) heading=%6.1f speed=%5.1f fSpd=%5.1f throttle=%5.2f steer=%5.2f handbrake=%d nearestIdx=%2zu distToCL=%5.2f hw=%.2f HIT=%d targetCP=%zu\n",
                   i, i*dt, car.position.x, car.position.z, toDegrees(car.heading), car.speed(), car.forwardSpeed(),
                   in.throttle, in.steer, (int)in.handbrake, idx, distToCenter, track.halfWidth(), (int)hit, ai.targetCheckpoint);
        }
    }
    return 0;
}

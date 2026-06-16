// ai.cpp
#include "../include/ai.h"

using namespace m3d;

CarInput AIDriver::computeInput(const Car& car, const Track& track) {
    CarInput input;
    if (track.checkpoints.empty()) return input;

    Vec3 target = track.checkpoints[targetCheckpoint];
    Vec3 to = target - car.position;
    float dist = std::sqrt(to.x * to.x + to.z * to.z);

    if (dist < checkpointRadius) {
        size_t n = track.numCheckpoints();
        size_t next = (targetCheckpoint + 1) % n;
        if (next == 0) lapCount++;
        targetCheckpoint = next;
        target = track.checkpoints[targetCheckpoint];
        to = target - car.position;
    }

    float desiredHeading = std::atan2(to.x, to.z);
    float angleDiff = normalizeAngle(desiredHeading - car.heading);

    input.steer = clampf(angleDiff * steerGain, -1.0f, 1.0f);

    float throttleReduction = std::fabs(angleDiff) / PI; // 0..1
    input.throttle = clampf(1.0f - throttleReduction, minThrottle, 1.0f);

    // Drift through sharp corners if already moving at a reasonable clip.
    input.handbrake = (std::fabs(angleDiff) > driftAngleThreshold) && (car.forwardSpeed() > 8.0f);

    return input;
}

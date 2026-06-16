// ai.h - waypoint-following AI driver (pure logic, no rendering deps)
#pragma once

#include "car.h"
#include "track.h"

class AIDriver {
public:
    size_t targetCheckpoint = 0;
    int lapCount = 0;

    float checkpointRadius = 14.0f;  // distance at which a checkpoint counts as "reached"
    float steerGain = 1.8f;          // how aggressively the AI corrects heading
    float minThrottle = 0.35f;       // never fully lifts off, even in tight turns
    float driftAngleThreshold = m3d::toRadians(35.0f); // heading error above which AI uses handbrake

    // Computes this frame's control input for `car` given the track.
    // May advance targetCheckpoint / lapCount as a side effect.
    CarInput computeInput(const Car& car, const Track& track);
};

// Tracks lap progress for a car (typically the player) by following the
// same ordered-checkpoint logic the AI uses, without producing any input.
struct LapTracker {
    size_t nextCheckpoint = 0;
    int lapCount = 0;
    float checkpointRadius = 14.0f;

    void update(const m3d::Vec3& pos, const Track& track) {
        if (track.checkpoints.empty()) return;
        m3d::Vec3 to = track.checkpoints[nextCheckpoint] - pos;
        float dist = std::sqrt(to.x * to.x + to.z * to.z);
        if (dist < checkpointRadius) {
            size_t n = track.numCheckpoints();
            size_t next = (nextCheckpoint + 1) % n;
            if (next == 0) lapCount++;
            nextCheckpoint = next;
        }
    }
};

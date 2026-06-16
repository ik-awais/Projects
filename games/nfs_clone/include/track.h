// track.h - procedural race track: centerline, meshes, checkpoints
#pragma once

#include "math3d.h"
#include "geometry.h"
#include "car.h"
#include <vector>

class Track {
public:
    std::vector<m3d::Vec3> centerline;  // closed loop, world space
    std::vector<m3d::Vec3> checkpoints; // subset of centerline, in order

    MeshData groundMesh;
    MeshData roadMesh;
    MeshData barrierMesh;

    float roadWidth = 14.0f;

    // Builds the centerline, checkpoints, and all meshes.
    void generate();

    size_t numCheckpoints() const { return checkpoints.size(); }

    // Returns a spawn position offset to the side of the start line so
    // multiple cars don't overlap, plus the heading to face down the track.
    m3d::Vec3 spawnPosition(int slot) const;
    float spawnHeading() const;

    // Index of the centerline point nearest to `pos` (brute force; the
    // centerline only has ~96 points so this is cheap).
    size_t nearestCenterlineIndex(const m3d::Vec3& pos) const;

    // Half-width of the drivable corridor (road + barriers), used to keep
    // cars from driving through the guard rails.
    float halfWidth() const { return roadWidth * 0.5f + 0.6f; }
};

// Keeps `car` within the drivable corridor around `track`. If the car has
// crossed the guard rail, it is pushed back to the boundary and the
// outward-pointing component of its velocity is removed, so it slides
// along the wall instead of tunneling through it.
void resolveTrackCollision(Car& car, const Track& track);

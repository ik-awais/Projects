// track.cpp
#include "../include/track.h"

using namespace m3d;

void Track::generate() {
    centerline.clear();
    checkpoints.clear();

    // A gently wavy closed loop (not a plain ellipse), built by radially
    // perturbing an ellipse. Amplitude is kept small relative to the base
    // radii so the curvature never tightens enough for the road ribbon or
    // barriers to self-intersect.
    const int N = 96;
    const float A = 140.0f; // base radius along X
    const float B = 90.0f;  // base radius along Z
    const float perturb = 0.12f;

    centerline.reserve(N);
    for (int i = 0; i < N; ++i) {
        float t = (2.0f * PI * i) / N;
        float radial = 1.0f + perturb * std::sin(3.0f * t);
        float x = A * std::sin(t) * radial;
        float z = B * std::cos(t) * radial;
        centerline.push_back(Vec3(x, 0.0f, z));
    }

    // Evenly spaced checkpoints (8 of them) used for lap detection and AI
    // waypoint following.
    const int checkpointStride = N / 8;
    for (int i = 0; i < N; i += checkpointStride) {
        checkpoints.push_back(centerline[i]);
    }

    // ---- Meshes ----
    const float maxExtent = (A > B ? A : B) * (1.0f + perturb) + 40.0f;
    groundMesh = makeGroundPlane(maxExtent, 24,
                                  Vec3(0.20f, 0.55f, 0.20f),   // grass green
                                  Vec3(0.17f, 0.48f, 0.17f));  // alternate shade

    roadMesh = makeRibbon(centerline, roadWidth, 0.02f, Vec3(0.18f, 0.18f, 0.20f)); // dark asphalt

    barrierMesh = makeBarriers(centerline, roadWidth,
                                /*height=*/0.9f, /*thickness=*/0.6f,
                                Vec3(0.85f, 0.10f, 0.10f),  // red
                                Vec3(0.92f, 0.92f, 0.92f)); // white
}

Vec3 Track::spawnPosition(int slot) const {
    if (centerline.size() < 2) return Vec3(0, 0, 0);
    const Vec3& p0 = centerline[0];
    const Vec3& p1 = centerline[1];
    const Vec3& pLast = centerline[centerline.size() - 1];

    Vec3 tangent = (p1 - pLast).normalized();
    Vec3 up(0, 1, 0);
    Vec3 side = Vec3::cross(up, tangent).normalized();

    // Stagger cars laterally and slightly back along the track so they
    // don't spawn overlapping each other or the start line.
    float lateral = (slot % 2 == 0) ? -3.0f : 3.0f;
    float back = static_cast<float>(slot / 2) * 6.0f;

    return p0 + side * lateral - tangent * back + Vec3(0, 0.3f, 0);
}

float Track::spawnHeading() const {
    if (centerline.size() < 2) return 0.0f;
    const Vec3& p1 = centerline[1];
    const Vec3& pLast = centerline[centerline.size() - 1];
    Vec3 tangent = (p1 - pLast).normalized();
    return std::atan2(tangent.x, tangent.z);
}

size_t Track::nearestCenterlineIndex(const Vec3& pos) const {
    size_t best = 0;
    float bestDistSq = 1e30f;
    for (size_t i = 0; i < centerline.size(); ++i) {
        Vec3 d = pos - centerline[i];
        float distSq = d.x * d.x + d.z * d.z;
        if (distSq < bestDistSq) {
            bestDistSq = distSq;
            best = i;
        }
    }
    return best;
}

void resolveTrackCollision(Car& car, const Track& track) {
    size_t n = track.centerline.size();
    if (n < 2) return;

    size_t idx = track.nearestCenterlineIndex(car.position);
    const Vec3& P = track.centerline[idx];

    // Local track direction at P (smooth tangent), and the perpendicular
    // ("left") direction in the horizontal plane.
    Vec3 tangent = (track.centerline[(idx + 1) % n] - track.centerline[(idx + n - 1) % n]).normalized();
    Vec3 up(0.0f, 1.0f, 0.0f);
    Vec3 left = Vec3::cross(up, tangent).normalized();

    Vec3 offset(car.position.x - P.x, 0.0f, car.position.z - P.z);
    float lateral = Vec3::dot(offset, left); // signed distance from centerline along "left"
    float hw = track.halfWidth();

    if (std::fabs(lateral) > hw) {
        Vec3 outward = left * (lateral > 0.0f ? 1.0f : -1.0f);
        float excess = std::fabs(lateral) - hw;

        car.position.x -= outward.x * excess;
        car.position.z -= outward.z * excess;

        float vn = Vec3::dot(car.velocity, outward);
        if (vn > 0.0f) {
            car.velocity -= outward * vn; // remove outward component; keep tangential slide
        }
    }
}

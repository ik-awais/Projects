// camera.h - third-person chase camera (pure math, no rendering deps)
#pragma once

#include "math3d.h"
#include "car.h"

class ChaseCamera {
public:
    m3d::Vec3 position{0.0f, 5.0f, -10.0f};
    m3d::Vec3 target{0.0f, 0.0f, 0.0f};

    float distance   = 9.0f;  // how far behind the car
    float height     = 3.2f;  // how high above the car
    float lookHeight = 1.2f;  // vertical offset of the look-at point
    float followSpeed = 5.0f; // higher = snappier (exponential smoothing rate)

    bool initialized = false;

    // Smoothly moves the camera toward its ideal position behind `car`.
    void update(float dt, const Car& car) {
        m3d::Vec3 desiredPos = car.position - car.forward() * distance + m3d::Vec3(0.0f, height, 0.0f);
        m3d::Vec3 desiredTarget = car.position + m3d::Vec3(0.0f, lookHeight, 0.0f);

        if (!initialized) {
            position = desiredPos;
            target = desiredTarget;
            initialized = true;
            return;
        }

        float a = 1.0f - std::exp(-followSpeed * dt);
        position = m3d::Vec3::lerp(position, desiredPos, a);
        target   = m3d::Vec3::lerp(target, desiredTarget, a);
    }

    m3d::Mat4 viewMatrix() const {
        return m3d::Mat4::lookAt(position, target, m3d::Vec3(0.0f, 1.0f, 0.0f));
    }
};

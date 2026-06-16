// car.h - arcade-style car physics (no rendering dependencies)
#pragma once

#include "math3d.h"

// Player/AI control input for a single frame.
struct CarInput {
    float throttle = 0.0f; // -1.0 (full reverse/brake) .. 1.0 (full forward)
    float steer = 0.0f;    // -1.0 (left) .. 1.0 (right)
    bool handbrake = false;
};

class Car {
public:
    // ---- Dynamic state ----
    m3d::Vec3 position{0.0f, 0.0f, 0.0f};
    float heading = 0.0f;          // yaw, radians. forward = (sin(heading), 0, cos(heading))
    m3d::Vec3 velocity{0.0f, 0.0f, 0.0f};
    float steerVisual = 0.0f;      // smoothed front-wheel angle, for rendering only

    // ---- Tunable parameters (arcade feel, not strict realism) ----
    float mass            = 1100.0f;  // kg
    float enginePower     = 15500.0f; // N, forward drive force at full throttle
    float reversePower    = 8000.0f;  // N, reverse drive force
    float brakePower      = 13000.0f; // N, extra force when braking
    float dragCoeff       = 2.6f;     // quadratic air drag: F = dragCoeff * v^2
    float rollResistance  = 35.0f;    // linear rolling resistance: F = rollResistance * v
    float baseTurnFactor  = 0.10f;    // overall steering responsiveness
    float steerSpeedDamp  = 0.06f;    // reduces turn rate at high speed
    float normalGripRate  = 22.0f;    // how fast lateral slide is killed when gripping
    float driftGripRate   = 2.2f;     // how fast lateral slide is killed when drifting
    float handbrakeDecel  = 8.0f;     // extra forward deceleration under handbrake
    float maxSteerVisual  = m3d::toRadians(28.0f);
    float steerVisualSpeed= 6.0f;     // rad/s, how fast the visual wheel angle moves

    m3d::Vec3 forward() const { return m3d::Vec3(std::sin(heading), 0.0f, std::cos(heading)); }
    m3d::Vec3 right()   const { return m3d::Vec3(std::cos(heading), 0.0f, -std::sin(heading)); }

    float speed() const { return velocity.length(); }
    float forwardSpeed() const { return m3d::Vec3::dot(velocity, forward()); }
    float lateralSpeed() const { return m3d::Vec3::dot(velocity, right()); }

    // World-space model matrix (translate * rotateY), suitable for rendering.
    m3d::Mat4 modelMatrix() const {
        return m3d::Mat4::translate(position) * m3d::Mat4::rotateY(heading);
    }

    void reset(const m3d::Vec3& pos, float headingRad) {
        position = pos;
        heading = headingRad;
        velocity = m3d::Vec3(0.0f, 0.0f, 0.0f);
        steerVisual = 0.0f;
    }

    // Advance the simulation by dt seconds given this frame's input.
    void update(float dt, const CarInput& input);
};

// car.cpp - arcade-style car physics implementation
#include "../include/car.h"

using namespace m3d;

void Car::update(float dt, const CarInput& rawInput) {
    CarInput input = rawInput;
    input.throttle = clampf(input.throttle, -1.0f, 1.0f);
    input.steer    = clampf(input.steer, -1.0f, 1.0f);

    Vec3 fwd = forward();
    float fSpeed = Vec3::dot(velocity, fwd);

    // ---- 1. Drive / brake force ----
    Vec3 driveForce(0.0f, 0.0f, 0.0f);
    if (input.throttle > 0.0f) {
        driveForce = fwd * (input.throttle * enginePower);
    } else if (input.throttle < 0.0f) {
        if (fSpeed > 0.5f) {
            // Moving forward: "reverse" input acts as a brake.
            driveForce = fwd * (input.throttle * brakePower);
        } else {
            // Stopped or already reversing: accelerate backward.
            driveForce = fwd * (input.throttle * reversePower);
        }
    }

    // ---- 2. Resistance forces ----
    float spd = velocity.length();
    Vec3 dragForce = velocity * (-dragCoeff * spd);   // quadratic drag
    Vec3 rollForce = velocity * (-rollResistance);    // linear rolling resistance

    // ---- 3. Integrate linear velocity ----
    Vec3 netForce = driveForce + dragForce + rollForce;
    Vec3 accel = netForce / mass;
    velocity += accel * dt;

    // ---- 4. Handbrake: extra forward deceleration ----
    if (input.handbrake) {
        float f = Vec3::dot(velocity, fwd);
        float decel = handbrakeDecel * dt;
        float newF;
        if (f > 0.0f) newF = (f > decel) ? f - decel : 0.0f;
        else          newF = (f < -decel) ? f + decel : 0.0f;
        velocity += fwd * (newF - f);
    }

    // ---- 5. Steering (speed-sensitive yaw rate) ----
    float fSpeedNow = Vec3::dot(velocity, fwd);
    float turnRate = input.steer * fSpeedNow * baseTurnFactor
                     / (1.0f + std::fabs(fSpeedNow) * steerSpeedDamp);
    heading += turnRate * dt;

    // ---- 6. Lateral grip / drift ----
    Vec3 rgt = right(); // uses the *new* heading
    float lat = Vec3::dot(velocity, rgt);
    float gripRate = input.handbrake ? driftGripRate : normalGripRate;
    float factor = clampf(gripRate * dt, 0.0f, 1.0f);
    velocity -= rgt * (lat * factor);

    // ---- 7. Integrate position ----
    position += velocity * dt;

    // ---- 8. Visual front-wheel angle (cosmetic only) ----
    float targetSteer = input.steer * maxSteerVisual;
    float maxDelta = steerVisualSpeed * dt;
    float diff = targetSteer - steerVisual;
    if (diff > maxDelta) diff = maxDelta;
    else if (diff < -maxDelta) diff = -maxDelta;
    steerVisual += diff;
}

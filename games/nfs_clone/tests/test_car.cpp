#include "../include/car.h"
#include <cstdio>

using namespace m3d;

static void printState(float t, const Car& c) {
    printf("t=%5.2f  speed=%6.2f m/s (%6.1f km/h)  fwdSpd=%6.2f  latSpd=%6.2f  heading=%6.2f deg  pos=(%7.2f, %7.2f)\n",
           t, c.speed(), c.speed() * 3.6f, c.forwardSpeed(), c.lateralSpeed(),
           toDegrees(c.heading), c.position.x, c.position.z);
}

int main() {
    const float dt = 1.0f / 60.0f;

    // --- Scenario A: full throttle from a standstill, straight line ---
    printf("=== A: Full throttle, straight line (10s) ===\n");
    {
        Car car;
        CarInput in;
        in.throttle = 1.0f;
        for (int i = 0; i <= 600; ++i) {
            car.update(dt, in);
            if (i % 60 == 0) printState(i * dt, car);
        }
    }

    // --- Scenario B: stationary, full steer => should NOT spin in place ---
    printf("\n=== B: Stationary + full steer (should not rotate) ===\n");
    {
        Car car;
        CarInput in;
        in.steer = 1.0f;
        for (int i = 0; i <= 120; ++i) car.update(dt, in);
        printf("heading after 2s = %.4f deg (expect ~0)\n", toDegrees(car.heading));
    }

    // --- Scenario C: cruise then full steer, no handbrake (grippy) ---
    printf("\n=== C: Cruise to ~20 m/s, then full steer, NO handbrake ===\n");
    {
        Car car;
        CarInput in;
        in.throttle = 1.0f;
        // get up to ~20 m/s
        for (int i = 0; i < 600 && car.forwardSpeed() < 20.0f; ++i) car.update(dt, in);
        printf("reached speed=%.2f m/s before turning\n", car.speed());
        in.steer = 1.0f;
        for (int i = 0; i <= 180; ++i) {
            car.update(dt, in);
            if (i % 30 == 0) printState(i * dt, car);
        }
    }

    // --- Scenario D: cruise then full steer WITH handbrake (drift) ---
    printf("\n=== D: Cruise to ~20 m/s, then full steer + HANDBRAKE (drift) ===\n");
    {
        Car car;
        CarInput in;
        in.throttle = 1.0f;
        for (int i = 0; i < 600 && car.forwardSpeed() < 20.0f; ++i) car.update(dt, in);
        printf("reached speed=%.2f m/s before turning\n", car.speed());
        in.steer = 1.0f;
        in.handbrake = true;
        for (int i = 0; i <= 180; ++i) {
            car.update(dt, in);
            if (i % 30 == 0) printState(i * dt, car);
        }
    }

    // --- Scenario E: braking from speed to a stop, then reverse ---
    printf("\n=== E: Cruise, then brake/reverse input until stopped + reversing ===\n");
    {
        Car car;
        CarInput in;
        in.throttle = 1.0f;
        for (int i = 0; i < 300; ++i) car.update(dt, in);
        printf("before braking: speed=%.2f m/s\n", car.speed());
        in.throttle = -1.0f;
        for (int i = 0; i <= 240; ++i) {
            car.update(dt, in);
            if (i % 20 == 0) printState(i * dt, car);
        }
    }

    return 0;
}

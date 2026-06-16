#include "../include/math3d.h"
#include <cstdio>
#include <cassert>

using namespace m3d;

static bool nearlyEqual(float a, float b, float eps = 1e-4f) {
    return std::fabs(a - b) < eps;
}

int main() {
    // Identity matrix * vector = vector
    Mat4 I = Mat4::identity();
    Vec4 v(1, 2, 3, 1);
    Vec4 r = I * v;
    assert(nearlyEqual(r.x, 1) && nearlyEqual(r.y, 2) && nearlyEqual(r.z, 3));
    printf("[OK] identity * vector\n");

    // Translation
    Mat4 T = Mat4::translate(Vec3(5, 0, -2));
    r = T * v;
    assert(nearlyEqual(r.x, 6) && nearlyEqual(r.y, 2) && nearlyEqual(r.z, 1));
    printf("[OK] translate\n");

    // RotateY by 90 degrees: +Z axis should map to +X axis (for our convention)
    Mat4 R = Mat4::rotateY(toRadians(90.0f));
    Vec4 zAxis(0, 0, 1, 0);
    Vec4 rz = R * zAxis;
    printf("rotateY(90) * (0,0,1) = (%.3f, %.3f, %.3f)\n", rz.x, rz.y, rz.z);
    assert(nearlyEqual(rz.x, 1.0f) && nearlyEqual(rz.z, 0.0f, 1e-3f));
    printf("[OK] rotateY\n");

    // Matrix multiplication composition: T * R should rotate then translate
    Mat4 TR = T * Mat4::rotateY(0.0f);
    r = TR * v;
    assert(nearlyEqual(r.x, 6) && nearlyEqual(r.z, 1));
    printf("[OK] matrix multiply (identity rotation)\n");

    // Perspective + lookAt sanity: a point directly in front of the camera
    // along -Z (view space) should project near the center of NDC (x,y ~ 0)
    // and have positive depth after perspective divide.
    Mat4 view = Mat4::lookAt(Vec3(0, 2, 5), Vec3(0, 0, 0), Vec3(0, 1, 0));
    Mat4 proj = Mat4::perspective(toRadians(60.0f), 16.0f / 9.0f, 0.1f, 1000.0f);
    Mat4 vp = proj * view;
    Vec4 worldPoint(0, 2, 0, 1); // looking roughly at the camera's target height
    Vec4 clip = vp * worldPoint;
    printf("clip = (%.3f, %.3f, %.3f, %.3f)\n", clip.x, clip.y, clip.z, clip.w);
    assert(clip.w > 0.0f); // in front of camera
    float ndcX = clip.x / clip.w;
    float ndcY = clip.y / clip.w;
    printf("ndc = (%.3f, %.3f)\n", ndcX, ndcY);
    assert(std::fabs(ndcX) < 1.0f && std::fabs(ndcY) < 1.0f); // roughly on-screen
    printf("[OK] perspective + lookAt produce on-screen point\n");

    // Mat4 * Mat4 inverse-ish check: translate then translate back = identity-ish
    Mat4 A = Mat4::translate(Vec3(3, -1, 2));
    Mat4 B = Mat4::translate(Vec3(-3, 1, -2));
    Mat4 C = A * B;
    r = C * v;
    assert(nearlyEqual(r.x, v.x) && nearlyEqual(r.y, v.y) && nearlyEqual(r.z, v.z));
    printf("[OK] translate then inverse-translate = identity\n");

    printf("\nAll math3d tests passed.\n");
    return 0;
}

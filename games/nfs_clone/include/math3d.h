// math3d.h - tiny header-only 3D math library (no external dependencies)
// Provides Vec2, Vec3, Vec4, Mat4 plus the transforms needed for a
// perspective 3D racing game (translate, rotate, scale, lookAt, perspective).
//
// Matrices are column-major (matches OpenGL), stored as float m[16] in
// column-major order: m[col*4 + row].
#pragma once

#include <cmath>
#include <cstring>

namespace m3d {

constexpr float PI = 3.14159265358979323846f;

inline float toRadians(float degrees) { return degrees * (PI / 180.0f); }
inline float toDegrees(float radians) { return radians * (180.0f / PI); }

inline float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

inline float lerp(float a, float b, float t) {
    return a + (b - a) * t;
}

// Wraps an angle (radians) into the range (-PI, PI].
inline float normalizeAngle(float a) {
    while (a > PI) a -= 2.0f * PI;
    while (a <= -PI) a += 2.0f * PI;
    return a;
}

// ---------------------------------------------------------------------
// Vec2
// ---------------------------------------------------------------------
struct Vec2 {
    float x = 0.0f, y = 0.0f;

    Vec2() = default;
    Vec2(float x_, float y_) : x(x_), y(y_) {}

    Vec2 operator+(const Vec2& o) const { return Vec2(x + o.x, y + o.y); }
    Vec2 operator-(const Vec2& o) const { return Vec2(x - o.x, y - o.y); }
    Vec2 operator*(float s) const { return Vec2(x * s, y * s); }

    float length() const { return std::sqrt(x * x + y * y); }
};

// ---------------------------------------------------------------------
// Vec3
// ---------------------------------------------------------------------
struct Vec3 {
    float x = 0.0f, y = 0.0f, z = 0.0f;

    Vec3() = default;
    Vec3(float x_, float y_, float z_) : x(x_), y(y_), z(z_) {}

    Vec3 operator+(const Vec3& o) const { return Vec3(x + o.x, y + o.y, z + o.z); }
    Vec3 operator-(const Vec3& o) const { return Vec3(x - o.x, y - o.y, z - o.z); }
    Vec3 operator-() const { return Vec3(-x, -y, -z); }
    Vec3 operator*(float s) const { return Vec3(x * s, y * s, z * s); }
    Vec3 operator/(float s) const { return Vec3(x / s, y / s, z / s); }

    Vec3& operator+=(const Vec3& o) { x += o.x; y += o.y; z += o.z; return *this; }
    Vec3& operator-=(const Vec3& o) { x -= o.x; y -= o.y; z -= o.z; return *this; }
    Vec3& operator*=(float s) { x *= s; y *= s; z *= s; return *this; }

    float length() const { return std::sqrt(x * x + y * y + z * z); }

    Vec3 normalized() const {
        float len = length();
        if (len < 1e-8f) return Vec3(0.0f, 0.0f, 0.0f);
        return Vec3(x / len, y / len, z / len);
    }

    static float dot(const Vec3& a, const Vec3& b) {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    static Vec3 cross(const Vec3& a, const Vec3& b) {
        return Vec3(
            a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x
        );
    }

    static Vec3 lerp(const Vec3& a, const Vec3& b, float t) {
        return a + (b - a) * t;
    }
};

inline Vec3 operator*(float s, const Vec3& v) { return v * s; }

// ---------------------------------------------------------------------
// Vec4
// ---------------------------------------------------------------------
struct Vec4 {
    float x = 0.0f, y = 0.0f, z = 0.0f, w = 0.0f;

    Vec4() = default;
    Vec4(float x_, float y_, float z_, float w_) : x(x_), y(y_), z(z_), w(w_) {}
    Vec4(const Vec3& v, float w_) : x(v.x), y(v.y), z(v.z), w(w_) {}

    Vec3 xyz() const { return Vec3(x, y, z); }
};

// ---------------------------------------------------------------------
// Mat4 (column-major, OpenGL compatible)
// ---------------------------------------------------------------------
struct Mat4 {
    // m[col*4 + row]
    float m[16];

    Mat4() { std::memset(m, 0, sizeof(m)); }

    static Mat4 identity() {
        Mat4 r;
        r.m[0] = r.m[5] = r.m[10] = r.m[15] = 1.0f;
        return r;
    }

    static Mat4 translate(const Vec3& t) {
        Mat4 r = identity();
        r.m[12] = t.x;
        r.m[13] = t.y;
        r.m[14] = t.z;
        return r;
    }

    static Mat4 scale(const Vec3& s) {
        Mat4 r = identity();
        r.m[0] = s.x;
        r.m[5] = s.y;
        r.m[10] = s.z;
        return r;
    }

    // Rotation about the Y axis (yaw), radians. Used for car heading.
    static Mat4 rotateY(float radians) {
        Mat4 r = identity();
        float c = std::cos(radians);
        float s = std::sin(radians);
        r.m[0] = c;  r.m[8]  = s;
        r.m[2] = -s; r.m[10] = c;
        return r;
    }

    // Rotation about the X axis (pitch), radians.
    static Mat4 rotateX(float radians) {
        Mat4 r = identity();
        float c = std::cos(radians);
        float s = std::sin(radians);
        r.m[5] = c;  r.m[9]  = -s;
        r.m[6] = s;  r.m[10] = c;
        return r;
    }

    // Rotation about the Z axis (roll), radians.
    static Mat4 rotateZ(float radians) {
        Mat4 r = identity();
        float c = std::cos(radians);
        float s = std::sin(radians);
        r.m[0] = c;  r.m[4] = -s;
        r.m[1] = s;  r.m[5] = c;
        return r;
    }

    // Standard OpenGL perspective projection matrix.
    static Mat4 perspective(float fovYRadians, float aspect, float zNear, float zFar) {
        Mat4 r; // zero-initialized
        float f = 1.0f / std::tan(fovYRadians * 0.5f);
        r.m[0]  = f / aspect;
        r.m[5]  = f;
        r.m[10] = (zFar + zNear) / (zNear - zFar);
        r.m[11] = -1.0f;
        r.m[14] = (2.0f * zFar * zNear) / (zNear - zFar);
        return r;
    }

    // Right-handed lookAt view matrix.
    static Mat4 lookAt(const Vec3& eye, const Vec3& center, const Vec3& up) {
        Vec3 f = (center - eye).normalized();        // forward
        Vec3 s = Vec3::cross(f, up).normalized();     // right
        Vec3 u = Vec3::cross(s, f);                   // recomputed up

        Mat4 r = identity();
        r.m[0] = s.x;  r.m[4] = s.y;  r.m[8]  = s.z;
        r.m[1] = u.x;  r.m[5] = u.y;  r.m[9]  = u.z;
        r.m[2] = -f.x; r.m[6] = -f.y; r.m[10] = -f.z;

        r.m[12] = -Vec3::dot(s, eye);
        r.m[13] = -Vec3::dot(u, eye);
        r.m[14] =  Vec3::dot(f, eye);
        return r;
    }

    // Orthographic projection - used for the 2D HUD overlay.
    static Mat4 ortho(float left, float right, float bottom, float top, float zNear, float zFar) {
        Mat4 r = identity();
        r.m[0]  = 2.0f / (right - left);
        r.m[5]  = 2.0f / (top - bottom);
        r.m[10] = -2.0f / (zFar - zNear);
        r.m[12] = -(right + left) / (right - left);
        r.m[13] = -(top + bottom) / (top - bottom);
        r.m[14] = -(zFar + zNear) / (zFar - zNear);
        return r;
    }

    Mat4 operator*(const Mat4& o) const {
        Mat4 r; // zero-initialized
        for (int col = 0; col < 4; ++col) {
            for (int row = 0; row < 4; ++row) {
                float sum = 0.0f;
                for (int k = 0; k < 4; ++k) {
                    sum += m[k * 4 + row] * o.m[col * 4 + k];
                }
                r.m[col * 4 + row] = sum;
            }
        }
        return r;
    }

    Vec4 operator*(const Vec4& v) const {
        Vec4 r;
        r.x = m[0] * v.x + m[4] * v.y + m[8]  * v.z + m[12] * v.w;
        r.y = m[1] * v.x + m[5] * v.y + m[9]  * v.z + m[13] * v.w;
        r.z = m[2] * v.x + m[6] * v.y + m[10] * v.z + m[14] * v.w;
        r.w = m[3] * v.x + m[7] * v.y + m[11] * v.z + m[15] * v.w;
        return r;
    }

    // Returns the 3x3 upper-left "rotation/forward" part's third basis
    // vector (i.e. the local +Z axis transformed into world space).
    // Useful for extracting a car's forward direction from its model matrix.
    Vec3 column(int col) const {
        return Vec3(m[col * 4 + 0], m[col * 4 + 1], m[col * 4 + 2]);
    }
};

} // namespace m3d

// geometry.h - CPU-side mesh data + shape generators (no GL dependency).
//
// Vertex format is position + normal + color (no textures, so no UVs).
// This keeps the whole project free of any image-loading dependency while
// still allowing per-face shading via vertex colors and Phong lighting via
// normals.
#pragma once

#include "math3d.h"
#include <vector>
#include <cstdint>

struct Vertex {
    m3d::Vec3 pos;
    m3d::Vec3 normal;
    m3d::Vec3 color;
};

struct MeshData {
    std::vector<Vertex> vertices;
    std::vector<uint32_t> indices;
};

// Appends `src` onto `dst`, fixing up index offsets.
inline void appendMesh(MeshData& dst, const MeshData& src) {
    uint32_t base = static_cast<uint32_t>(dst.vertices.size());
    dst.vertices.insert(dst.vertices.end(), src.vertices.begin(), src.vertices.end());
    dst.indices.reserve(dst.indices.size() + src.indices.size());
    for (uint32_t idx : src.indices) dst.indices.push_back(base + idx);
}

// Transforms all vertex positions/normals of `m` by `model` in place.
// Normals are transformed by the rotation part only (assumes no
// non-uniform scaling, which holds for every mesh in this project).
inline void transformMesh(MeshData& m, const m3d::Mat4& model) {
    using namespace m3d;
    for (auto& v : m.vertices) {
        Vec4 p = model * Vec4(v.pos, 1.0f);
        v.pos = p.xyz();
        Vec4 n = model * Vec4(v.normal, 0.0f);
        v.normal = n.xyz().normalized();
    }
}

// A box centered at the origin with the given half-extents, with distinct
// flat-shaded faces (each face gets its own normal, required for correct
// lighting on a box).
inline MeshData makeBox(const m3d::Vec3& halfExtents, const m3d::Vec3& color) {
    using namespace m3d;
    MeshData m;
    float x = halfExtents.x, y = halfExtents.y, z = halfExtents.z;

    struct Face { Vec3 normal; Vec3 v0, v1, v2, v3; };
    Face faces[6] = {
        { Vec3( 0,  0,  1), Vec3(-x,-y, z), Vec3( x,-y, z), Vec3( x, y, z), Vec3(-x, y, z) }, // +Z front
        { Vec3( 0,  0, -1), Vec3( x,-y,-z), Vec3(-x,-y,-z), Vec3(-x, y,-z), Vec3( x, y,-z) }, // -Z back
        { Vec3( 1,  0,  0), Vec3( x,-y, z), Vec3( x,-y,-z), Vec3( x, y,-z), Vec3( x, y, z) }, // +X right
        { Vec3(-1,  0,  0), Vec3(-x,-y,-z), Vec3(-x,-y, z), Vec3(-x, y, z), Vec3(-x, y,-z) }, // -X left
        { Vec3( 0,  1,  0), Vec3(-x, y, z), Vec3( x, y, z), Vec3( x, y,-z), Vec3(-x, y,-z) }, // +Y top
        { Vec3( 0, -1,  0), Vec3(-x,-y,-z), Vec3( x,-y,-z), Vec3( x,-y, z), Vec3(-x,-y, z) }, // -Y bottom
    };

    for (auto& f : faces) {
        uint32_t base = static_cast<uint32_t>(m.vertices.size());
        m.vertices.push_back({f.v0, f.normal, color});
        m.vertices.push_back({f.v1, f.normal, color});
        m.vertices.push_back({f.v2, f.normal, color});
        m.vertices.push_back({f.v3, f.normal, color});
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 1);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 3);
    }
    return m;
}

// Appends a box at world-space `center`, rotated by `yaw` radians about Y,
// to `dst`.
inline void appendBox(MeshData& dst, const m3d::Vec3& center, const m3d::Vec3& halfExtents,
                       const m3d::Vec3& color, float yaw = 0.0f) {
    using namespace m3d;
    MeshData box = makeBox(halfExtents, color);
    transformMesh(box, Mat4::translate(center) * Mat4::rotateY(yaw));
    appendMesh(dst, box);
}

// A flat checkerboard ground plane, centered at the origin, spanning
// [-halfSize, halfSize] in X and Z, made of `cells` x `cells` quads
// alternating between colorA and colorB.
inline MeshData makeGroundPlane(float halfSize, int cells, const m3d::Vec3& colorA, const m3d::Vec3& colorB) {
    using namespace m3d;
    MeshData m;
    float cellSize = (halfSize * 2.0f) / static_cast<float>(cells);
    Vec3 up(0, 1, 0);

    for (int cz = 0; cz < cells; ++cz) {
        for (int cx = 0; cx < cells; ++cx) {
            float x0 = -halfSize + cx * cellSize;
            float x1 = x0 + cellSize;
            float z0 = -halfSize + cz * cellSize;
            float z1 = z0 + cellSize;
            Vec3 color = ((cx + cz) % 2 == 0) ? colorA : colorB;

            uint32_t base = static_cast<uint32_t>(m.vertices.size());
            m.vertices.push_back({Vec3(x0, 0, z0), up, color});
            m.vertices.push_back({Vec3(x1, 0, z0), up, color});
            m.vertices.push_back({Vec3(x1, 0, z1), up, color});
            m.vertices.push_back({Vec3(x0, 0, z1), up, color});
            m.indices.push_back(base + 0);
            m.indices.push_back(base + 1);
            m.indices.push_back(base + 2);
            m.indices.push_back(base + 0);
            m.indices.push_back(base + 2);
            m.indices.push_back(base + 3);
        }
    }
    return m;
}

// Generates a flat ribbon mesh following a closed-loop centerline, e.g. a
// road surface. `yOffset` lifts the ribbon slightly above the ground to
// avoid z-fighting. The centerline is treated as a closed loop (last point
// connects back to the first).
inline MeshData makeRibbon(const std::vector<m3d::Vec3>& centerline, float width,
                            float yOffset, const m3d::Vec3& color) {
    using namespace m3d;
    MeshData m;
    size_t n = centerline.size();
    if (n < 2) return m;

    Vec3 up(0, 1, 0);
    std::vector<Vec3> lefts(n), rights(n);

    for (size_t i = 0; i < n; ++i) {
        const Vec3& prev = centerline[(i + n - 1) % n];
        const Vec3& next = centerline[(i + 1) % n];
        Vec3 tangent = (next - prev).normalized();
        Vec3 side = Vec3::cross(up, tangent).normalized(); // points to local "left"
        Vec3 center = centerline[i] + Vec3(0, yOffset, 0);
        lefts[i]  = center - side * (width * 0.5f);
        rights[i] = center + side * (width * 0.5f);
    }

    for (size_t i = 0; i < n; ++i) {
        m.vertices.push_back({lefts[i],  up, color});
        m.vertices.push_back({rights[i], up, color});
    }
    for (size_t i = 0; i < n; ++i) {
        uint32_t i0 = static_cast<uint32_t>((2 * i) % (2 * n));
        uint32_t i1 = static_cast<uint32_t>((2 * i + 1) % (2 * n));
        uint32_t i2 = static_cast<uint32_t>((2 * ((i + 1) % n)));
        uint32_t i3 = static_cast<uint32_t>((2 * ((i + 1) % n)) + 1);
        // two triangles per segment (left0,right0,right1) and (left0,right1,left1)
        m.indices.push_back(i0);
        m.indices.push_back(i1);
        m.indices.push_back(i3);
        m.indices.push_back(i0);
        m.indices.push_back(i3);
        m.indices.push_back(i2);
    }
    return m;
}

// Generates low guard-rail walls along both edges of a track centerline.
// Produces alternating-color stripes for a classic rumble-strip look.
inline MeshData makeBarriers(const std::vector<m3d::Vec3>& centerline, float roadWidth,
                              float barrierHeight, float barrierThickness,
                              const m3d::Vec3& colorA, const m3d::Vec3& colorB) {
    using namespace m3d;
    MeshData m;
    size_t n = centerline.size();
    if (n < 2) return m;

    Vec3 up(0, 1, 0);
    for (size_t i = 0; i < n; ++i) {
        const Vec3& prev = centerline[(i + n - 1) % n];
        const Vec3& curr = centerline[i];
        const Vec3& next = centerline[(i + 1) % n];
        Vec3 tangent = (next - curr).normalized();
        Vec3 prevTangent = (curr - prev).normalized();
        Vec3 side = Vec3::cross(up, tangent).normalized();

        float yaw = std::atan2(tangent.x, tangent.z);
        float segLen = (next - curr).length();
        Vec3 mid = (curr + next) * 0.5f;
        Vec3 color = (i % 2 == 0) ? colorA : colorB;

        // outer (right) barrier segment
        Vec3 outerCenter = mid + side * (roadWidth * 0.5f + barrierThickness * 0.5f)
                                + Vec3(0, barrierHeight * 0.5f, 0);
        appendBox(m, outerCenter, Vec3(barrierThickness * 0.5f, barrierHeight * 0.5f, segLen * 0.5f + 0.05f), color, yaw);

        // inner (left) barrier segment
        Vec3 innerCenter = mid - side * (roadWidth * 0.5f + barrierThickness * 0.5f)
                                + Vec3(0, barrierHeight * 0.5f, 0);
        appendBox(m, innerCenter, Vec3(barrierThickness * 0.5f, barrierHeight * 0.5f, segLen * 0.5f + 0.05f), color, yaw);

        (void)prevTangent; // currently unused, kept for future smoothing
    }
    return m;
}

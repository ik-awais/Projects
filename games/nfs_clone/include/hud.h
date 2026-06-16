// hud.h - builds the HUD as a set of 2D colored quads (pure data, no GL deps)
//
// The quads are positioned in pixel coordinates with the origin at the
// bottom-left of the screen (matching an orthographic projection set up as
// ortho(0, screenW, 0, screenH, -1, 1)). z is always 0; the normal field is
// unused but kept so the HUD can share the same Vertex layout / shader
// plumbing as the 3D meshes.
#pragma once

#include "geometry.h"
#include "math3d.h"

inline MeshData buildHUD(float speedFraction, int lapCount, int totalLaps, bool drifting,
                          float screenW, float screenH) {
    using namespace m3d;
    MeshData m;
    Vec3 normal(0.0f, 0.0f, 1.0f);

    auto addQuad = [&](float x, float y, float w, float h, const Vec3& color) {
        uint32_t base = static_cast<uint32_t>(m.vertices.size());
        m.vertices.push_back({Vec3(x,     y,     0.0f), normal, color});
        m.vertices.push_back({Vec3(x + w, y,     0.0f), normal, color});
        m.vertices.push_back({Vec3(x + w, y + h, 0.0f), normal, color});
        m.vertices.push_back({Vec3(x,     y + h, 0.0f), normal, color});
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 1);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 0);
        m.indices.push_back(base + 2);
        m.indices.push_back(base + 3);
    };

    speedFraction = clampf(speedFraction, 0.0f, 1.0f);
    (void)screenW; // currently all elements are anchored from the left edge

    // ---- Speedometer bar (bottom-left) ----
    const float margin = 20.0f;
    const float barW = 220.0f, barH = 22.0f;
    const float barX = margin, barY = margin;

    addQuad(barX, barY, barW, barH, Vec3(0.08f, 0.08f, 0.08f)); // background

    Vec3 fillColor;
    if (speedFraction < 0.5f) {
        fillColor = Vec3::lerp(Vec3(0.20f, 0.90f, 0.20f), Vec3(0.95f, 0.85f, 0.10f), speedFraction / 0.5f);
    } else {
        fillColor = Vec3::lerp(Vec3(0.95f, 0.85f, 0.10f), Vec3(0.95f, 0.15f, 0.15f), (speedFraction - 0.5f) / 0.5f);
    }
    addQuad(barX + 3.0f, barY + 3.0f, (barW - 6.0f) * speedFraction, barH - 6.0f, fillColor);

    // ---- Drift indicator (to the right of the speedometer) ----
    const float driftSize = barH;
    Vec3 driftColor = drifting ? Vec3(1.0f, 0.5f, 0.0f) : Vec3(0.15f, 0.15f, 0.15f);
    addQuad(barX + barW + 10.0f, barY, driftSize, driftSize, driftColor);

    // ---- Lap progress indicators (top-left) ----
    const float lapSize = 18.0f, lapGap = 6.0f;
    for (int i = 0; i < totalLaps; ++i) {
        Vec3 c = (i < lapCount) ? Vec3(0.95f, 0.95f, 0.95f) : Vec3(0.22f, 0.22f, 0.22f);
        addQuad(margin + i * (lapSize + lapGap), screenH - margin - lapSize, lapSize, lapSize, c);
    }

    return m;
}

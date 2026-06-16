// shaders.h - GLSL source for the 3D scene shader and the HUD overlay shader.
// Targets OpenGL 3.3 core profile (#version 330 core) for Linux/Windows/macOS.
#pragma once

// ---------------------------------------------------------------------
// 3D scene shader: position/normal/color vertices, Phong-ish lighting
// with a directional "sun" light, ambient term, specular highlight, and
// simple distance fog.
// ---------------------------------------------------------------------
inline const char* kSceneVertexShader = R"GLSL(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec3 aColor;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProj;

out vec3 vNormal;
out vec3 vColor;
out vec3 vWorldPos;

void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vWorldPos = worldPos.xyz;
    vNormal = mat3(uModel) * aNormal;
    vColor = aColor;
    gl_Position = uProj * uView * worldPos;
}
)GLSL";

inline const char* kSceneFragmentShader = R"GLSL(
#version 330 core
in vec3 vNormal;
in vec3 vColor;
in vec3 vWorldPos;

uniform vec3 uLightDir;  // direction TOWARD the light, normalized, world space
uniform vec3 uViewPos;   // camera position, world space
uniform vec3 uFogColor;
uniform float uFogDensity;

out vec4 FragColor;

void main() {
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uLightDir);
    vec3 V = normalize(uViewPos - vWorldPos);

    float diff = max(dot(N, L), 0.0);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0), 32.0);

    vec3 ambient  = 0.35 * vColor;
    vec3 diffuse  = 0.75 * diff * vColor;
    vec3 specular = vec3(0.25) * spec;

    vec3 color = ambient + diffuse + specular;

    float dist = length(uViewPos - vWorldPos);
    float fog = clamp(exp(-uFogDensity * dist), 0.0, 1.0);
    color = mix(uFogColor, color, fog);

    FragColor = vec4(color, 1.0);
}
)GLSL";

// ---------------------------------------------------------------------
// HUD shader: 2D quads in pixel space, orthographic projection, flat
// vertex color (no lighting).
// ---------------------------------------------------------------------
inline const char* kHudVertexShader = R"GLSL(
#version 330 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal; // unused
layout(location = 2) in vec3 aColor;

uniform mat4 uProj;

out vec3 vColor;

void main() {
    vColor = aColor;
    gl_Position = uProj * vec4(aPos.xy, 0.0, 1.0);
}
)GLSL";

inline const char* kHudFragmentShader = R"GLSL(
#version 330 core
in vec3 vColor;
out vec4 FragColor;

void main() {
    FragColor = vec4(vColor, 1.0);
}
)GLSL";

// mesh.h - GPU-side mesh (VAO/VBO/EBO wrapper)
#pragma once

#include "gl_core.h"
#include "geometry.h"

class Mesh {
public:
    Mesh() = default;
    ~Mesh();

    Mesh(const Mesh&) = delete;
    Mesh& operator=(const Mesh&) = delete;
    Mesh(Mesh&& other) noexcept;
    Mesh& operator=(Mesh&& other) noexcept;

    // Uploads (or re-uploads) vertex/index data to the GPU. Pass
    // dynamic = true for meshes rebuilt every frame (e.g. the HUD).
    void upload(const MeshData& data, bool dynamic = false);

    // Binds the VAO and issues a glDrawElements call.
    void draw() const;

    bool valid() const { return vao != 0; }

private:
    GLuint vao = 0, vbo = 0, ebo = 0;
    GLsizei indexCount = 0;

    void destroy();
};

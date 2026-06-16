// mesh.cpp
#include "../include/mesh.h"
#include <cstddef>
#include <utility>

Mesh::~Mesh() {
    destroy();
}

Mesh::Mesh(Mesh&& other) noexcept {
    vao = other.vao;
    vbo = other.vbo;
    ebo = other.ebo;
    indexCount = other.indexCount;
    other.vao = other.vbo = other.ebo = 0;
    other.indexCount = 0;
}

Mesh& Mesh::operator=(Mesh&& other) noexcept {
    if (this != &other) {
        destroy();
        vao = other.vao;
        vbo = other.vbo;
        ebo = other.ebo;
        indexCount = other.indexCount;
        other.vao = other.vbo = other.ebo = 0;
        other.indexCount = 0;
    }
    return *this;
}

void Mesh::destroy() {
    if (ebo) glDeleteBuffers(1, &ebo);
    if (vbo) glDeleteBuffers(1, &vbo);
    if (vao) glDeleteVertexArrays(1, &vao);
    vao = vbo = ebo = 0;
    indexCount = 0;
}

void Mesh::upload(const MeshData& data, bool dynamic) {
    if (vao == 0) {
        glGenVertexArrays(1, &vao);
        glGenBuffers(1, &vbo);
        glGenBuffers(1, &ebo);
    }

    glBindVertexArray(vao);

    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER,
                  static_cast<GLsizeiptr>(data.vertices.size() * sizeof(Vertex)),
                  data.vertices.empty() ? nullptr : data.vertices.data(),
                  dynamic ? GL_DYNAMIC_DRAW : GL_STATIC_DRAW);

    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                  static_cast<GLsizeiptr>(data.indices.size() * sizeof(uint32_t)),
                  data.indices.empty() ? nullptr : data.indices.data(),
                  dynamic ? GL_DYNAMIC_DRAW : GL_STATIC_DRAW);

    // layout(location = 0) vec3 position
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)offsetof(Vertex, pos));
    // layout(location = 1) vec3 normal
    glEnableVertexAttribArray(1);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)offsetof(Vertex, normal));
    // layout(location = 2) vec3 color
    glEnableVertexAttribArray(2);
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, sizeof(Vertex), (void*)offsetof(Vertex, color));

    glBindVertexArray(0);

    indexCount = static_cast<GLsizei>(data.indices.size());
}

void Mesh::draw() const {
    if (vao == 0 || indexCount == 0) return;
    glBindVertexArray(vao);
    glDrawElements(GL_TRIANGLES, indexCount, GL_UNSIGNED_INT, nullptr);
    glBindVertexArray(0);
}

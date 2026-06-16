// shader.h - GLSL shader program wrapper
#pragma once

#include "gl_core.h"
#include "math3d.h"
#include <string>

class Shader {
public:
    Shader() = default;
    ~Shader();

    Shader(const Shader&) = delete;
    Shader& operator=(const Shader&) = delete;

    // Compiles and links a vertex+fragment shader pair. On failure, returns
    // false and fills `errorLog` with the compiler/linker message.
    bool compile(const char* vertexSrc, const char* fragmentSrc, std::string& errorLog);

    void use() const;

    void setMat4(const char* name, const m3d::Mat4& m) const;
    void setVec3(const char* name, const m3d::Vec3& v) const;
    void setFloat(const char* name, float v) const;
    void setInt(const char* name, int v) const;

    GLuint id() const { return program; }

private:
    GLuint program = 0;
};

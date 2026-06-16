// shader.cpp
#include "../include/shader.h"
#include <vector>

namespace {

bool compileStage(GLenum type, const char* src, GLuint& outShader, std::string& errorLog) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &src, nullptr);
    glCompileShader(shader);

    GLint success = 0;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &success);
    if (!success) {
        GLint len = 0;
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &len);
        std::vector<char> log(len > 0 ? len : 1);
        glGetShaderInfoLog(shader, (GLsizei)log.size(), nullptr, log.data());
        errorLog = std::string("shader compile error: ") + log.data();
        glDeleteShader(shader);
        return false;
    }
    outShader = shader;
    return true;
}

} // namespace

Shader::~Shader() {
    if (program) glDeleteProgram(program);
}

bool Shader::compile(const char* vertexSrc, const char* fragmentSrc, std::string& errorLog) {
    GLuint vs = 0, fs = 0;
    if (!compileStage(GL_VERTEX_SHADER, vertexSrc, vs, errorLog)) return false;
    if (!compileStage(GL_FRAGMENT_SHADER, fragmentSrc, fs, errorLog)) {
        glDeleteShader(vs);
        return false;
    }

    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    glLinkProgram(prog);

    GLint success = 0;
    glGetProgramiv(prog, GL_LINK_STATUS, &success);
    if (!success) {
        GLint len = 0;
        glGetProgramiv(prog, GL_INFO_LOG_LENGTH, &len);
        std::vector<char> log(len > 0 ? len : 1);
        glGetProgramInfoLog(prog, (GLsizei)log.size(), nullptr, log.data());
        errorLog = std::string("program link error: ") + log.data();
        glDeleteShader(vs);
        glDeleteShader(fs);
        glDeleteProgram(prog);
        return false;
    }

    // Shaders are no longer needed standalone once linked into the program.
    glDetachShader(prog, vs);
    glDetachShader(prog, fs);
    glDeleteShader(vs);
    glDeleteShader(fs);

    if (program) glDeleteProgram(program);
    program = prog;
    return true;
}

void Shader::use() const {
    glUseProgram(program);
}

void Shader::setMat4(const char* name, const m3d::Mat4& m) const {
    GLint loc = glGetUniformLocation(program, name);
    glUniformMatrix4fv(loc, 1, GL_FALSE, m.m);
}

void Shader::setVec3(const char* name, const m3d::Vec3& v) const {
    GLint loc = glGetUniformLocation(program, name);
    glUniform3f(loc, v.x, v.y, v.z);
}

void Shader::setFloat(const char* name, float v) const {
    GLint loc = glGetUniformLocation(program, name);
    glUniform1f(loc, v);
}

void Shader::setInt(const char* name, int v) const {
    GLint loc = glGetUniformLocation(program, name);
    glUniform1i(loc, v);
}

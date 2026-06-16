// gl_stub.cpp - fake OpenGL implementation, for end-to-end testing of
// main.cpp's logic only. NOT a real renderer (draws nothing).
#include "../include/gl_core.h"
#include <cstring>
#include <cstdio>

// ---- GL 1.1 functions declared in stubs/GL/gl.h ----
extern "C" {
void glViewport(GLint, GLint, GLsizei, GLsizei) {}
void glClearColor(GLfloat, GLfloat, GLfloat, GLfloat) {}
void glClear(GLbitfield) {}
void glEnable(GLenum) {}
void glDisable(GLenum) {}
void glDrawElements(GLenum, GLsizei, GLenum, const void*) {}
}

// ---- GL 3.x functions, normally loaded via function pointers ----
namespace stubgl {

static GLuint nextId = 1;

GLuint CreateShader(GLenum) { return nextId++; }
void ShaderSource(GLuint, GLsizei, const GLchar* const*, const GLint*) {}
void CompileShader(GLuint) {}
void GetShaderiv(GLuint, GLenum pname, GLint* params) {
    *params = (pname == GL_COMPILE_STATUS) ? GL_TRUE : 0;
}
void GetShaderInfoLog(GLuint, GLsizei, GLsizei* length, GLchar* infoLog) {
    if (length) *length = 0;
    if (infoLog) infoLog[0] = '\0';
}
void DeleteShader(GLuint) {}

GLuint CreateProgram() { return nextId++; }
void AttachShader(GLuint, GLuint) {}
void DetachShader(GLuint, GLuint) {}
void LinkProgram(GLuint) {}
void GetProgramiv(GLuint, GLenum pname, GLint* params) {
    *params = (pname == GL_LINK_STATUS) ? GL_TRUE : 0;
}
void GetProgramInfoLog(GLuint, GLsizei, GLsizei* length, GLchar* infoLog) {
    if (length) *length = 0;
    if (infoLog) infoLog[0] = '\0';
}
void DeleteProgram(GLuint) {}
void UseProgram(GLuint) {}

GLint GetUniformLocation(GLuint, const GLchar*) { return 0; }
void UniformMatrix4fv(GLint, GLsizei, GLboolean, const GLfloat*) {}
void Uniform1f(GLint, GLfloat) {}
void Uniform1i(GLint, GLint) {}
void Uniform3f(GLint, GLfloat, GLfloat, GLfloat) {}
void Uniform4f(GLint, GLfloat, GLfloat, GLfloat, GLfloat) {}

void GenVertexArrays(GLsizei n, GLuint* arrays) { for (GLsizei i = 0; i < n; ++i) arrays[i] = nextId++; }
void BindVertexArray(GLuint) {}
void DeleteVertexArrays(GLsizei, const GLuint*) {}

void GenBuffers(GLsizei n, GLuint* buffers) { for (GLsizei i = 0; i < n; ++i) buffers[i] = nextId++; }
void BindBuffer(GLenum, GLuint) {}
void BufferData(GLenum, GLsizeiptr, const void*, GLenum) {}
void DeleteBuffers(GLsizei, const GLuint*) {}

void EnableVertexAttribArray(GLuint) {}
void VertexAttribPointer(GLuint, GLint, GLenum, GLboolean, GLsizei, const void*) {}

} // namespace stubgl

void* fakeGetProcAddress(const char* name) {
    using namespace stubgl;
    #define MATCH(n, fn) if (std::strcmp(name, n) == 0) return reinterpret_cast<void*>(&fn);
    MATCH("glCreateShader", CreateShader)
    MATCH("glShaderSource", ShaderSource)
    MATCH("glCompileShader", CompileShader)
    MATCH("glGetShaderiv", GetShaderiv)
    MATCH("glGetShaderInfoLog", GetShaderInfoLog)
    MATCH("glDeleteShader", DeleteShader)
    MATCH("glCreateProgram", CreateProgram)
    MATCH("glAttachShader", AttachShader)
    MATCH("glDetachShader", DetachShader)
    MATCH("glLinkProgram", LinkProgram)
    MATCH("glGetProgramiv", GetProgramiv)
    MATCH("glGetProgramInfoLog", GetProgramInfoLog)
    MATCH("glDeleteProgram", DeleteProgram)
    MATCH("glUseProgram", UseProgram)
    MATCH("glGetUniformLocation", GetUniformLocation)
    MATCH("glUniformMatrix4fv", UniformMatrix4fv)
    MATCH("glUniform1f", Uniform1f)
    MATCH("glUniform1i", Uniform1i)
    MATCH("glUniform3f", Uniform3f)
    MATCH("glUniform4f", Uniform4f)
    MATCH("glGenVertexArrays", GenVertexArrays)
    MATCH("glBindVertexArray", BindVertexArray)
    MATCH("glDeleteVertexArrays", DeleteVertexArrays)
    MATCH("glGenBuffers", GenBuffers)
    MATCH("glBindBuffer", BindBuffer)
    MATCH("glBufferData", BufferData)
    MATCH("glDeleteBuffers", DeleteBuffers)
    MATCH("glEnableVertexAttribArray", EnableVertexAttribArray)
    MATCH("glVertexAttribPointer", VertexAttribPointer)
    #undef MATCH
    std::fprintf(stderr, "fakeGetProcAddress: unknown symbol %s\n", name);
    return nullptr;
}

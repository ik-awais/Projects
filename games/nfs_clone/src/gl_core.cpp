// gl_core.cpp - resolves OpenGL 3.3 core function pointers at runtime.
#include "../include/gl_core.h"

#if !defined(__APPLE__)
#include <cstdio>

// ---- Definitions for the extern pointers declared in gl_core.h ----
PFNGLCREATESHADERPROC       glCreateShader       = nullptr;
PFNGLSHADERSOURCEPROC       glShaderSource       = nullptr;
PFNGLCOMPILESHADERPROC      glCompileShader      = nullptr;
PFNGLGETSHADERIVPROC        glGetShaderiv        = nullptr;
PFNGLGETSHADERINFOLOGPROC   glGetShaderInfoLog   = nullptr;
PFNGLDELETESHADERPROC       glDeleteShader       = nullptr;

PFNGLCREATEPROGRAMPROC      glCreateProgram      = nullptr;
PFNGLATTACHSHADERPROC       glAttachShader       = nullptr;
PFNGLDETACHSHADERPROC       glDetachShader       = nullptr;
PFNGLLINKPROGRAMPROC        glLinkProgram        = nullptr;
PFNGLGETPROGRAMIVPROC       glGetProgramiv       = nullptr;
PFNGLGETPROGRAMINFOLOGPROC  glGetProgramInfoLog  = nullptr;
PFNGLDELETEPROGRAMPROC      glDeleteProgram      = nullptr;
PFNGLUSEPROGRAMPROC         glUseProgram         = nullptr;

PFNGLGETUNIFORMLOCATIONPROC glGetUniformLocation = nullptr;
PFNGLUNIFORMMATRIX4FVPROC   glUniformMatrix4fv   = nullptr;
PFNGLUNIFORM1FPROC          glUniform1f          = nullptr;
PFNGLUNIFORM1IPROC          glUniform1i          = nullptr;
PFNGLUNIFORM3FPROC          glUniform3f          = nullptr;
PFNGLUNIFORM4FPROC          glUniform4f          = nullptr;

PFNGLGENVERTEXARRAYSPROC    glGenVertexArrays    = nullptr;
PFNGLBINDVERTEXARRAYPROC    glBindVertexArray    = nullptr;
PFNGLDELETEVERTEXARRAYSPROC glDeleteVertexArrays = nullptr;

PFNGLGENBUFFERSPROC         glGenBuffers         = nullptr;
PFNGLBINDBUFFERPROC         glBindBuffer         = nullptr;
PFNGLBUFFERDATAPROC         glBufferData         = nullptr;
PFNGLDELETEBUFFERSPROC      glDeleteBuffers      = nullptr;

PFNGLENABLEVERTEXATTRIBARRAYPROC glEnableVertexAttribArray = nullptr;
PFNGLVERTEXATTRIBPOINTERPROC     glVertexAttribPointer     = nullptr;

#define GL_LOAD(name) \
    do { \
        name = reinterpret_cast<decltype(name)>(getProcAddress(#name)); \
        if (!name) { std::fprintf(stderr, "gl_core_load: missing %s\n", #name); ok = false; } \
    } while (0)

bool gl_core_load(void* (*getProcAddress)(const char* name)) {
    bool ok = true;

    GL_LOAD(glCreateShader);
    GL_LOAD(glShaderSource);
    GL_LOAD(glCompileShader);
    GL_LOAD(glGetShaderiv);
    GL_LOAD(glGetShaderInfoLog);
    GL_LOAD(glDeleteShader);

    GL_LOAD(glCreateProgram);
    GL_LOAD(glAttachShader);
    GL_LOAD(glDetachShader);
    GL_LOAD(glLinkProgram);
    GL_LOAD(glGetProgramiv);
    GL_LOAD(glGetProgramInfoLog);
    GL_LOAD(glDeleteProgram);
    GL_LOAD(glUseProgram);

    GL_LOAD(glGetUniformLocation);
    GL_LOAD(glUniformMatrix4fv);
    GL_LOAD(glUniform1f);
    GL_LOAD(glUniform1i);
    GL_LOAD(glUniform3f);
    GL_LOAD(glUniform4f);

    GL_LOAD(glGenVertexArrays);
    GL_LOAD(glBindVertexArray);
    GL_LOAD(glDeleteVertexArrays);

    GL_LOAD(glGenBuffers);
    GL_LOAD(glBindBuffer);
    GL_LOAD(glBufferData);
    GL_LOAD(glDeleteBuffers);

    GL_LOAD(glEnableVertexAttribArray);
    GL_LOAD(glVertexAttribPointer);

    return ok;
}

#undef GL_LOAD

#else // __APPLE__

bool gl_core_load(void* (*)(const char*)) {
    return true; // <OpenGL/gl3.h> already declares everything we need
}

#endif

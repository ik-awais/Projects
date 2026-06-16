// gl_core.h - minimal OpenGL 3.3 core profile loader.
//
// On Windows/Linux, OpenGL 1.1 is the only version guaranteed to be
// declared by the system headers, so anything from GL 1.5+ (VBOs, VAOs,
// shaders, etc.) must be loaded manually as function pointers at runtime.
// This header declares exactly the subset this project needs and provides
// gl_core_load() to resolve them via a platform-supplied "get proc address"
// function (we pass SDL_GL_GetProcAddress from main.cpp, keeping this header
// decoupled from SDL).
//
// On macOS, <OpenGL/gl3.h> already declares the OpenGL 3.2 core profile
// functions directly (and the OpenGL framework exports them), so no
// runtime loading is necessary there.
#pragma once

#include <cstddef> // ptrdiff_t

#if defined(__APPLE__)
    #define GL_SILENCE_DEPRECATION
    #include <OpenGL/gl3.h>
#else
    #if defined(_WIN32)
        #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
        #endif
        #include <windows.h>
    #endif
    #include <GL/gl.h>

    // ---- Types not present in the OpenGL 1.1 headers ----
    typedef ptrdiff_t GLsizeiptr;
    typedef ptrdiff_t GLintptr;
    typedef char GLchar;

    // ---- Constants not present in the OpenGL 1.1 headers ----
    #ifndef GL_ARRAY_BUFFER
    #define GL_ARRAY_BUFFER         0x8892
    #endif
    #ifndef GL_ELEMENT_ARRAY_BUFFER
    #define GL_ELEMENT_ARRAY_BUFFER 0x8893
    #endif
    #ifndef GL_STATIC_DRAW
    #define GL_STATIC_DRAW          0x88E4
    #endif
    #ifndef GL_DYNAMIC_DRAW
    #define GL_DYNAMIC_DRAW         0x88E8
    #endif
    #ifndef GL_FRAGMENT_SHADER
    #define GL_FRAGMENT_SHADER      0x8B30
    #endif
    #ifndef GL_VERTEX_SHADER
    #define GL_VERTEX_SHADER        0x8B31
    #endif
    #ifndef GL_COMPILE_STATUS
    #define GL_COMPILE_STATUS       0x8B81
    #endif
    #ifndef GL_LINK_STATUS
    #define GL_LINK_STATUS          0x8B82
    #endif
    #ifndef GL_INFO_LOG_LENGTH
    #define GL_INFO_LOG_LENGTH      0x8B84
    #endif
    #ifndef GL_MULTISAMPLE
    #define GL_MULTISAMPLE          0x809D
    #endif

    // ---- Function pointer typedefs (match khronos glext.h signatures) ----
    typedef GLuint (APIENTRY *PFNGLCREATESHADERPROC)(GLenum type);
    typedef void   (APIENTRY *PFNGLSHADERSOURCEPROC)(GLuint shader, GLsizei count, const GLchar* const* string, const GLint* length);
    typedef void   (APIENTRY *PFNGLCOMPILESHADERPROC)(GLuint shader);
    typedef void   (APIENTRY *PFNGLGETSHADERIVPROC)(GLuint shader, GLenum pname, GLint* params);
    typedef void   (APIENTRY *PFNGLGETSHADERINFOLOGPROC)(GLuint shader, GLsizei bufSize, GLsizei* length, GLchar* infoLog);
    typedef void   (APIENTRY *PFNGLDELETESHADERPROC)(GLuint shader);

    typedef GLuint (APIENTRY *PFNGLCREATEPROGRAMPROC)(void);
    typedef void   (APIENTRY *PFNGLATTACHSHADERPROC)(GLuint program, GLuint shader);
    typedef void   (APIENTRY *PFNGLDETACHSHADERPROC)(GLuint program, GLuint shader);
    typedef void   (APIENTRY *PFNGLLINKPROGRAMPROC)(GLuint program);
    typedef void   (APIENTRY *PFNGLGETPROGRAMIVPROC)(GLuint program, GLenum pname, GLint* params);
    typedef void   (APIENTRY *PFNGLGETPROGRAMINFOLOGPROC)(GLuint program, GLsizei bufSize, GLsizei* length, GLchar* infoLog);
    typedef void   (APIENTRY *PFNGLDELETEPROGRAMPROC)(GLuint program);
    typedef void   (APIENTRY *PFNGLUSEPROGRAMPROC)(GLuint program);

    typedef GLint  (APIENTRY *PFNGLGETUNIFORMLOCATIONPROC)(GLuint program, const GLchar* name);
    typedef void   (APIENTRY *PFNGLUNIFORMMATRIX4FVPROC)(GLint location, GLsizei count, GLboolean transpose, const GLfloat* value);
    typedef void   (APIENTRY *PFNGLUNIFORM1FPROC)(GLint location, GLfloat v0);
    typedef void   (APIENTRY *PFNGLUNIFORM1IPROC)(GLint location, GLint v0);
    typedef void   (APIENTRY *PFNGLUNIFORM3FPROC)(GLint location, GLfloat v0, GLfloat v1, GLfloat v2);
    typedef void   (APIENTRY *PFNGLUNIFORM4FPROC)(GLint location, GLfloat v0, GLfloat v1, GLfloat v2, GLfloat v3);

    typedef void   (APIENTRY *PFNGLGENVERTEXARRAYSPROC)(GLsizei n, GLuint* arrays);
    typedef void   (APIENTRY *PFNGLBINDVERTEXARRAYPROC)(GLuint array);
    typedef void   (APIENTRY *PFNGLDELETEVERTEXARRAYSPROC)(GLsizei n, const GLuint* arrays);

    typedef void   (APIENTRY *PFNGLGENBUFFERSPROC)(GLsizei n, GLuint* buffers);
    typedef void   (APIENTRY *PFNGLBINDBUFFERPROC)(GLenum target, GLuint buffer);
    typedef void   (APIENTRY *PFNGLBUFFERDATAPROC)(GLenum target, GLsizeiptr size, const void* data, GLenum usage);
    typedef void   (APIENTRY *PFNGLDELETEBUFFERSPROC)(GLsizei n, const GLuint* buffers);

    typedef void   (APIENTRY *PFNGLENABLEVERTEXATTRIBARRAYPROC)(GLuint index);
    typedef void   (APIENTRY *PFNGLVERTEXATTRIBPOINTERPROC)(GLuint index, GLint size, GLenum type, GLboolean normalized, GLsizei stride, const void* pointer);

    // ---- Extern function pointer declarations ----
    extern PFNGLCREATESHADERPROC       glCreateShader;
    extern PFNGLSHADERSOURCEPROC       glShaderSource;
    extern PFNGLCOMPILESHADERPROC      glCompileShader;
    extern PFNGLGETSHADERIVPROC        glGetShaderiv;
    extern PFNGLGETSHADERINFOLOGPROC   glGetShaderInfoLog;
    extern PFNGLDELETESHADERPROC       glDeleteShader;

    extern PFNGLCREATEPROGRAMPROC      glCreateProgram;
    extern PFNGLATTACHSHADERPROC       glAttachShader;
    extern PFNGLDETACHSHADERPROC       glDetachShader;
    extern PFNGLLINKPROGRAMPROC        glLinkProgram;
    extern PFNGLGETPROGRAMIVPROC       glGetProgramiv;
    extern PFNGLGETPROGRAMINFOLOGPROC  glGetProgramInfoLog;
    extern PFNGLDELETEPROGRAMPROC      glDeleteProgram;
    extern PFNGLUSEPROGRAMPROC         glUseProgram;

    extern PFNGLGETUNIFORMLOCATIONPROC glGetUniformLocation;
    extern PFNGLUNIFORMMATRIX4FVPROC   glUniformMatrix4fv;
    extern PFNGLUNIFORM1FPROC          glUniform1f;
    extern PFNGLUNIFORM1IPROC          glUniform1i;
    extern PFNGLUNIFORM3FPROC          glUniform3f;
    extern PFNGLUNIFORM4FPROC          glUniform4f;

    extern PFNGLGENVERTEXARRAYSPROC    glGenVertexArrays;
    extern PFNGLBINDVERTEXARRAYPROC    glBindVertexArray;
    extern PFNGLDELETEVERTEXARRAYSPROC glDeleteVertexArrays;

    extern PFNGLGENBUFFERSPROC         glGenBuffers;
    extern PFNGLBINDBUFFERPROC         glBindBuffer;
    extern PFNGLBUFFERDATAPROC         glBufferData;
    extern PFNGLDELETEBUFFERSPROC      glDeleteBuffers;

    extern PFNGLENABLEVERTEXATTRIBARRAYPROC glEnableVertexAttribArray;
    extern PFNGLVERTEXATTRIBPOINTERPROC     glVertexAttribPointer;
#endif // !__APPLE__

// Resolves all the function pointers above using the supplied
// "get proc address" function (e.g. SDL_GL_GetProcAddress). Must be called
// once after an OpenGL context is created and made current. Returns false
// (and prints which symbol failed) if any required function is missing.
//
// On macOS this is a no-op that always returns true, since the functions
// are declared and linked directly via <OpenGL/gl3.h>.
bool gl_core_load(void* (*getProcAddress)(const char* name));

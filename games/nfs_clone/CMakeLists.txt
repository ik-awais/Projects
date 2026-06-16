cmake_minimum_required(VERSION 3.16)
project(cpp_racer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

find_package(SDL2 REQUIRED)
find_package(OpenGL REQUIRED)

add_executable(cpp_racer
    src/main.cpp
    src/car.cpp
    src/track.cpp
    src/ai.cpp
    src/shader.cpp
    src/mesh.cpp
    src/gl_core.cpp
)

target_include_directories(cpp_racer PRIVATE include)

# SDL2's CMake config differs by platform/version: modern config packages
# (vcpkg, Homebrew, recent distros) provide the SDL2::SDL2 target; older
# distro FindSDL2 modules only set SDL2_INCLUDE_DIRS / SDL2_LIBRARIES.
if(TARGET SDL2::SDL2)
    target_link_libraries(cpp_racer PRIVATE SDL2::SDL2)
else()
    target_include_directories(cpp_racer PRIVATE ${SDL2_INCLUDE_DIRS})
    target_link_libraries(cpp_racer PRIVATE ${SDL2_LIBRARIES})
endif()

# On Windows, SDL2main provides the WinMain shim so a normal main() works.
if(TARGET SDL2::SDL2main)
    target_link_libraries(cpp_racer PRIVATE SDL2::SDL2main)
endif()

target_link_libraries(cpp_racer PRIVATE OpenGL::GL)

if(MSVC)
    target_compile_options(cpp_racer PRIVATE /W4)
else()
    target_compile_options(cpp_racer PRIVATE -Wall -Wextra)
endif()

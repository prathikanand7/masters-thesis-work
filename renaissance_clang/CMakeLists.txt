cmake_minimum_required(VERSION 3.20)
project(csp_matcher LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ── MSYS2 MinGW64 paths ───────────────────────────────────────────────────────
# Build with: cmake -B build_mingw -G "MinGW Makefiles"
#   -DCMAKE_BUILD_TYPE=Release
#   -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/clang++.exe
# Or with Ninja: -G Ninja
set(MINGW_ROOT "C:/msys64/mingw64" CACHE PATH "MSYS2 mingw64 root directory")

set(LLVM_DIR  "${MINGW_ROOT}/lib/cmake/llvm"  CACHE PATH "LLVM CMake config dir")
set(Clang_DIR "${MINGW_ROOT}/lib/cmake/clang" CACHE PATH "Clang CMake config dir")

# Point CMake prefix path to MSYS2 so all find_package calls find MSYS2 packages
list(PREPEND CMAKE_PREFIX_PATH "${MINGW_ROOT}")

# Dependencies that LLVM's config files reference
set(ZLIB_ROOT "${MINGW_ROOT}" CACHE PATH "")
find_package(ZLIB REQUIRED)

# Ensure ZLIB::ZLIB imported target exists (needed by LLVMConfig.cmake)
if(ZLIB_FOUND AND NOT TARGET ZLIB::ZLIB)
  add_library(ZLIB::ZLIB UNKNOWN IMPORTED)
  set_target_properties(ZLIB::ZLIB PROPERTIES
    IMPORTED_LOCATION             "${ZLIB_LIBRARIES}"
    INTERFACE_INCLUDE_DIRECTORIES "${ZLIB_INCLUDE_DIRS}")
endif()

find_package(LLVM  REQUIRED CONFIG)
find_package(Clang REQUIRED CONFIG)

message(STATUS "LLVM ${LLVM_VERSION} at ${LLVM_DIR}")
message(STATUS "Clang include dirs: ${CLANG_INCLUDE_DIRS}")

# ── Tool executable ───────────────────────────────────────────────────────────
add_executable(csp_matcher src/main.cpp)

target_include_directories(csp_matcher PRIVATE
    ${LLVM_INCLUDE_DIRS}
    ${CLANG_INCLUDE_DIRS}
)

# Core LLVM support libraries
llvm_map_components_to_libnames(llvm_libs support core irreader option remarks)

target_link_libraries(csp_matcher PRIVATE
    clangTooling
    clangFrontend
    clangSerialization
    clangDriver
    clangParse
    clangSema
    clangAnalysis
    clangEdit
    clangAST
    clangASTMatchers
    clangDynamicASTMatchers
    clangBasic
    clangRewrite
    clangLex
    clangToolingCore
    ${llvm_libs}
)

# LLVM preprocessor definitions (e.g. -D_GNU_SOURCE, -D__STDC_CONSTANT_MACROS)
separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND "${LLVM_DEFINITIONS}")
target_compile_definitions(csp_matcher PRIVATE
    ${LLVM_DEFINITIONS_LIST}
    CSP_MINGW_ROOT="${MINGW_ROOT}"
)

target_compile_options(csp_matcher PRIVATE -Wall -Wextra -Wno-unused-parameter)

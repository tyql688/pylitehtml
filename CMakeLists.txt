cmake_minimum_required(VERSION 3.21)
project(pylitehtml CXX)

# macOS: pin deployment target to match Homebrew Python (15.0).
# Without this, CMake defaults to the current SDK version and produces a .so
# that requires libc++ symbols unavailable in older Python runtimes.
if(APPLE AND NOT CMAKE_OSX_DEPLOYMENT_TARGET)
  set(CMAKE_OSX_DEPLOYMENT_TARGET "15.0" CACHE STRING "Minimum macOS version")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)  # required for .so on Linux

# ── Dependencies via pkg-config ───────────────────────────────────────────────
find_package(PkgConfig REQUIRED)
pkg_check_modules(CAIRO     REQUIRED IMPORTED_TARGET cairo)
pkg_check_modules(PANGOCAIRO REQUIRED IMPORTED_TARGET pangocairo)
pkg_check_modules(FONTCONFIG REQUIRED IMPORTED_TARGET fontconfig)

# JPEG: prefer CMake config (libjpeg-turbo), fall back to pkg-config
find_package(JPEG QUIET)
if(NOT JPEG_FOUND)
  pkg_check_modules(JPEG REQUIRED IMPORTED_TARGET libjpeg)
endif()

# WebP: prefer CMake config, fall back to pkg-config
find_package(WebP CONFIG QUIET)
if(NOT WebP_FOUND)
  pkg_check_modules(WEBP REQUIRED IMPORTED_TARGET libwebp)
endif()

# OpenSSL: enables HTTPS fetching (images / CSS) in the vendored cpp-httplib.
# Optional — without it the build still works, but https:// resources are
# skipped (never an error). Most real-world images are https, so prefer having it.
find_package(OpenSSL QUIET)

# ── litehtml ──────────────────────────────────────────────────────────────────
set(LITEHTML_BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/litehtml)

# ── pybind11 ─────────────────────────────────────────────────────────────────
find_package(pybind11 CONFIG REQUIRED)

# ── Extension module ─────────────────────────────────────────────────────────
pybind11_add_module(_core MODULE
  src/cpp/binding.cpp
  src/cpp/http_util.cpp
  src/cpp/image_cache.cpp
  src/cpp/font_manager.cpp
  src/cpp/py_container.cpp
  src/cpp/encode.cpp
  # Reuse Cairo drawing helpers from litehtml (no GDK dependency)
  third_party/litehtml/containers/cairo/container_cairo.cpp
  third_party/litehtml/containers/cairo/cairo_borders.cpp
  third_party/litehtml/containers/cairo/conic_gradient.cpp
)

target_include_directories(_core PRIVATE
  src/cpp
  src/cpp/vendor
  third_party/litehtml/include
  third_party/litehtml/containers/cairo
)

# Use IMPORTED_TARGET from pkg_check_modules — carries both include dirs AND cflags
target_link_libraries(_core PRIVATE
  litehtml
  PkgConfig::CAIRO
  PkgConfig::PANGOCAIRO
  PkgConfig::FONTCONFIG
)

if(JPEG_FOUND AND TARGET JPEG::JPEG)
  target_link_libraries(_core PRIVATE JPEG::JPEG)
elseif(TARGET PkgConfig::JPEG)
  target_link_libraries(_core PRIVATE PkgConfig::JPEG)
endif()

if(TARGET WebP::webp)
  target_link_libraries(_core PRIVATE WebP::webp)
elseif(TARGET PkgConfig::WEBP)
  target_link_libraries(_core PRIVATE PkgConfig::WEBP)
endif()

# The vendored cpp-httplib requires OpenSSL >= 3.0 for TLS. manylinux_2_28 ships
# OpenSSL 1.1.1, so gate the feature on the version: with < 3.0 (or none) HTTPS
# is disabled and https:// resources are skipped gracefully (never a build error).
if(OpenSSL_FOUND AND OPENSSL_VERSION VERSION_GREATER_EQUAL "3.0.0")
  message(STATUS "pylitehtml: OpenSSL ${OPENSSL_VERSION} — HTTPS fetching enabled")
  target_compile_definitions(_core PRIVATE CPPHTTPLIB_OPENSSL_SUPPORT)
  target_link_libraries(_core PRIVATE OpenSSL::SSL OpenSSL::Crypto)
else()
  message(STATUS "pylitehtml: OpenSSL >= 3.0 not found — https:// resources will be skipped")
endif()

# stdc++fs on older Linux toolchains
if(UNIX AND NOT APPLE)
  target_link_libraries(_core PRIVATE stdc++fs)
endif()

# MSVC: enable M_PI and other POSIX math constants (not defined by default)
if(MSVC)
  target_compile_definitions(_core PRIVATE _USE_MATH_DEFINES)
endif()

# ── Install ───────────────────────────────────────────────────────────────────
install(TARGETS _core DESTINATION pylitehtml)
install(DIRECTORY fonts/ DESTINATION pylitehtml/fonts)

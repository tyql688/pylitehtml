cmake_minimum_required(VERSION 3.21)
project(pylitehtml CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

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

# ── litehtml ──────────────────────────────────────────────────────────────────
set(LITEHTML_BUILD_TESTING OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/litehtml)

# ── pybind11 ─────────────────────────────────────────────────────────────────
find_package(pybind11 CONFIG REQUIRED)

# ── Extension module ─────────────────────────────────────────────────────────
pybind11_add_module(_core
  src/cpp/binding.cpp
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

target_compile_options(_core PRIVATE -UCPPHTTPLIB_OPENSSL_SUPPORT)

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

# stdc++fs on older Linux toolchains
if(UNIX AND NOT APPLE)
  target_link_libraries(_core PRIVATE stdc++fs)
endif()

# ── Install ───────────────────────────────────────────────────────────────────
install(TARGETS _core DESTINATION pylitehtml)
install(DIRECTORY fonts/ DESTINATION pylitehtml/fonts)

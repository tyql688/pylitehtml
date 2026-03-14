// src/cpp/encode.h
#pragma once
#include <cairo.h>
#include <vector>
#include <cstdint>

namespace encode {
std::vector<uint8_t> to_png (cairo_surface_t* surface);
std::vector<uint8_t> to_jpeg(cairo_surface_t* surface, int quality);
std::vector<uint8_t> to_rgba(cairo_surface_t* surface);
} // namespace encode

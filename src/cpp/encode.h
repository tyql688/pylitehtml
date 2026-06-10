#pragma once
#include <cairo.h>
#include <vector>
#include <cstdint>

namespace encode {
std::vector<uint8_t> to_png (cairo_surface_t* surface);
std::vector<uint8_t> to_jpeg(cairo_surface_t* surface, int quality);
// Swizzle ARGB32 → RGBA directly into a caller-provided buffer of
// width*height*4 bytes (avoids an intermediate full-frame copy).
void to_rgba_into(cairo_surface_t* surface, uint8_t* dst);
} // namespace encode

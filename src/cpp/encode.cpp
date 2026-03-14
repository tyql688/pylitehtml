// src/cpp/encode.cpp
#include "encode.h"
#include <cstdio>   // FILE — required before jpeglib.h
#include <jpeglib.h>
#include <csetjmp>
#include <stdexcept>
#include <string>

namespace encode {

// ── PNG ───────────────────────────────────────────────────────────────────────
static cairo_status_t png_write_cb(void* closure, const unsigned char* data, unsigned int len) {
    auto* buf = static_cast<std::vector<uint8_t>*>(closure);
    buf->insert(buf->end(), data, data + len);
    return CAIRO_STATUS_SUCCESS;
}

std::vector<uint8_t> to_png(cairo_surface_t* surface) {
    std::vector<uint8_t> buf;
    auto st = cairo_surface_write_to_png_stream(surface, png_write_cb, &buf);
    if (st != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error(std::string("PNG encode: ") + cairo_status_to_string(st));
    return buf;
}

// ── JPEG (safe setjmp error handler — never calls exit()) ─────────────────────
struct SafeJpegError {
    jpeg_error_mgr pub;   // must be first
    jmp_buf        jmpbuf;
};

static void jpeg_error_exit(j_common_ptr cinfo) {
    auto* err = reinterpret_cast<SafeJpegError*>(cinfo->err);
    longjmp(err->jmpbuf, 1);
}

std::vector<uint8_t> to_jpeg(cairo_surface_t* surface, int quality) {
    int w = cairo_image_surface_get_width(surface);
    int h = cairo_image_surface_get_height(surface);
    int stride = cairo_image_surface_get_stride(surface);
    const uint8_t* src = cairo_image_surface_get_data(surface);

    // Build RGB buffer (flatten alpha on white background)
    std::vector<uint8_t> rgb(w * h * 3);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + y * stride;
        uint8_t* out = rgb.data() + y * w * 3;
        for (int x = 0; x < w; ++x) {
            // Cairo ARGB32 LE: [B, G, R, A]
            float a = row[x*4+3] / 255.0f;
            out[x*3+0] = static_cast<uint8_t>(row[x*4+2] * a + 255.0f * (1.0f - a)); // R
            out[x*3+1] = static_cast<uint8_t>(row[x*4+1] * a + 255.0f * (1.0f - a)); // G
            out[x*3+2] = static_cast<uint8_t>(row[x*4+0] * a + 255.0f * (1.0f - a)); // B
        }
    }

    jpeg_compress_struct cinfo{};
    SafeJpegError jerr{};
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = jpeg_error_exit;

    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_compress(&cinfo);
        throw std::runtime_error("JPEG encode error");
    }

    jpeg_create_compress(&cinfo);
    uint8_t* mem = nullptr;
    unsigned long mem_size = 0;
    jpeg_mem_dest(&cinfo, &mem, &mem_size);

    cinfo.image_width = w;
    cinfo.image_height = h;
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    while (cinfo.next_scanline < cinfo.image_height) {
        JSAMPROW row = rgb.data() + cinfo.next_scanline * w * 3;
        jpeg_write_scanlines(&cinfo, &row, 1);
    }
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);

    std::vector<uint8_t> result(mem, mem + mem_size);
    free(mem);
    return result;
}

// ── RAW RGBA ─────────────────────────────────────────────────────────────────
// Cairo ARGB32 LE: [B,G,R,A] per pixel → swizzle to true [R,G,B,A]
std::vector<uint8_t> to_rgba(cairo_surface_t* surface) {
    int w = cairo_image_surface_get_width(surface);
    int h = cairo_image_surface_get_height(surface);
    int stride = cairo_image_surface_get_stride(surface);
    const uint8_t* src = cairo_image_surface_get_data(surface);

    std::vector<uint8_t> rgba(w * h * 4);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + y * stride;
        uint8_t* out = rgba.data() + y * w * 4;
        for (int x = 0; x < w; ++x) {
            out[x*4+0] = row[x*4+2]; // R
            out[x*4+1] = row[x*4+1]; // G
            out[x*4+2] = row[x*4+0]; // B
            out[x*4+3] = row[x*4+3]; // A
        }
    }
    return rgba;
}

} // namespace encode

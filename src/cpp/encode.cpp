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

    // Build RGB buffer (flatten alpha on white background). size_t math avoids
    // int overflow on very large surfaces.
    const size_t rowstride = static_cast<size_t>(w) * 3;
    std::vector<uint8_t> rgb(rowstride * static_cast<size_t>(h));
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * stride;
        uint8_t* out = rgb.data() + static_cast<size_t>(y) * rowstride;
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

    // volatile so the buffer can be freed in the error branch after longjmp.
    unsigned char* volatile mem = nullptr;
    unsigned long mem_size = 0;
    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_compress(&cinfo);
        if (mem) free(const_cast<unsigned char*>(mem));
        throw std::runtime_error("JPEG encode error");
    }

    jpeg_create_compress(&cinfo);
    jpeg_mem_dest(&cinfo, const_cast<unsigned char**>(&mem), &mem_size);

    cinfo.image_width = static_cast<JDIMENSION>(w);
    cinfo.image_height = static_cast<JDIMENSION>(h);
    cinfo.input_components = 3;
    cinfo.in_color_space = JCS_RGB;
    jpeg_set_defaults(&cinfo);
    jpeg_set_quality(&cinfo, quality, TRUE);
    jpeg_start_compress(&cinfo, TRUE);

    while (cinfo.next_scanline < cinfo.image_height) {
        JSAMPROW row = rgb.data() + static_cast<size_t>(cinfo.next_scanline) * rowstride;
        jpeg_write_scanlines(&cinfo, &row, 1);
    }
    jpeg_finish_compress(&cinfo);
    jpeg_destroy_compress(&cinfo);

    unsigned char* buf = const_cast<unsigned char*>(mem);
    std::vector<uint8_t> result(buf, buf + mem_size);
    free(buf);
    return result;
}

// ── RAW RGBA ─────────────────────────────────────────────────────────────────
// Cairo ARGB32 LE: [B,G,R,A] per pixel → swizzle to true [R,G,B,A]
std::vector<uint8_t> to_rgba(cairo_surface_t* surface) {
    int w = cairo_image_surface_get_width(surface);
    int h = cairo_image_surface_get_height(surface);
    int stride = cairo_image_surface_get_stride(surface);
    const uint8_t* src = cairo_image_surface_get_data(surface);

    const size_t rowstride = static_cast<size_t>(w) * 4;
    std::vector<uint8_t> rgba(rowstride * static_cast<size_t>(h));
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * stride;
        uint8_t* out = rgba.data() + static_cast<size_t>(y) * rowstride;
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

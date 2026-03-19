// src/cpp/image_cache.cpp
#include "image_cache.h"
#include "base64.h"
#include <cairo.h>
#include <webp/decode.h>
#include <cstdio>   // FILE — required before jpeglib.h
#include <jpeglib.h>
#include <csetjmp>
#include <cstring>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>

#ifdef HAVE_LIBRSVG
#include <librsvg/rsvg.h>
#endif

#include "http_util.h"

namespace fs = std::filesystem;

ImageCache::ImageCache(Config cfg) : cfg_(std::move(cfg)) {}

ImageCache::~ImageCache() {
    for (auto& [key, entry] : map_) {
        if (entry.surface) cairo_surface_destroy(entry.surface);
    }
}

cairo_surface_t* ImageCache::get(const std::string& url, const std::string& base_url) {
    std::string key = resolve(url, base_url);
    if (key.empty()) return nullptr;

    // Fast path: shared lock
    {
        std::shared_lock lk(mu_);
        auto it = map_.find(key);
        if (it != map_.end()) return it->second.surface;
    }

    // Slow path: load then exclusive lock
    cairo_surface_t* surface = load(key);
    if (!surface) return nullptr;

    size_t img_bytes = static_cast<size_t>(
        cairo_image_surface_get_stride(surface)) *
        cairo_image_surface_get_height(surface);

    std::unique_lock lk(mu_);
    // Double-check
    auto it = map_.find(key);
    if (it != map_.end()) {
        cairo_surface_destroy(surface);
        return it->second.surface;
    }

    evict_to_fit(img_bytes);
    insertion_order_.push_back(key);
    map_[key] = {surface, img_bytes};
    used_bytes_ += img_bytes;
    return surface;
}

void ImageCache::evict_to_fit(size_t needed) {
    while (!insertion_order_.empty() && used_bytes_ + needed > cfg_.max_bytes) {
        const std::string& victim = insertion_order_.front();
        auto it = map_.find(victim);
        if (it != map_.end()) {
            if (it->second.surface) cairo_surface_destroy(it->second.surface);
            used_bytes_ -= it->second.bytes;
            map_.erase(it);
        }
        insertion_order_.pop_front();
    }
}

std::string ImageCache::resolve(const std::string& url, const std::string& base_url) const {
    if (url.empty()) return {};
    // data: URIs are self-contained; return as-is without base resolution
    if (url.rfind("data:", 0) == 0) return url;
    if (url.find("://") != std::string::npos) return url;
    if (url[0] == '/') return "file://" + url;
    if (base_url.rfind("file://", 0) == 0) {
        fs::path base = fs::path(base_url.substr(7)).parent_path();
        return "file://" + (base / url).string();
    }
    if (base_url.rfind("http://", 0) == 0 || base_url.rfind("https://", 0) == 0) {
        auto slash = base_url.rfind('/');
        return base_url.substr(0, slash + 1) + url;
    }
    return {};
}

cairo_surface_t* ImageCache::load(const std::string& resolved) {
    if (resolved.rfind("file://", 0) == 0) return load_file(resolved.substr(7));
    if (resolved.rfind("data:", 0) == 0) return load_data_uri(resolved);
    if (cfg_.allow_http &&
        (resolved.rfind("http://", 0) == 0 || resolved.rfind("https://", 0) == 0))
        return load_http(resolved);
    return nullptr;
}

cairo_surface_t* ImageCache::load_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return nullptr;
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(f)), {});
    if (data.size() > cfg_.max_image_bytes) return nullptr;
    return load_from_memory(data.data(), data.size());
}

// ── data: URI support ─────────────────────────────────────────────────────────

cairo_surface_t* ImageCache::load_data_uri(const std::string& uri) {
    // Format: data:[<mediatype>][;base64],<data>
    auto comma = uri.find(',');
    if (comma == std::string::npos) return nullptr;

    std::string header = uri.substr(5, comma - 5);  // skip "data:"
    bool is_base64 = header.find(";base64") != std::string::npos;
    if (!is_base64) return nullptr;  // only base64-encoded data URIs are supported

    std::vector<uint8_t> raw = base64_decode(uri.substr(comma + 1));
    if (raw.empty() || raw.size() > cfg_.max_image_bytes) return nullptr;

    return load_from_memory(raw.data(), raw.size());
}

// Detect image format by magic bytes and route to the appropriate decoder.
cairo_surface_t* ImageCache::load_from_memory(const uint8_t* data, size_t size) {
    if (size < 4) return nullptr;

    // PNG: 8-byte signature \x89PNG\r\n\x1a\n
    if (size >= 8 && data[0] == 0x89 && data[1] == 'P' && data[2] == 'N' && data[3] == 'G') {
        struct PngCtx { const uint8_t* p; size_t pos; size_t size; };
        PngCtx ctx{data, 0, size};
        auto read_fn = [](void* closure, unsigned char* buf, unsigned int len) -> cairo_status_t {
            auto* c = static_cast<PngCtx*>(closure);
            if (c->pos + len > c->size) return CAIRO_STATUS_READ_ERROR;
            std::memcpy(buf, c->p + c->pos, len);
            c->pos += len;
            return CAIRO_STATUS_SUCCESS;
        };
        cairo_surface_t* s = cairo_image_surface_create_from_png_stream(read_fn, &ctx);
        if (cairo_surface_status(s) == CAIRO_STATUS_SUCCESS) return s;
        cairo_surface_destroy(s);
        return nullptr;
    }

    // JPEG: \xFF\xD8\xFF
    if (data[0] == 0xFF && data[1] == 0xD8 && data[2] == 0xFF)
        return load_jpeg_mem(data, size);

    // WebP: RIFF....WEBP
    if (size >= 12 && data[0] == 'R' && data[1] == 'I' && data[2] == 'F' && data[3] == 'F' &&
        data[8] == 'W' && data[9] == 'E' && data[10] == 'B' && data[11] == 'P')
        return load_webp_mem(data, size);

    // SVG: starts with '<svg' or '<?xml' (skip leading whitespace)
    {
        size_t i = 0;
        while (i < size && (data[i] == ' ' || data[i] == '\t' ||
                             data[i] == '\r' || data[i] == '\n')) ++i;
        bool looks_svg = false;
        if (i + 4 <= size && data[i] == '<' && data[i+1] == 's' &&
                              data[i+2] == 'v' && data[i+3] == 'g')
            looks_svg = true;
        if (!looks_svg && i + 5 <= size && data[i] == '<' && data[i+1] == '?' &&
                                           data[i+2] == 'x' && data[i+3] == 'm' && data[i+4] == 'l')
            looks_svg = true;
        if (looks_svg) return load_svg_mem(data, size);
    }

    return nullptr;
}

cairo_surface_t* ImageCache::load_jpeg_mem(const uint8_t* data, size_t size) {
    struct SafeErr { jpeg_error_mgr pub; jmp_buf jmpbuf; };
    static auto err_exit = [](j_common_ptr c) {
        longjmp(reinterpret_cast<SafeErr*>(c->err)->jmpbuf, 1);
    };

    jpeg_decompress_struct cinfo{};
    SafeErr jerr{};
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = err_exit;

    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_decompress(&cinfo);
        return nullptr;
    }

    jpeg_create_decompress(&cinfo);
    jpeg_mem_src(&cinfo, const_cast<unsigned char*>(data), static_cast<unsigned long>(size));
    jpeg_read_header(&cinfo, TRUE);
    cinfo.out_color_space = JCS_RGB;
    jpeg_start_decompress(&cinfo);

    int w = cinfo.output_width, h = cinfo.output_height;
    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_surface_flush(surf);
    uint8_t* dst = cairo_image_surface_get_data(surf);
    int stride = cairo_image_surface_get_stride(surf);

    std::vector<uint8_t> row_buf(w * 3);
    while (cinfo.output_scanline < static_cast<JDIMENSION>(h)) {
        JSAMPROW p = row_buf.data();
        jpeg_read_scanlines(&cinfo, &p, 1);
        int y = cinfo.output_scanline - 1;
        uint8_t* out = dst + y * stride;
        for (int x = 0; x < w; ++x) {
            out[x*4+0] = row_buf[x*3+2]; // B
            out[x*4+1] = row_buf[x*3+1]; // G
            out[x*4+2] = row_buf[x*3+0]; // R
            out[x*4+3] = 255;             // A
        }
    }
    cairo_surface_mark_dirty(surf);
    jpeg_finish_decompress(&cinfo);
    jpeg_destroy_decompress(&cinfo);
    return surf;
}

cairo_surface_t* ImageCache::load_webp_mem(const uint8_t* data, size_t size) {
    int w = 0, h = 0;
    uint8_t* rgba = WebPDecodeRGBA(data, size, &w, &h);
    if (!rgba) return nullptr;

    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    cairo_surface_flush(surf);
    uint8_t* dst = cairo_image_surface_get_data(surf);
    int stride = cairo_image_surface_get_stride(surf);

    for (int y = 0; y < h; ++y) {
        const uint8_t* src = rgba + y * w * 4;
        uint8_t* out = dst + y * stride;
        for (int x = 0; x < w; ++x) {
            uint8_t r = src[x*4+0], g = src[x*4+1],
                    b = src[x*4+2], a = src[x*4+3];
            out[x*4+0] = static_cast<uint8_t>((b * a + 127) / 255);
            out[x*4+1] = static_cast<uint8_t>((g * a + 127) / 255);
            out[x*4+2] = static_cast<uint8_t>((r * a + 127) / 255);
            out[x*4+3] = a;
        }
    }
    cairo_surface_mark_dirty(surf);
    free(rgba);  // WebPDecodeRGBA uses malloc; free() works on all libwebp versions
    return surf;
}

cairo_surface_t* ImageCache::load_svg_mem(const uint8_t* data, size_t size) {
#ifdef HAVE_LIBRSVG
    GError* err = nullptr;
    RsvgHandle* handle = rsvg_handle_new_from_data(data, size, &err);
    if (!handle) {
        if (err) g_error_free(err);
        return nullptr;
    }
    rsvg_handle_set_dpi(handle, 96.0);

    double w = 0.0, h = 0.0;
    if (!rsvg_handle_get_intrinsic_size_in_pixels(handle, &w, &h) || w <= 0 || h <= 0) {
        // SVG has no intrinsic size (e.g. only viewBox with no width/height).
        // Default to 512×512 — caller can scale later via CSS.
        w = h = 512.0;
    }

    int iw = static_cast<int>(std::ceil(w));
    int ih = static_cast<int>(std::ceil(h));
    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, iw, ih);
    cairo_t* cr = cairo_create(surf);

    // White background
    cairo_set_source_rgb(cr, 1.0, 1.0, 1.0);
    cairo_paint(cr);

    RsvgRectangle viewport{0.0, 0.0, static_cast<double>(iw), static_cast<double>(ih)};
    GError* render_err = nullptr;
    rsvg_handle_render_document(handle, cr, &viewport, &render_err);
    if (render_err) g_error_free(render_err);

    cairo_surface_flush(surf);
    cairo_destroy(cr);
    g_object_unref(handle);
    return surf;
#else
    (void)data; (void)size;
    return nullptr;
#endif
}

cairo_surface_t* ImageCache::load_http(const std::string& url) {
    std::string body = http_util::fetch(url, cfg_.timeout_ms);
    if (body.empty()) return nullptr;
    if (body.size() > cfg_.max_image_bytes) return nullptr;
    return load_from_memory(
        reinterpret_cast<const uint8_t*>(body.data()), body.size());
}

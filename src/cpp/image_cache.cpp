#include "image_cache.h"
#include "base64.h"
#include <cairo.h>
#include <webp/decode.h>
#include <cstdio>   // FILE — required before jpeglib.h
#include <jpeglib.h>
#include <csetjmp>
#include <cstring>
#include <cmath>
#include <iterator>
#include <mutex>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>

// SVG: vendored nanosvg (header-only, stdlib-only — works identically on all
// platforms including MSVC). The implementation must live in exactly one TU.
#define NANOSVG_IMPLEMENTATION
#include "vendor/nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "vendor/nanosvgrast.h"

#include "http_util.h"

namespace fs = std::filesystem;

// Straight-alpha RGBA (row-major, stride w*4) → new premultiplied ARGB32 cairo
// surface, or nullptr. Shared by the WebP and SVG decode paths.
static cairo_surface_t* surface_from_rgba(const uint8_t* rgba, int w, int h) {
    cairo_surface_t* surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    if (cairo_surface_status(surf) != CAIRO_STATUS_SUCCESS) {
        cairo_surface_destroy(surf);
        return nullptr;
    }
    cairo_surface_flush(surf);
    uint8_t* dst = cairo_image_surface_get_data(surf);
    const size_t stride = static_cast<size_t>(cairo_image_surface_get_stride(surf));

    for (int y = 0; y < h; ++y) {
        const uint8_t* src = rgba + static_cast<size_t>(y) * w * 4;
        uint8_t* out = dst + static_cast<size_t>(y) * stride;
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
    return surf;
}

ImageCache::ImageCache(Config cfg) : cfg_(std::move(cfg)) {}

ImageCache::~ImageCache() {
    for (auto& [key, entry] : map_) {
        if (entry->surface) cairo_surface_destroy(entry->surface);
    }
}

cairo_surface_t* ImageCache::get(const std::string& url, const std::string& base_url) {
    std::string key = resolve(url, base_url);
    if (key.empty()) return nullptr;

    // Fast path: shared lock. Hand back an extra reference so the surface
    // survives even if another thread evicts this entry right after we unlock.
    {
        std::shared_lock lk(mu_);
        auto it = map_.find(key);
        if (it != map_.end()) {
            touch(*it->second);
            return cairo_surface_reference(it->second->surface);
        }
    }

    // Slow path. Deduplicate concurrent first loads: exactly one thread decodes
    // a given key; the others wait on cv_ and pick the entry up from the map.
    {
        std::unique_lock lk(mu_);
        for (;;) {
            auto it = map_.find(key);
            if (it != map_.end()) {
                touch(*it->second);
                return cairo_surface_reference(it->second->surface);
            }
            if (loading_.insert(key).second) break;  // we are the loader
            cv_.wait(lk);  // another thread is decoding this key
        }
    }

    cairo_surface_t* surface = load(key);  // no lock held while decoding

    std::unique_lock lk(mu_);
    loading_.erase(key);
    cv_.notify_all();
    if (!surface) return nullptr;  // load failed; waiters will retry and fail too

    size_t img_bytes = static_cast<size_t>(
        cairo_image_surface_get_stride(surface)) *
        cairo_image_surface_get_height(surface);

    // A single image larger than the whole budget is never cached (it would
    // evict everything and still blow the bound). Hand the owned surface to the
    // caller directly without inserting.
    if (img_bytes > cfg_.max_bytes) return surface;

    evict_to_fit(img_bytes);
    map_[key] = std::make_unique<Entry>(surface, img_bytes, tick());
    used_bytes_ += img_bytes;
    // map_ holds one reference; return a second one to the caller.
    return cairo_surface_reference(surface);
}

void ImageCache::evict_to_fit(size_t needed) {
    // LRU: evict the entry with the smallest last_used stamp until it fits.
    // O(n) scan per eviction, but the map is small (tens of images) and
    // eviction is rare relative to hits.
    while (!map_.empty() && used_bytes_ + needed > cfg_.max_bytes) {
        auto victim = map_.begin();
        for (auto it = std::next(map_.begin()); it != map_.end(); ++it) {
            if (it->second->last_used.load(std::memory_order_relaxed) <
                victim->second->last_used.load(std::memory_order_relaxed))
                victim = it;
        }
        if (victim->second->surface) cairo_surface_destroy(victim->second->surface);
        used_bytes_ -= victim->second->bytes;
        map_.erase(victim);
    }
}

std::string ImageCache::resolve(const std::string& url, const std::string& base_url) const {
    if (url.empty()) return {};
    // data: URIs are self-contained; return as-is without base resolution
    if (url.rfind("data:", 0) == 0) return url;

    const bool base_is_file = base_url.rfind("file://", 0) == 0;
    const bool base_is_http = base_url.rfind("http://", 0) == 0 ||
                              base_url.rfind("https://", 0) == 0;

    // Absolute URL with an explicit scheme.
    if (url.find("://") != std::string::npos) {
        // file:// only honoured under a file:// base (render_file); blocked for
        // bare HTML strings so untrusted markup can't read local files.
        if (url.rfind("file://", 0) == 0 && !base_is_file) return {};
        return url;
    }

    // Root-relative URL ("/path"): resolve against the base's origin/root.
    if (url[0] == '/') {
        if (base_is_http) {
            // scheme://host  — strip the path, keep the origin.
            auto scheme_end = base_url.find("://");
            auto host_end   = base_url.find('/', scheme_end + 3);
            std::string origin = (host_end == std::string::npos)
                                     ? base_url : base_url.substr(0, host_end);
            return origin + url;
        }
        if (base_is_file) return "file://" + url;  // filesystem root
        return {};  // no base → refuse to touch the local filesystem
    }

    // Document-relative URL.
    if (base_is_file) {
        fs::path base = fs::path(base_url.substr(7)).parent_path();
        return "file://" + (base / url).string();
    }
    if (base_is_http) {
        // Strip the last path segment. Guard the no-path case ("http://host"),
        // where rfind('/') would otherwise land on the "://" slash.
        auto scheme_end = base_url.find("://");
        auto path_start = base_url.find('/', scheme_end + 3);
        if (path_start == std::string::npos) return base_url + "/" + url;
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

    // `surf` is volatile so the setjmp branch can free it safely: a non-volatile
    // local modified after setjmp has an indeterminate value after longjmp.
    cairo_surface_t* volatile surf = nullptr;
    if (setjmp(jerr.jmpbuf)) {
        if (surf) cairo_surface_destroy(const_cast<cairo_surface_t*>(surf));
        jpeg_destroy_decompress(&cinfo);
        return nullptr;
    }

    jpeg_create_decompress(&cinfo);
    jpeg_mem_src(&cinfo, const_cast<unsigned char*>(data), static_cast<unsigned long>(size));
    jpeg_read_header(&cinfo, TRUE);
    cinfo.out_color_space = JCS_RGB;
    jpeg_start_decompress(&cinfo);

    const int w = static_cast<int>(cinfo.output_width);
    const int h = static_cast<int>(cinfo.output_height);
    if (w <= 0 || h <= 0) { jpeg_destroy_decompress(&cinfo); return nullptr; }

    surf = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    // A decompression bomb can declare huge dimensions; Cairo then returns an
    // error surface with a NULL data pointer. Guard before writing pixels.
    if (cairo_surface_status(const_cast<cairo_surface_t*>(surf)) != CAIRO_STATUS_SUCCESS) {
        cairo_surface_destroy(const_cast<cairo_surface_t*>(surf));
        jpeg_destroy_decompress(&cinfo);
        return nullptr;
    }
    cairo_surface_flush(const_cast<cairo_surface_t*>(surf));
    uint8_t* dst = cairo_image_surface_get_data(const_cast<cairo_surface_t*>(surf));
    const size_t stride = static_cast<size_t>(
        cairo_image_surface_get_stride(const_cast<cairo_surface_t*>(surf)));

    std::vector<uint8_t> row_buf(static_cast<size_t>(w) * 3);
    while (cinfo.output_scanline < static_cast<JDIMENSION>(h)) {
        JSAMPROW p = row_buf.data();
        jpeg_read_scanlines(&cinfo, &p, 1);
        const size_t y = static_cast<size_t>(cinfo.output_scanline - 1);
        uint8_t* out = dst + y * stride;
        for (int x = 0; x < w; ++x) {
            out[x*4+0] = row_buf[x*3+2]; // B
            out[x*4+1] = row_buf[x*3+1]; // G
            out[x*4+2] = row_buf[x*3+0]; // R
            out[x*4+3] = 255;             // A
        }
    }
    cairo_surface_mark_dirty(const_cast<cairo_surface_t*>(surf));
    jpeg_finish_decompress(&cinfo);
    jpeg_destroy_decompress(&cinfo);
    return const_cast<cairo_surface_t*>(surf);
}

cairo_surface_t* ImageCache::load_webp_mem(const uint8_t* data, size_t size) {
    int w = 0, h = 0;
    uint8_t* rgba = WebPDecodeRGBA(data, size, &w, &h);
    if (!rgba) return nullptr;
    if (w <= 0 || h <= 0) { free(rgba); return nullptr; }

    cairo_surface_t* surf = surface_from_rgba(rgba, w, h);
    free(rgba);  // WebPDecodeRGBA uses malloc; free() works on all libwebp versions
    return surf;
}

// SVG via vendored nanosvg: covers the icon/graphics subset (paths, basic
// shapes, strokes, userSpaceOnUse gradients). NOT covered: <text>, filters,
// objectBoundingBox gradient coords. Output keeps transparency so icons
// composite correctly over coloured page backgrounds.
cairo_surface_t* ImageCache::load_svg_mem(const uint8_t* data, size_t size) {
    // nsvgParse mutates its input and expects NUL-terminated text.
    std::string text(reinterpret_cast<const char*>(data), size);
    NSVGimage* img = nsvgParse(text.data(), "px", 96.0f);
    if (!img) return nullptr;

    // Decompression-bomb guard: an SVG can declare absurd dimensions (also,
    // float→int cast is UB once the value exceeds INT_MAX). Reject instead of
    // attempting a giant rasterization buffer.
    constexpr float kMaxDim = 16384.0f;
    const float w = img->width, h = img->height;
    if (w <= 0.0f || h <= 0.0f || w > kMaxDim || h > kMaxDim) {
        nsvgDelete(img);
        return nullptr;
    }
    const int iw = static_cast<int>(std::ceil(w));
    const int ih = static_cast<int>(std::ceil(h));

    std::vector<uint8_t> rgba(static_cast<size_t>(iw) * ih * 4);
    NSVGrasterizer* rast = nsvgCreateRasterizer();
    if (!rast) {
        nsvgDelete(img);
        return nullptr;
    }
    nsvgRasterize(rast, img, 0, 0, 1.0f, rgba.data(), iw, ih, iw * 4);
    nsvgDeleteRasterizer(rast);
    nsvgDelete(img);

    return surface_from_rgba(rgba.data(), iw, ih);
}

cairo_surface_t* ImageCache::load_http(const std::string& url) {
    std::string body = http_util::fetch(url, cfg_.timeout_ms);
    if (body.empty()) return nullptr;
    if (body.size() > cfg_.max_image_bytes) return nullptr;
    return load_from_memory(
        reinterpret_cast<const uint8_t*>(body.data()), body.size());
}

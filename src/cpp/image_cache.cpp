// src/cpp/image_cache.cpp
#include "image_cache.h"
#include <cairo.h>
#include <webp/decode.h>
#include <jpeglib.h>
#include <csetjmp>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <random>
#include <chrono>
#include <vector>

#undef CPPHTTPLIB_OPENSSL_SUPPORT
#include "vendor/httplib.h"

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
    if (url.find("://") != std::string::npos) return url;
    if (url[0] == '/') return "file://" + url;
    if (base_url.substr(0, 7) == "file://") {
        fs::path base = fs::path(base_url.substr(7)).parent_path();
        return "file://" + (base / url).string();
    }
    if (base_url.substr(0, 7) == "http://" || base_url.substr(0, 8) == "https://") {
        auto slash = base_url.rfind('/');
        return base_url.substr(0, slash + 1) + url;
    }
    return {};
}

cairo_surface_t* ImageCache::load(const std::string& resolved) {
    if (resolved.substr(0, 7) == "file://") return load_file(resolved.substr(7));
    if (cfg_.allow_http &&
        (resolved.substr(0, 7) == "http://" || resolved.substr(0, 8) == "https://"))
        return load_http(resolved);
    return nullptr;
}

cairo_surface_t* ImageCache::load_file(const std::string& path) {
    // Try PNG (Cairo built-in)
    cairo_surface_t* s = cairo_image_surface_create_from_png(path.c_str());
    if (cairo_surface_status(s) == CAIRO_STATUS_SUCCESS) return s;
    cairo_surface_destroy(s);

    // Try JPEG
    s = load_jpeg_file(path);
    if (s) return s;

    // Try WebP
    return load_webp_file(path);
}

cairo_surface_t* ImageCache::load_jpeg_file(const std::string& path) {
    struct SafeErr {
        jpeg_error_mgr pub;
        jmp_buf jmpbuf;
    };
    static auto err_exit = [](j_common_ptr c) {
        longjmp(reinterpret_cast<SafeErr*>(c->err)->jmpbuf, 1);
    };

    FILE* f = fopen(path.c_str(), "rb");
    if (!f) return nullptr;

    jpeg_decompress_struct cinfo{};
    SafeErr jerr{};
    cinfo.err = jpeg_std_error(&jerr.pub);
    jerr.pub.error_exit = err_exit;

    if (setjmp(jerr.jmpbuf)) {
        jpeg_destroy_decompress(&cinfo);
        fclose(f);
        return nullptr;
    }

    jpeg_create_decompress(&cinfo);
    jpeg_stdio_src(&cinfo, f);
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
    fclose(f);
    return surf;
}

cairo_surface_t* ImageCache::load_webp_file(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return nullptr;
    std::string data((std::istreambuf_iterator<char>(f)), {});
    if (data.size() > cfg_.max_image_bytes) return nullptr;

    int w = 0, h = 0;
    uint8_t* rgba = WebPDecodeRGBA(
        reinterpret_cast<const uint8_t*>(data.data()), data.size(), &w, &h);
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
            // Premultiply alpha for CAIRO_FORMAT_ARGB32
            out[x*4+0] = static_cast<uint8_t>((b * a + 127) / 255);
            out[x*4+1] = static_cast<uint8_t>((g * a + 127) / 255);
            out[x*4+2] = static_cast<uint8_t>((r * a + 127) / 255);
            out[x*4+3] = a;
        }
    }
    cairo_surface_mark_dirty(surf);
    WebPFree(rgba);
    return surf;
}

cairo_surface_t* ImageCache::load_http(const std::string& url) {
    bool https = url.substr(0, 8) == "https://";
    std::string rest = url.substr(https ? 8 : 7);
    auto slash = rest.find('/');
    std::string host = rest.substr(0, slash);
    std::string path = slash != std::string::npos ? rest.substr(slash) : "/";

    httplib::Client cli((https ? "https://" : "http://") + host);
    int sec = cfg_.timeout_ms / 1000;
    int us  = (cfg_.timeout_ms % 1000) * 1000;
    cli.set_connection_timeout(sec, us);
    cli.set_read_timeout(sec, us);

    auto res = cli.Get(path);
    if (!res || res->status != 200) return nullptr;
    if (res->body.size() > cfg_.max_image_bytes) return nullptr;

    // Unique temp file per call to avoid concurrent races
    auto uid = std::chrono::steady_clock::now().time_since_epoch().count();
    std::mt19937_64 rng(uid ^ reinterpret_cast<uintptr_t>(&url));
    std::string tmp = (fs::temp_directory_path() /
        ("pylitehtml_" + std::to_string(rng()) + ".tmp")).string();
    {
        std::ofstream out(tmp, std::ios::binary);
        out.write(res->body.data(), res->body.size());
    }
    cairo_surface_t* surf = load_file(tmp);
    fs::remove(tmp);
    return surf;
}

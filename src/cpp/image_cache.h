// src/cpp/image_cache.h
#pragma once
#include <cairo.h>
#include <list>
#include <shared_mutex>
#include <string>
#include <unordered_map>
#include <cstdint>

// Thread-safe image cache with FIFO eviction (bounded by byte count).
// Holds decoded cairo_surface_t* ready to draw.
class ImageCache {
public:
    struct Config {
        size_t max_bytes       = 64 * 1024 * 1024;
        int    timeout_ms      = 5000;
        size_t max_image_bytes = 10 * 1024 * 1024;
        bool   allow_http      = true;
    };

    explicit ImageCache(Config cfg);
    ~ImageCache();

    // Returns non-owning pointer valid for lifetime of this cache, or nullptr.
    cairo_surface_t* get(const std::string& url, const std::string& base_url);

private:
    struct Entry {
        cairo_surface_t* surface;
        size_t bytes;
    };

    std::string resolve(const std::string& url, const std::string& base_url) const;
    cairo_surface_t* load(const std::string& resolved);
    cairo_surface_t* load_file(const std::string& path);
    cairo_surface_t* load_jpeg_file(const std::string& path);
    cairo_surface_t* load_webp_file(const std::string& path);
    cairo_surface_t* load_http(const std::string& url);
    cairo_surface_t* load_data_uri(const std::string& uri);
    cairo_surface_t* load_from_memory(const uint8_t* data, size_t size);
    cairo_surface_t* load_jpeg_mem(const uint8_t* data, size_t size);
    cairo_surface_t* load_webp_mem(const uint8_t* data, size_t size);
    void evict_to_fit(size_t needed);  // call under exclusive lock

    Config cfg_;
    mutable std::shared_mutex mu_;
    std::list<std::string> insertion_order_;   // FIFO: front=oldest
    std::unordered_map<std::string, Entry> map_;
    size_t used_bytes_ = 0;
};

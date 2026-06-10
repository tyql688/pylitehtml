#pragma once
#include <cairo.h>
#include <atomic>
#include <condition_variable>
#include <memory>
#include <shared_mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <cstdint>

// Thread-safe image cache with LRU eviction (bounded by byte count).
// Holds decoded cairo_surface_t* ready to draw. Concurrent first loads of the
// same URL are deduplicated: one thread decodes, the others wait for the entry.
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

    // Returns an OWNED surface reference (already cairo_surface_reference'd), or
    // nullptr. The caller MUST cairo_surface_destroy() it when done. This keeps
    // the surface alive even if another thread evicts the cache entry mid-use,
    // making concurrent renders that share one cache safe.
    cairo_surface_t* get(const std::string& url, const std::string& base_url);

    bool allow_http() const { return cfg_.allow_http; }
    int  timeout_ms() const { return cfg_.timeout_ms; }

private:
    struct Entry {
        cairo_surface_t* surface;
        size_t bytes;
        // LRU stamp; atomic so cache hits can bump it under the shared lock.
        std::atomic<uint64_t> last_used;
        Entry(cairo_surface_t* s, size_t b, uint64_t t)
            : surface(s), bytes(b), last_used(t) {}
    };

    std::string resolve(const std::string& url, const std::string& base_url) const;
    cairo_surface_t* load(const std::string& resolved);
    cairo_surface_t* load_file(const std::string& path);
    cairo_surface_t* load_http(const std::string& url);
    cairo_surface_t* load_data_uri(const std::string& uri);
    cairo_surface_t* load_from_memory(const uint8_t* data, size_t size);
    cairo_surface_t* load_jpeg_mem(const uint8_t* data, size_t size);
    cairo_surface_t* load_webp_mem(const uint8_t* data, size_t size);
    cairo_surface_t* load_svg_mem(const uint8_t* data, size_t size);
    void evict_to_fit(size_t needed);  // call under exclusive lock
    uint64_t tick() { return clock_.fetch_add(1, std::memory_order_relaxed) + 1; }
    // Bump LRU recency. Safe under the shared lock: last_used is atomic.
    void touch(Entry& e) { e.last_used.store(tick(), std::memory_order_relaxed); }

    Config cfg_;
    mutable std::shared_mutex mu_;
    std::condition_variable_any cv_;          // signals completed loads
    std::unordered_set<std::string> loading_; // keys currently being decoded
    std::unordered_map<std::string, std::unique_ptr<Entry>> map_;
    std::atomic<uint64_t> clock_{0};          // LRU timestamp source
    size_t used_bytes_ = 0;
};

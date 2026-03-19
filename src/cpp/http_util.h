// src/cpp/http_util.h
#pragma once
#include <string>
#include <optional>

namespace http_util {

struct ParsedUrl {
    std::string scheme;   // "http" or "https"
    std::string host;     // "example.com" or "example.com:8080"
    std::string path;     // "/path/to/resource"
};

// Parse an HTTP/HTTPS URL into components. Returns nullopt on failure.
std::optional<ParsedUrl> parse_url(const std::string& url);

// Fetch a URL via HTTP/HTTPS. Returns response body, or empty string on failure.
std::string fetch(const std::string& url, int timeout_ms = 5000);

} // namespace http_util

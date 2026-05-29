#pragma once
#include <string>

namespace http_util {

// Fetch a URL via HTTP/HTTPS. Returns response body, or empty string on failure.
std::string fetch(const std::string& url, int timeout_ms = 5000);

} // namespace http_util

#include "http_util.h"

#include <optional>

// CPPHTTPLIB_OPENSSL_SUPPORT is defined by the build (CMake) when OpenSSL is
// available, enabling https://. When it is not, https requests are skipped
// gracefully below rather than failing the render.
#include "vendor/httplib.h"

namespace http_util {
namespace {

struct ParsedUrl {
    std::string scheme;   // "http" or "https"
    std::string host;     // "example.com" or "example.com:8080"
    std::string path;     // "/path/to/resource"
};

// Parse an HTTP/HTTPS URL into components. Returns nullopt on failure.
std::optional<ParsedUrl> parse_url(const std::string& url) {
    bool https = url.rfind("https://", 0) == 0;
    bool http  = url.rfind("http://", 0) == 0;
    if (!https && !http) return std::nullopt;

    std::string rest = url.substr(https ? 8 : 7);
    auto slash = rest.find('/');
    ParsedUrl parsed;
    parsed.scheme = https ? "https" : "http";
    parsed.host   = rest.substr(0, slash);
    parsed.path   = (slash != std::string::npos) ? rest.substr(slash) : "/";
    return parsed;
}

} // namespace

std::string fetch(const std::string& url, int timeout_ms) {
    // A network fetch must never crash a render: any failure (unreachable host,
    // TLS error, unsupported scheme, httplib throwing) returns an empty body and
    // the caller simply skips the resource.
    try {
        auto parsed = parse_url(url);
        if (!parsed) return {};
#ifndef CPPHTTPLIB_OPENSSL_SUPPORT
        if (parsed->scheme == "https") return {};  // HTTPS unavailable in this build
#endif
        httplib::Client cli(parsed->scheme + "://" + parsed->host);
        cli.set_follow_location(true);   // many image/CSS URLs redirect
        const int sec = timeout_ms / 1000;
        const int us  = (timeout_ms % 1000) * 1000;
        cli.set_connection_timeout(sec, us);
        cli.set_read_timeout(sec, us);

        auto res = cli.Get(parsed->path);
        if (!res || res->status < 200 || res->status >= 300) return {};
        return res->body;
    } catch (...) {
        return {};
    }
}

} // namespace http_util

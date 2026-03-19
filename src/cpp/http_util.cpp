// src/cpp/http_util.cpp
#include "http_util.h"

#undef CPPHTTPLIB_OPENSSL_SUPPORT
#include "vendor/httplib.h"

namespace http_util {

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

std::string fetch(const std::string& url, int timeout_ms) {
    auto parsed = parse_url(url);
    if (!parsed) return {};

    httplib::Client cli(parsed->scheme + "://" + parsed->host);
    int sec = timeout_ms / 1000;
    int us  = (timeout_ms % 1000) * 1000;
    cli.set_connection_timeout(sec, us);
    cli.set_read_timeout(sec, us);

    auto res = cli.Get(parsed->path);
    if (!res || res->status != 200) return {};
    return res->body;
}

} // namespace http_util

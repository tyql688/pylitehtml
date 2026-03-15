// src/cpp/base64.h
#pragma once
#include <cstdint>
#include <string>
#include <vector>

// Decode standard base64 (RFC 4648). Ignores whitespace; stops at '=' padding.
inline std::vector<uint8_t> base64_decode(const std::string& in) {
    auto decode_char = [](unsigned char c) -> int {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;  // whitespace, padding, invalid — skip
    };

    std::vector<uint8_t> out;
    out.reserve(in.size() * 3 / 4);
    uint32_t val = 0;
    int bits = 0;
    for (unsigned char c : in) {
        if (c == '=') break;
        int v = decode_char(c);
        if (v < 0) continue;
        val = (val << 6) | static_cast<uint32_t>(v);
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out.push_back(static_cast<uint8_t>((val >> bits) & 0xFF));
        }
    }
    return out;
}

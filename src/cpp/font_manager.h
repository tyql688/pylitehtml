// src/cpp/font_manager.h
#pragma once
#include <fontconfig/fontconfig.h>
#include <mutex>
#include <set>
#include <string>
#include <vector>

class FontManager {
public:
    struct Config {
        std::string fonts_dir;
        std::string default_font      = "Noto Sans";
        int         default_font_size = 16;
        std::vector<std::string> extra_fonts;
    };

    explicit FontManager(Config cfg);
    ~FontManager();

    FontManager(const FontManager&) = delete;
    FontManager& operator=(const FontManager&) = delete;
    FontManager(FontManager&&) = delete;
    FontManager& operator=(FontManager&&) = delete;

    const std::string& default_font() const { return cfg_.default_font; }
    int default_font_size_px() const { return cfg_.default_font_size; }

private:
    Config cfg_;

    // Process-wide shared state
    static std::once_flag   fc_init_flag_;
    static std::mutex       fc_mutex_;
    static FcConfig*        fc_config_;
    static std::set<std::string> registered_fonts_;
};

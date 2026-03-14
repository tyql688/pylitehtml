// src/cpp/font_manager.h
#pragma once
#include <fontconfig/fontconfig.h>
#include <pango/pango.h>
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

    const std::string& default_font() const { return cfg_.default_font; }
    int default_font_size_px() const { return cfg_.default_font_size; }
    PangoFontMap* font_map() const { return font_map_; }

private:
    Config cfg_;
    FcConfig* fc_config_ = nullptr;
    PangoFontMap* font_map_ = nullptr;
};

// src/cpp/font_manager.cpp
#include "font_manager.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <stdexcept>

namespace fs = std::filesystem;

std::once_flag          FontManager::fc_init_flag_;
std::mutex              FontManager::fc_mutex_;
FcConfig*               FontManager::fc_config_ = nullptr;
std::set<std::string>   FontManager::registered_fonts_;

FontManager::FontManager(Config cfg) : cfg_(std::move(cfg)) {
    // Base init: once per process
    std::call_once(fc_init_flag_, [this]() {
        fc_config_ = FcConfigCreate();
        if (!fc_config_) throw std::runtime_error("FcConfigCreate failed");

        const FcChar8* sys_conf = FcConfigFilename(nullptr);
        if (sys_conf) FcConfigParseAndLoad(fc_config_, sys_conf, FcFalse);

        fs::path conf = fs::path(cfg_.fonts_dir) / "fonts.conf";
        if (fs::exists(conf))
            FcConfigParseAndLoad(fc_config_,
                reinterpret_cast<const FcChar8*>(conf.string().c_str()), FcFalse);

        FcConfigAppFontAddDir(fc_config_,
            reinterpret_cast<const FcChar8*>(cfg_.fonts_dir.c_str()));

        FcConfigBuildFonts(fc_config_);
        FcConfigSetCurrent(fc_config_);
    });

    // Incremental: register new extra_fonts (thread-safe)
    if (!cfg_.extra_fonts.empty()) {
        std::lock_guard lk(fc_mutex_);
        bool added = false;
        for (const auto& path : cfg_.extra_fonts) {
            if (registered_fonts_.insert(path).second) {
                FcConfigAppFontAddFile(fc_config_,
                    reinterpret_cast<const FcChar8*>(path.c_str()));
                added = true;
            }
        }
        if (added) {
            FcConfigBuildFonts(fc_config_);
        }
    }
}

FontManager::~FontManager() {
    // fc_config_ is process-global; do not free.
}

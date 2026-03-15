// src/cpp/font_manager.cpp
#include "font_manager.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <stdexcept>

namespace fs = std::filesystem;

std::once_flag FontManager::fc_init_flag_;

FontManager::FontManager(Config cfg) : cfg_(std::move(cfg)) {
    // ── Fontconfig global init (once per process) ─────────────────────────────
    // FcConfigSetCurrent sets a process-global pointer. We run the full init
    // only once; subsequent Renderer instances reuse the same fontconfig state.
    // Limitation: extra_fonts from the first Renderer wins for the process.
    std::call_once(fc_init_flag_, [this]() {
        fc_config_ = FcConfigCreate();
        if (!fc_config_) throw std::runtime_error("FcConfigCreate failed");

        // Step 1: system fonts
        const FcChar8* sys_conf = FcConfigFilename(nullptr);
        if (sys_conf) FcConfigParseAndLoad(fc_config_, sys_conf, FcFalse);

        // Step 2: bundled fonts.conf
        fs::path conf = fs::path(cfg_.fonts_dir) / "fonts.conf";
        if (fs::exists(conf))
            FcConfigParseAndLoad(fc_config_,
                reinterpret_cast<const FcChar8*>(conf.string().c_str()), FcFalse);

        // Step 3: bundled fonts directory
        FcConfigAppFontAddDir(fc_config_,
            reinterpret_cast<const FcChar8*>(cfg_.fonts_dir.c_str()));

        // Step 4: extra user fonts
        for (const auto& path : cfg_.extra_fonts)
            FcConfigAppFontAddFile(fc_config_,
                reinterpret_cast<const FcChar8*>(path.c_str()));

        // Step 5: build index, then activate (LAST)
        FcConfigBuildFonts(fc_config_);
        FcConfigSetCurrent(fc_config_);
        // fc_config_ is now owned by fontconfig; do not destroy it.
    });
}

FontManager::~FontManager() {
    // fc_config_ is owned by fontconfig after FcConfigSetCurrent; do not free.
}

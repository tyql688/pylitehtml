// src/cpp/font_manager.cpp
#include "font_manager.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <stdexcept>

namespace fs = std::filesystem;

std::atomic<bool> FontManager::instance_exists_{false};

FontManager::FontManager(Config cfg) : cfg_(std::move(cfg)) {
    if (instance_exists_.exchange(true))
        throw std::runtime_error("Only one FontManager may exist at a time (FcConfigSetCurrent is global)");

    // ── Step 1: create a fresh fontconfig config ──────────────────────────────
    fc_config_ = FcConfigCreate();
    if (!fc_config_) throw std::runtime_error("FcConfigCreate failed");

    // ── Step 2: load system fonts into this config ────────────────────────────
    {
        const FcChar8* sys_conf = FcConfigFilename(nullptr);  // system fonts.conf path
        if (sys_conf) FcConfigParseAndLoad(fc_config_, sys_conf, FcFalse);
    }

    // ── Step 3: load bundled fonts.conf (Windows runtime path setup) ──────────
    fs::path conf = fs::path(cfg_.fonts_dir) / "fonts.conf";
    if (fs::exists(conf)) {
        FcConfigParseAndLoad(fc_config_,
            reinterpret_cast<const FcChar8*>(conf.string().c_str()), FcFalse);
    }

    // ── Step 4: add bundled fonts directory ───────────────────────────────────
    FcConfigAppFontAddDir(fc_config_,
        reinterpret_cast<const FcChar8*>(cfg_.fonts_dir.c_str()));

    // ── Step 5: add user-supplied extra fonts ─────────────────────────────────
    for (const auto& path : cfg_.extra_fonts) {
        FcConfigAppFontAddFile(fc_config_,
            reinterpret_cast<const FcChar8*>(path.c_str()));
    }

    // ── Step 6: build font index ──────────────────────────────────────────────
    FcConfigBuildFonts(fc_config_);

    // ── Step 7: activate config (LAST — after all fonts are registered) ───────
    FcConfigSetCurrent(fc_config_);

    // ── Step 8: init Pango using the now-active fontconfig ────────────────────
    font_map_ = pango_cairo_font_map_new();
    if (!font_map_) {
        FcConfigDestroy(fc_config_);
        fc_config_ = nullptr;
        instance_exists_.store(false);
        throw std::runtime_error("pango_cairo_font_map_new failed");
    }
}

FontManager::~FontManager() {
    if (font_map_) g_object_unref(font_map_);
    // Note: do NOT call FcConfigDestroy on the current config while Pango is alive.
    // Pango holds a reference; let it be destroyed when Pango is cleaned up.
    instance_exists_.store(false);
}

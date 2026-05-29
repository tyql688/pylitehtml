#pragma once
#include <fontconfig/fontconfig.h>
#include <mutex>
#include <set>
#include <string>
#include <vector>

// Thread-safety note: fontconfig state is PROCESS-GLOBAL. The base config
// (system config + the bundled fonts dir) is built once via call_once for the
// first FontManager; later instances reuse it. Registering `extra_fonts`
// mutates and rebuilds that global config under fc_mutex_. Because Pango reads
// the global config during GIL-released renders WITHOUT that lock, you must
// construct all Renderers (especially with extra_fonts) BEFORE rendering
// concurrently — i.e. "thread-safe after construction", not during it.
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

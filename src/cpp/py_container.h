// src/cpp/py_container.h
#pragma once
#include "container_cairo.h"       // from third_party/litehtml/containers/cairo/
#include "font_manager.h"
#include "image_cache.h"
#include <pango/pangocairo.h>
#include <string>
#include <unordered_map>
#include <memory>

// FontHandle stores PangoFontDescription plus text decoration info.
struct FontHandle {
    PangoFontDescription* desc       = nullptr;
    bool underline                   = false;
    bool strikethrough               = false;
    bool overline                    = false;

    ~FontHandle() { if (desc) pango_font_description_free(desc); }
    FontHandle(const FontHandle&) = delete;
    FontHandle& operator=(const FontHandle&) = delete;
    FontHandle(FontHandle&&) = default;
    FontHandle() = default;
};

// PyContainer inherits container_cairo for all Cairo drawing primitives.
// It adds Pango-based text rendering and ImageCache-based image loading.
// MUST be stack-allocated inside render() — never stored in Renderer.
class PyContainer : public container_cairo {
public:
    PyContainer(FontManager& fm, ImageCache& ic, int width);
    ~PyContainer();

    // Render html into an internal cairo_surface_t; returns actual height.
    int render(const std::string& html, const std::string& base_url, int fixed_height);

    cairo_surface_t* surface() const { return surface_; }

    // ── Required overrides for font management ───────────────────────────────
    litehtml::uint_ptr create_font(const litehtml::font_description& descr,
                                   const litehtml::document* doc,
                                   litehtml::font_metrics* fm) override;
    void delete_font(litehtml::uint_ptr hFont) override;
    litehtml::pixel_t text_width(const char* text, litehtml::uint_ptr hFont) override;
    void draw_text(litehtml::uint_ptr hdc, const char* text, litehtml::uint_ptr hFont,
                   litehtml::web_color color, const litehtml::position& pos) override;
    litehtml::pixel_t pt_to_px(float pt) const override;
    litehtml::pixel_t get_default_font_size() const override;
    const char* get_default_font_name() const override;

    // ── Required overrides for image loading ──────────────────────────────────
    void load_image(const char* src, const char* baseurl, bool redraw_on_ready) override;
    void get_image_size(const char* src, const char* baseurl, litehtml::size& sz) override;
    void draw_image(litehtml::uint_ptr hdc, const litehtml::background_layer& layer,
                    const std::string& url, const std::string& base_url) override;

    // ── Required abstract methods from container_cairo ───────────────────────
    cairo_surface_t* get_image(const std::string& url) override;
    double get_screen_dpi() const override { return 96.0; }
    int get_screen_width() const override { return width_; }
    int get_screen_height() const override { return rendered_height_ > 0 ? rendered_height_ : 600; }

    // ── Overrides for metadata and CSS loading ───────────────────────────────
    void set_caption(const char*) override {}
    void set_base_url(const char* base_url) override;
    void link(const std::shared_ptr<litehtml::document>&,
              const litehtml::element::ptr&) override {}
    void on_anchor_click(const char*, const litehtml::element::ptr&) override {}
    void on_mouse_event(const litehtml::element::ptr&, litehtml::mouse_event) override {}
    void set_cursor(const char*) override {}
    void transform_text(litehtml::string& text, litehtml::text_transform tt) override;
    void import_css(litehtml::string& text, const litehtml::string& url,
                    litehtml::string& baseurl) override;
    void get_viewport(litehtml::position& vp) const override;
    litehtml::element::ptr create_element(const char*, const litehtml::string_map&,
                                          const std::shared_ptr<litehtml::document>&) override;
    void get_media_features(litehtml::media_features& mf) const override;
    void get_language(litehtml::string& lang, litehtml::string& culture) const override;

private:
    FontManager& fm_;
    ImageCache&  ic_;
    int          width_;
    int          rendered_height_ = 0;
    std::string  base_url_;

    cairo_surface_t* surface_ = nullptr;
    cairo_t*         cr_      = nullptr;

    // Font ID → FontHandle (owned)
    std::unordered_map<litehtml::uint_ptr, std::unique_ptr<FontHandle>> fonts_;
    litehtml::uint_ptr next_font_id_ = 1;

    void create_surface(int w, int h);
};

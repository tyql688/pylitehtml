// src/cpp/py_container.cpp
#include "py_container.h"
#include "base64.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cassert>
#include <cctype>
#include <cmath>
#include <stdexcept>

#undef CPPHTTPLIB_OPENSSL_SUPPORT
#include "vendor/httplib.h"

namespace fs = std::filesystem;

PyContainer::PyContainer(FontManager& fm, ImageCache& ic, int width,
                         float dpi, std::string lang, std::string culture)
    : fm_(fm), ic_(ic), width_(width)
    , dpi_(dpi > 0 ? dpi : 96.0f)
    , lang_(std::move(lang))
    , culture_(std::move(culture)) {}

PyContainer::~PyContainer() {
    fonts_.clear();
    if (cr_)      cairo_destroy(cr_);
    if (surface_) cairo_surface_destroy(surface_);
}

void PyContainer::create_surface(int w, int h) {
    if (cr_)      { cairo_destroy(cr_); cr_ = nullptr; }
    if (surface_) { cairo_surface_destroy(surface_); surface_ = nullptr; }
    surface_ = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    if (cairo_surface_status(surface_) != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error(std::string("Cairo surface: ") +
            cairo_status_to_string(cairo_surface_status(surface_)));
    cr_ = cairo_create(surface_);
    if (cairo_status(cr_) != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error("Cairo context create failed");
    // White background
    cairo_set_source_rgb(cr_, 1, 1, 1);
    cairo_paint(cr_);
}

int PyContainer::render(const std::string& html, const std::string& base_url,
                        int fixed_height, bool allow_refit) {
    base_url_ = base_url;
    create_surface(width_, 1);  // minimal surface needed for text metrics

    auto doc = litehtml::document::createFromString(html, this);
    if (!doc) throw std::runtime_error("litehtml: failed to parse HTML");

    doc->render(width_);

    // Auto-refit: if content bounding box is narrower than viewport, re-render at that width.
    // doc->width() returns the max right-edge across all rendered elements (starts at 0).
    if (allow_refit) {
        int cw = static_cast<int>(doc->width());
        if (cw > 0 && cw < width_) {
            width_ = cw;
            doc->render(width_);
        }
    }

    int h = (fixed_height > 0) ? fixed_height : static_cast<int>(doc->height());
    if (h < 1) h = 1;
    rendered_height_ = h;

    create_surface(width_, h);  // final surface with correct dimensions
    litehtml::position clip{0, 0, static_cast<litehtml::pixel_t>(width_),
                            static_cast<litehtml::pixel_t>(h)};
    doc->draw(reinterpret_cast<litehtml::uint_ptr>(cr_), 0, 0, &clip);
    cairo_surface_flush(surface_);
    return h;
}

// ── Fonts ─────────────────────────────────────────────────────────────────────
litehtml::uint_ptr PyContainer::create_font(const litehtml::font_description& descr,
                                             const litehtml::document*,
                                             litehtml::font_metrics* fm_out) {
    auto handle = std::make_unique<FontHandle>();
    handle->desc = pango_font_description_new();
    pango_font_description_set_family(handle->desc, descr.family.c_str());
    pango_font_description_set_absolute_size(handle->desc,
        static_cast<double>(descr.size) * PANGO_SCALE);
    pango_font_description_set_style(handle->desc,
        (descr.style == litehtml::font_style_italic) ? PANGO_STYLE_ITALIC : PANGO_STYLE_NORMAL);
    pango_font_description_set_weight(handle->desc,
        static_cast<PangoWeight>(descr.weight));

    // Store text decoration info using text_decoration_line flags
    handle->underline     = (descr.decoration_line & litehtml::text_decoration_line_underline) != 0;
    handle->strikethrough = (descr.decoration_line & litehtml::text_decoration_line_line_through) != 0;
    handle->overline      = (descr.decoration_line & litehtml::text_decoration_line_overline) != 0;

    // Measure font metrics
    if (fm_out) {
        assert(cr_ != nullptr && "create_font called before create_surface");
        PangoLayout* layout = pango_cairo_create_layout(cr_);
        pango_layout_set_font_description(layout, handle->desc);
        PangoContext* pango_ctx = pango_layout_get_context(layout);
        PangoFontMetrics* metrics = pango_context_get_metrics(pango_ctx, handle->desc, nullptr);
        fm_out->ascent   = static_cast<litehtml::pixel_t>(PANGO_PIXELS(pango_font_metrics_get_ascent(metrics)));
        fm_out->descent  = static_cast<litehtml::pixel_t>(PANGO_PIXELS(pango_font_metrics_get_descent(metrics)));
        fm_out->height   = fm_out->ascent + fm_out->descent;
        fm_out->x_height = fm_out->ascent / 2.0f;
        fm_out->font_size = descr.size;
        pango_font_metrics_unref(metrics);
        g_object_unref(layout);
    }

    litehtml::uint_ptr id = next_font_id_++;
    fonts_[id] = std::move(handle);
    return id;
}

void PyContainer::delete_font(litehtml::uint_ptr hFont) {
    fonts_.erase(hFont);
}

litehtml::pixel_t PyContainer::text_width(const char* text, litehtml::uint_ptr hFont) {
    auto it = fonts_.find(hFont);
    if (it == fonts_.end() || !cr_) return 0;
    PangoLayout* layout = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(layout, it->second->desc);
    pango_layout_set_text(layout, text, -1);
    int w = 0, h = 0;
    pango_layout_get_pixel_size(layout, &w, &h);
    g_object_unref(layout);
    return static_cast<litehtml::pixel_t>(w);
}

void PyContainer::draw_text(litehtml::uint_ptr, const char* text, litehtml::uint_ptr hFont,
                             litehtml::web_color color, const litehtml::position& pos) {
    auto it = fonts_.find(hFont);
    if (it == fonts_.end() || !cr_) return;
    const FontHandle& fh = *it->second;

    cairo_save(cr_);
    cairo_set_source_rgba(cr_, color.red/255.0, color.green/255.0,
                          color.blue/255.0, color.alpha/255.0);
    cairo_move_to(cr_, pos.x, pos.y);

    PangoLayout* layout = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(layout, fh.desc);
    pango_layout_set_text(layout, text, -1);
    pango_cairo_show_layout(cr_, layout);

    // Draw text decorations
    if (fh.underline || fh.strikethrough || fh.overline) {
        int w = 0, h = 0;
        pango_layout_get_pixel_size(layout, &w, &h);
        cairo_set_line_width(cr_, 1.0);
        if (fh.underline) {
            cairo_move_to(cr_, pos.x, pos.y + h);
            cairo_line_to(cr_, pos.x + w, pos.y + h);
            cairo_stroke(cr_);
        }
        if (fh.strikethrough) {
            cairo_move_to(cr_, pos.x, pos.y + h / 2.0);
            cairo_line_to(cr_, pos.x + w, pos.y + h / 2.0);
            cairo_stroke(cr_);
        }
        if (fh.overline) {
            cairo_move_to(cr_, pos.x, pos.y);
            cairo_line_to(cr_, pos.x + w, pos.y);
            cairo_stroke(cr_);
        }
    }

    g_object_unref(layout);
    cairo_restore(cr_);
}

litehtml::pixel_t PyContainer::pt_to_px(float pt) const {
    return static_cast<litehtml::pixel_t>(pt * dpi_ / 72.0f);
}
litehtml::pixel_t PyContainer::get_default_font_size() const {
    return static_cast<litehtml::pixel_t>(fm_.default_font_size_px());
}
const char* PyContainer::get_default_font_name() const {
    return fm_.default_font().c_str();
}

// ── Images ────────────────────────────────────────────────────────────────────
cairo_surface_t* PyContainer::get_image(const std::string& url) {
    return ic_.get(url, base_url_);
}

void PyContainer::load_image(const char* src, const char* baseurl, bool) {
    ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
}
void PyContainer::get_image_size(const char* src, const char* baseurl, litehtml::size& sz) {
    cairo_surface_t* s = ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
    if (s) {
        sz.width  = static_cast<litehtml::pixel_t>(cairo_image_surface_get_width(s));
        sz.height = static_cast<litehtml::pixel_t>(cairo_image_surface_get_height(s));
    }
}
// ic_.get() returns a non-owning pointer valid for the lifetime of ic_.
// Do not cache or store this pointer beyond this function.
void PyContainer::draw_image(litehtml::uint_ptr, const litehtml::background_layer& layer,
                              const std::string& url, const std::string& base_url) {
    cairo_surface_t* img = ic_.get(url, base_url.empty() ? base_url_ : base_url);
    if (!img || !cr_) return;
    cairo_save(cr_);
    cairo_set_source_surface(cr_, img, layer.origin_box.x, layer.origin_box.y);
    cairo_rectangle(cr_, layer.border_box.x, layer.border_box.y,
                    layer.border_box.width, layer.border_box.height);
    cairo_fill(cr_);
    cairo_restore(cr_);
}

// ── CSS / Base URL ────────────────────────────────────────────────────────────
void PyContainer::set_base_url(const char* u) { if (u) base_url_ = u; }

void PyContainer::import_css(litehtml::string& text, const litehtml::string& url,
                               litehtml::string& baseurl) {
    // Handle data: URIs directly (e.g. data:text/css;base64,...)
    if (url.rfind("data:", 0) == 0) {
        auto comma = url.find(',');
        if (comma != std::string::npos) {
            std::string header = url.substr(5, comma - 5);
            if (header.find(";base64") != std::string::npos) {
                auto raw = base64_decode(url.substr(comma + 1));
                text = std::string(raw.begin(), raw.end());
            } else {
                // Plain (URL-encoded) data URI — use as-is
                text = url.substr(comma + 1);
            }
        }
        return;
    }

    const std::string& effective_base = baseurl.empty() ? base_url_ : std::string(baseurl);
    if (effective_base.empty()) return;

    if (effective_base.rfind("file://", 0) == 0) {
        fs::path base_path = fs::path(effective_base.substr(7)).parent_path();
        fs::path css_path = base_path / url;
        std::ifstream f(css_path);
        if (f) { std::ostringstream ss; ss << f.rdbuf(); text = ss.str(); }
        return;
    }
    // HTTP CSS: skip
    text = "";
}

// ── Viewport / Media ──────────────────────────────────────────────────────────
void PyContainer::get_viewport(litehtml::position& vp) const {
    vp = {0, 0, static_cast<litehtml::pixel_t>(width_),
          static_cast<litehtml::pixel_t>(rendered_height_ > 0 ? rendered_height_ : 600)};
}
void PyContainer::get_media_features(litehtml::media_features& mf) const {
    mf.type       = litehtml::media_type_screen;
    mf.width      = static_cast<litehtml::pixel_t>(width_);
    mf.height     = static_cast<litehtml::pixel_t>(rendered_height_ > 0 ? rendered_height_ : 600);
    mf.color      = 8;
    mf.resolution = static_cast<litehtml::pixel_t>(dpi_);
}
void PyContainer::get_language(litehtml::string& lang, litehtml::string& culture) const {
    lang = lang_; culture = culture_;
}

// ── Text transform ────────────────────────────────────────────────────────────
void PyContainer::transform_text(litehtml::string& text, litehtml::text_transform tt) {
    if (tt == litehtml::text_transform_uppercase)
        std::transform(text.begin(), text.end(), text.begin(),
            [](unsigned char c) { return static_cast<char>(::toupper(c)); });
    else if (tt == litehtml::text_transform_lowercase)
        std::transform(text.begin(), text.end(), text.begin(),
            [](unsigned char c) { return static_cast<char>(::tolower(c)); });
}

litehtml::element::ptr PyContainer::create_element(const char*, const litehtml::string_map&,
                                                    const std::shared_ptr<litehtml::document>&) {
    return nullptr;
}

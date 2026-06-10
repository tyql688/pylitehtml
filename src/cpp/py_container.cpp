#include "py_container.h"
#include "base64.h"
#include <pango/pangocairo.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>

#include "http_util.h"

namespace fs = std::filesystem;

PyContainer::PyContainer(FontManager& fm, ImageCache& ic, int width,
                         float dpi, int device_height,
                         std::string lang, std::string culture,
                         bool allow_http)
    : fm_(fm), ic_(ic), width_(width)
    , dpi_(dpi > 0 ? dpi : 96.0f)
    , device_height_(device_height > 0 ? device_height : 600)
    , lang_(std::move(lang))
    , culture_(std::move(culture))
    , allow_http_(allow_http) {}

PyContainer::~PyContainer() {
    fonts_.clear();
    if (measure_layout_) g_object_unref(measure_layout_);
    if (cr_)      cairo_destroy(cr_);
    if (surface_) cairo_surface_destroy(surface_);
}

void PyContainer::create_surface(int w, int h) {
    // The measure layout is bound to cr_; drop it so it is rebuilt lazily.
    if (measure_layout_) { g_object_unref(measure_layout_); measure_layout_ = nullptr; }
    if (cr_)      { cairo_destroy(cr_); cr_ = nullptr; }
    if (surface_) { cairo_surface_destroy(surface_); surface_ = nullptr; }
    surface_ = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, w, h);
    if (cairo_surface_status(surface_) != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error(std::string("Cairo surface: ") +
            cairo_status_to_string(cairo_surface_status(surface_)));
    cr_ = cairo_create(surface_);
    if (cairo_status(cr_) != CAIRO_STATUS_SUCCESS)
        throw std::runtime_error("Cairo context create failed");
    cairo_set_source_rgb(cr_, 1, 1, 1);
    cairo_paint(cr_);
}

int PyContainer::render(const std::string& html,
                        int fixed_height, bool shrink_to_fit) {
    create_surface(width_, 1);  // minimal surface needed for text metrics

    auto doc = litehtml::document::createFromString(html, this);
    if (!doc) throw std::runtime_error("litehtml: failed to parse HTML");

    doc->render(width_);

    // Shrink-to-fit: if content bounding box is narrower than viewport, re-render at that width.
    // doc->width() returns the max right-edge across all rendered elements (starts at 0).
    if (shrink_to_fit) {
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

    handle->underline     = (descr.decoration_line & litehtml::text_decoration_line_underline) != 0;
    handle->strikethrough = (descr.decoration_line & litehtml::text_decoration_line_line_through) != 0;
    handle->overline      = (descr.decoration_line & litehtml::text_decoration_line_overline) != 0;

    // Always compute `ascent` (draw_text aligns runs to pos.y + ascent), not
    // only when litehtml requests fm_out.
    if (cr_) {
        PangoLayout* layout = pango_cairo_create_layout(cr_);
        pango_layout_set_font_description(layout, handle->desc);
        PangoContext* pango_ctx = pango_layout_get_context(layout);
        PangoFontMetrics* metrics = pango_context_get_metrics(pango_ctx, handle->desc, nullptr);
        // Keep sub-pixel precision: litehtml's pixel_t is float, so divide the
        // raw Pango units by PANGO_SCALE instead of rounding with PANGO_PIXELS.
        const float ascent  = pango_font_metrics_get_ascent(metrics)  / float(PANGO_SCALE);
        const float descent = pango_font_metrics_get_descent(metrics) / float(PANGO_SCALE);
        handle->ascent = ascent;

        if (fm_out) {
            fm_out->ascent    = static_cast<litehtml::pixel_t>(ascent);
            fm_out->descent   = static_cast<litehtml::pixel_t>(descent);
            fm_out->height    = static_cast<litehtml::pixel_t>(ascent + descent);
            fm_out->font_size = descr.size;

            // Real x-height: measure the ink height of 'x' (sub-pixel) rather
            // than guessing ascent/2. Affects the CSS `ex` unit and vertical-align.
            pango_layout_set_text(layout, "x", 1);
            PangoRectangle ink{};
            pango_layout_get_extents(layout, &ink, nullptr);
            fm_out->x_height = (ink.height > 0)
                ? ink.height / float(PANGO_SCALE)
                : ascent / 2.0f;
        }

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
    // Reuse one layout across calls — text_width is on the layout hot path.
    if (!measure_layout_) measure_layout_ = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(measure_layout_, it->second->desc);
    pango_layout_set_text(measure_layout_, text, -1);
    int w = 0, h = 0;
    // Sub-pixel width: pango_layout_get_size is in Pango units; rounding to
    // whole pixels here would drift text layout and break wrapping/alignment.
    pango_layout_get_size(measure_layout_, &w, &h);
    return static_cast<litehtml::pixel_t>(w) / float(PANGO_SCALE);
}

void PyContainer::draw_text(litehtml::uint_ptr, const char* text, litehtml::uint_ptr hFont,
                             litehtml::web_color color, const litehtml::position& pos) {
    auto it = fonts_.find(hFont);
    if (it == fonts_.end() || !cr_) return;
    const FontHandle& fh = *it->second;

    cairo_save(cr_);
    cairo_set_source_rgba(cr_, color.red/255.0, color.green/255.0,
                          color.blue/255.0, color.alpha/255.0);

    PangoLayout* layout = pango_cairo_create_layout(cr_);
    pango_layout_set_font_description(layout, fh.desc);
    pango_layout_set_text(layout, text, -1);

    // Pin every run to litehtml's baseline (pos.y + ascent). A layout's own
    // top-to-baseline distance varies by script, so drawing all layouts at pos.y
    // makes CJK drift relative to Latin ("飞").
    const double layout_baseline = pango_layout_get_baseline(layout) / double(PANGO_SCALE);
    const double baseline_y = pos.y + fh.ascent;       // litehtml's text baseline
    const double draw_y = baseline_y - layout_baseline;
    cairo_move_to(cr_, pos.x, draw_y);
    pango_cairo_show_layout(cr_, layout);

    // Decorations are placed against the same baseline.
    if (fh.underline || fh.strikethrough || fh.overline) {
        int w = 0, h = 0;
        pango_layout_get_pixel_size(layout, &w, &h);
        cairo_set_line_width(cr_, 1.0);
        if (fh.underline) {
            const double y = baseline_y + 1.0;
            cairo_move_to(cr_, pos.x, y);
            cairo_line_to(cr_, pos.x + w, y);
            cairo_stroke(cr_);
        }
        if (fh.strikethrough) {
            const double y = baseline_y - fh.ascent * 0.3;  // ~mid x-height
            cairo_move_to(cr_, pos.x, y);
            cairo_line_to(cr_, pos.x + w, y);
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
// ic_.get() returns an OWNED surface reference (or nullptr); every caller below
// is responsible for cairo_surface_destroy()'ing it. container_cairo's get_image
// contract is the same (it destroys what we return), so this stays consistent.
cairo_surface_t* PyContainer::get_image(const std::string& url) {
    return ic_.get(url, base_url_);
}

void PyContainer::load_image(const char* src, const char* baseurl, bool) {
    // Warm the cache, then release our reference immediately.
    cairo_surface_t* s = ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
    if (s) cairo_surface_destroy(s);
}
void PyContainer::get_image_size(const char* src, const char* baseurl, litehtml::size& sz) {
    cairo_surface_t* s = ic_.get(src ? src : "", baseurl ? baseurl : base_url_);
    if (s) {
        sz.width  = static_cast<litehtml::pixel_t>(cairo_image_surface_get_width(s));
        sz.height = static_cast<litehtml::pixel_t>(cairo_image_surface_get_height(s));
        cairo_surface_destroy(s);
    }
}
void PyContainer::draw_image(litehtml::uint_ptr, const litehtml::background_layer& layer,
                              const std::string& url, const std::string& base_url) {
    cairo_surface_t* img = ic_.get(url, base_url.empty() ? base_url_ : base_url);
    if (!img) return;
    if (!cr_) { cairo_surface_destroy(img); return; }
    cairo_save(cr_);
    cairo_set_source_surface(cr_, img, layer.origin_box.x, layer.origin_box.y);
    cairo_rectangle(cr_, layer.border_box.x, layer.border_box.y,
                    layer.border_box.width, layer.border_box.height);
    cairo_fill(cr_);
    cairo_restore(cr_);
    cairo_surface_destroy(img);
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

    std::string effective_base = baseurl.empty() ? base_url_ : std::string(baseurl);
    if (effective_base.empty()) return;

    if (effective_base.rfind("file://", 0) == 0) {
        fs::path base_path = fs::path(effective_base.substr(7)).parent_path();
        fs::path css_path = base_path / url;
        std::ifstream f(css_path);
        if (f) { std::ostringstream ss; ss << f.rdbuf(); text = ss.str(); }
        return;
    }

    // HTTP CSS: resolve URL and fetch
    if (!allow_http_) return;
    if (effective_base.rfind("http://", 0) == 0 || effective_base.rfind("https://", 0) == 0) {
        std::string abs_url;
        if (url.rfind("http://", 0) == 0 || url.rfind("https://", 0) == 0) {
            abs_url = url;
        } else {
            auto slash = effective_base.rfind('/');
            abs_url = effective_base.substr(0, slash + 1) + url;
        }
        text = http_util::fetch(abs_url, ic_.timeout_ms());
        return;
    }
}

// ── Viewport / Media ──────────────────────────────────────────────────────────
void PyContainer::get_viewport(litehtml::position& vp) const {
    vp = {0, 0, static_cast<litehtml::pixel_t>(width_),
          static_cast<litehtml::pixel_t>(rendered_height_ > 0 ? rendered_height_ : device_height_)};
}
void PyContainer::get_media_features(litehtml::media_features& mf) const {
    mf.type       = litehtml::media_type_screen;
    mf.width      = static_cast<litehtml::pixel_t>(width_);
    mf.height     = static_cast<litehtml::pixel_t>(rendered_height_ > 0 ? rendered_height_ : device_height_);
    mf.color      = 8;
    mf.resolution = static_cast<litehtml::pixel_t>(dpi_);
}
void PyContainer::get_language(litehtml::string& lang, litehtml::string& culture) const {
    lang = lang_; culture = culture_;
}

// ── Text transform ────────────────────────────────────────────────────────────
void PyContainer::transform_text(litehtml::string& text, litehtml::text_transform tt) {
    if (tt == litehtml::text_transform_uppercase) {
        char* upper = g_utf8_strup(text.c_str(), -1);
        text = upper;
        g_free(upper);
    } else if (tt == litehtml::text_transform_lowercase) {
        char* lower = g_utf8_strdown(text.c_str(), -1);
        text = lower;
        g_free(lower);
    }
}

litehtml::element::ptr PyContainer::create_element(const char*, const litehtml::string_map&,
                                                    const std::shared_ptr<litehtml::document>&) {
    return nullptr;
}

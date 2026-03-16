// src/cpp/binding.cpp
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <filesystem>
#include "font_manager.h"
#include "image_cache.h"
#include "py_container.h"
#include "encode.h"

namespace nb = nanobind;
namespace fs = std::filesystem;

static fs::path fonts_dir_from_module() {
    // _core.so lives at pylitehtml/_core.so; fonts/ is at pylitehtml/fonts/
    nb::object this_mod = nb::module_::import_("pylitehtml._core");
    std::string so_path = nb::cast<std::string>(
        nb::getattr(this_mod, "__file__", nb::str("")));
    return fs::path(so_path).parent_path() / "fonts";
}

enum class OutputFormat { PNG = 0, JPEG = 1, RAW = 2 };

struct RawResult {
    nb::bytes data;
    int width;
    int height;
};

struct RenderError    : std::runtime_error { using runtime_error::runtime_error; };
struct ImageFetchError: std::runtime_error { using runtime_error::runtime_error; };

class Renderer {
public:
    Renderer(int width, std::string default_font, int default_font_size,
             std::vector<std::string> extra_fonts,
             size_t image_cache_max_bytes, int image_timeout_ms,
             size_t image_max_bytes, bool allow_http_images,
             float dpi, int device_height, std::string lang, std::string culture)
        : width_(width)
        , dpi_(dpi > 0 ? dpi : 96.0f)
        , device_height_(device_height > 0 ? device_height : 600)
        , lang_(std::move(lang))
        , culture_(std::move(culture))
        , fm_(FontManager::Config{
              fonts_dir_from_module().string(),
              std::move(default_font),
              default_font_size,
              std::move(extra_fonts)})
        , ic_(ImageCache::Config{
              image_cache_max_bytes,
              image_timeout_ms,
              image_max_bytes,
              allow_http_images})
    {}

    nb::object render(const std::string& html, const std::string& base_url,
                      int height, OutputFormat fmt, int quality, bool shrink_to_fit) {
        // Release the GIL only for the CPU-heavy rendering work.
        // nb::bytes / nb::cast must be constructed while holding the GIL.
        std::vector<uint8_t> buf;
        int surf_w = 0, surf_h = 0;
        {
            nb::gil_scoped_release release;
            PyContainer container(fm_, ic_, width_, dpi_, device_height_, lang_, culture_);
            try {
                container.render(html, base_url, height, shrink_to_fit);
            } catch (const std::exception& e) {
                throw RenderError(e.what());
            }
            cairo_surface_t* surf = container.surface();
            surf_w = cairo_image_surface_get_width(surf);
            surf_h = cairo_image_surface_get_height(surf);
            switch (fmt) {
                case OutputFormat::PNG:  buf = encode::to_png(surf);           break;
                case OutputFormat::JPEG: buf = encode::to_jpeg(surf, quality); break;
                case OutputFormat::RAW:  buf = encode::to_rgba(surf);          break;
            }
        }
        // GIL re-acquired here — safe to construct Python objects
        auto pybytes = nb::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
        if (fmt == OutputFormat::RAW) {
            RawResult r;
            r.data   = std::move(pybytes);
            r.width  = surf_w;
            r.height = surf_h;
            return nb::cast(std::move(r));
        }
        return pybytes;
    }

private:
    int         width_;
    float       dpi_;
    int         device_height_;
    std::string lang_;
    std::string culture_;
    FontManager fm_;
    ImageCache  ic_;
};

NB_MODULE(_core, m) {
    m.doc() = "pylitehtml: HTML+CSS to image renderer";

    nb::exception<RenderError>(m, "RenderError");
    nb::exception<ImageFetchError>(m, "ImageFetchError");

    nb::enum_<OutputFormat>(m, "OutputFormat")
        .value("PNG",  OutputFormat::PNG)
        .value("JPEG", OutputFormat::JPEG)
        .value("RAW",  OutputFormat::RAW);
        // Note: no .export_values() — nanobind doesn't pollute module scope

    nb::class_<RawResult>(m, "RawResult")
        .def_ro("data",   &RawResult::data)
        .def_ro("width",  &RawResult::width)
        .def_ro("height", &RawResult::height);

    nb::class_<Renderer>(m, "Renderer")
        .def(nb::init<int,std::string,int,std::vector<std::string>,
                      size_t,int,size_t,bool,float,int,std::string,std::string>(),
             nb::arg("width"),
             nb::arg("default_font")          = "Noto Sans",
             nb::arg("default_font_size")     = 16,
             nb::arg("extra_fonts")           = std::vector<std::string>{},
             nb::arg("image_cache_max_bytes") = 64*1024*1024,
             nb::arg("image_timeout_ms")      = 5000,
             nb::arg("image_max_bytes")       = 10*1024*1024,
             nb::arg("allow_http_images")     = true,
             nb::arg("dpi")                   = 96.0f,
             nb::arg("device_height")         = 600,
             nb::arg("lang")                  = "en",
             nb::arg("culture")               = "en-US")
        .def("render", &Renderer::render,
             nb::arg("html"),
             nb::arg("base_url")      = "",
             nb::arg("height")        = 0,
             nb::arg("fmt")           = OutputFormat::PNG,
             nb::arg("quality")       = 85,
             nb::arg("shrink_to_fit") = false);

    // Note: this convenience function constructs a full Renderer (including
    // FontManager + FcConfigSetCurrent) on every call. For repeated rendering,
    // use the Renderer class directly.
    m.def("render",
        [](const std::string& html, int width, const std::string& base_url,
           int height, OutputFormat fmt, int quality, bool shrink_to_fit) -> nb::object {
            Renderer r(width,"Noto Sans",16,{},64*1024*1024,5000,10*1024*1024,
                       true,96.0f,600,"en","en-US");
            return r.render(html, base_url, height, fmt, quality, shrink_to_fit);
        },
        nb::arg("html"), nb::arg("width"),
        nb::arg("base_url")      = "",
        nb::arg("height")        = 0,
        nb::arg("fmt")           = OutputFormat::PNG,
        nb::arg("quality")       = 85,
        nb::arg("shrink_to_fit") = false);
}

// src/cpp/binding.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <filesystem>
#include "font_manager.h"
#include "image_cache.h"
#include "py_container.h"
#include "encode.h"

namespace py = pybind11;
namespace fs = std::filesystem;

static fs::path fonts_dir_from_module() {
    // _core.so lives at pylitehtml/_core.so; fonts/ is at pylitehtml/fonts/
    py::object this_mod = py::module_::import("pylitehtml._core");
    std::string so_path = py::cast<std::string>(
        py::getattr(this_mod, "__file__", py::str("")));
    return fs::path(so_path).parent_path() / "fonts";
}

enum class OutputFormat { PNG = 0, JPEG = 1, RAW = 2 };

struct RawResult {
    py::bytes data;
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

    py::object render(const std::string& html,
                      int height, OutputFormat fmt, int quality, bool shrink_to_fit) {
        // Release the GIL only for the CPU-heavy rendering work.
        // py::bytes / py::cast must be constructed while holding the GIL.
        std::vector<uint8_t> buf;
        int surf_w = 0, surf_h = 0;
        {
            py::gil_scoped_release release;
            PyContainer container(fm_, ic_, width_, dpi_, device_height_, lang_, culture_,
                                  ic_.allow_http());
            try {
                container.render(html, height, shrink_to_fit);
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
        auto pybytes = py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
        if (fmt == OutputFormat::RAW) {
            RawResult r;
            r.data   = std::move(pybytes);
            r.width  = surf_w;
            r.height = surf_h;
            return py::cast(std::move(r));
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

PYBIND11_MODULE(_core, m) {
    m.doc() = "pylitehtml: HTML+CSS to image renderer";

    py::register_exception<RenderError>(m, "RenderError");
    py::register_exception<ImageFetchError>(m, "ImageFetchError");

    py::enum_<OutputFormat>(m, "OutputFormat")
        .value("PNG",  OutputFormat::PNG)
        .value("JPEG", OutputFormat::JPEG)
        .value("RAW",  OutputFormat::RAW)
        .export_values();

    py::class_<RawResult>(m, "RawResult")
        .def_readonly("data",   &RawResult::data)
        .def_readonly("width",  &RawResult::width)
        .def_readonly("height", &RawResult::height);

    py::class_<Renderer>(m, "Renderer")
        .def(py::init<int,std::string,int,std::vector<std::string>,
                      size_t,int,size_t,bool,float,int,std::string,std::string>(),
             py::arg("width"),
             py::arg("default_font")          = "Noto Sans",
             py::arg("default_font_size")     = 16,
             py::arg("extra_fonts")           = std::vector<std::string>{},
             py::arg("image_cache_max_bytes") = 64*1024*1024,
             py::arg("image_timeout_ms")      = 5000,
             py::arg("image_max_bytes")       = 10*1024*1024,
             py::arg("allow_http_images")     = true,
             py::arg("dpi")                   = 96.0f,
             py::arg("device_height")         = 600,
             py::arg("lang")                  = "en",
             py::arg("culture")               = "en-US")
        .def("render", &Renderer::render,
             py::arg("html"),
             py::arg("height")        = 0,
             py::arg("fmt")           = OutputFormat::PNG,
             py::arg("quality")       = 85,
             py::arg("shrink_to_fit") = true);

    // Note: this convenience function constructs a full Renderer (including
    // FontManager + FcConfigSetCurrent) on every call. For repeated rendering,
    // use the Renderer class directly.
    m.def("render",
        [](const std::string& html, int width,
           const std::string& default_font, int default_font_size,
           const std::vector<std::string>& extra_fonts,
           size_t image_cache_max_bytes, int image_timeout_ms,
           size_t image_max_bytes, bool allow_http_images,
           float dpi, int device_height,
           const std::string& lang, const std::string& culture,
           int height, OutputFormat fmt, int quality, bool shrink_to_fit) -> py::object {
            Renderer r(width, default_font, default_font_size, extra_fonts,
                       image_cache_max_bytes, image_timeout_ms, image_max_bytes,
                       allow_http_images, dpi, device_height, lang, culture);
            return r.render(html, height, fmt, quality, shrink_to_fit);
        },
        py::arg("html"), py::arg("width"),
        py::arg("default_font")          = "Noto Sans",
        py::arg("default_font_size")     = 16,
        py::arg("extra_fonts")           = std::vector<std::string>{},
        py::arg("image_cache_max_bytes") = 64*1024*1024,
        py::arg("image_timeout_ms")      = 5000,
        py::arg("image_max_bytes")       = 10*1024*1024,
        py::arg("allow_http_images")     = true,
        py::arg("dpi")                   = 96.0f,
        py::arg("device_height")         = 600,
        py::arg("lang")                  = "en",
        py::arg("culture")               = "en-US",
        py::arg("height")                = 0,
        py::arg("fmt")                   = OutputFormat::PNG,
        py::arg("quality")               = 85,
        py::arg("shrink_to_fit")         = true);
}

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
    Renderer(int width, int dpi, std::string default_font, int default_font_size,
             std::vector<std::string> extra_fonts,
             size_t image_cache_max_bytes, int image_timeout_ms,
             size_t image_max_bytes, bool allow_http_images)
        : width_(width)
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

    py::object render(const std::string& html, const std::string& base_url,
                      int height, OutputFormat fmt, int quality) {
        // Stack-local — thread safe. Each call is fully independent.
        PyContainer container(fm_, ic_, width_);
        try {
            container.render(html, base_url, height);
        } catch (const std::exception& e) {
            throw RenderError(e.what());
        }
        cairo_surface_t* surf = container.surface();
        switch (fmt) {
            case OutputFormat::PNG: {
                auto buf = encode::to_png(surf);
                return py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
            }
            case OutputFormat::JPEG: {
                auto buf = encode::to_jpeg(surf, quality);
                return py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
            }
            case OutputFormat::RAW: {
                auto buf = encode::to_rgba(surf);
                RawResult r;
                r.data   = py::bytes(reinterpret_cast<const char*>(buf.data()), buf.size());
                r.width  = cairo_image_surface_get_width(surf);
                r.height = cairo_image_surface_get_height(surf);
                return py::cast(std::move(r));
            }
        }
        throw RenderError("Unknown output format");
    }

private:
    int         width_;
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
        .def(py::init<int,int,std::string,int,std::vector<std::string>,
                      size_t,int,size_t,bool>(),
             py::arg("width"),
             py::arg("dpi")                   = 96,
             py::arg("default_font")          = "Noto Sans",
             py::arg("default_font_size")     = 16,
             py::arg("extra_fonts")           = std::vector<std::string>{},
             py::arg("image_cache_max_bytes") = 64*1024*1024,
             py::arg("image_timeout_ms")      = 5000,
             py::arg("image_max_bytes")       = 10*1024*1024,
             py::arg("allow_http_images")     = true)
        .def("render", &Renderer::render,
             py::arg("html"),
             py::arg("base_url") = "",
             py::arg("height")   = 0,
             py::arg("fmt")      = OutputFormat::PNG,
             py::arg("quality")  = 85,
             py::call_guard<py::gil_scoped_release>());

    m.def("render",
        [](const std::string& html, int width, const std::string& base_url,
           int height, OutputFormat fmt, int quality) -> py::object {
            Renderer r(width,96,"Noto Sans",16,{},64*1024*1024,5000,10*1024*1024,true);
            return r.render(html, base_url, height, fmt, quality);
        },
        py::arg("html"), py::arg("width"),
        py::arg("base_url") = "", py::arg("height") = 0,
        py::arg("fmt")      = OutputFormat::PNG,
        py::arg("quality")  = 85);
}

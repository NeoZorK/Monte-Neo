#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include "metrics.cpp" // Simple inclusion for this small extension

namespace py = pybind11;

PYBIND11_MODULE(native_metrics, m) {
    m.doc() = "Native metrics calculation for Monte-Neo";

    py::class_<NativeTradeResult>(m, "NativeTradeResult")
        .def_readonly("entry_idx", &NativeTradeResult::entry_idx)
        .def_readonly("exit_idx", &NativeTradeResult::exit_idx)
        .def_readonly("entry_price", &NativeTradeResult::entry_price)
        .def_readonly("exit_price", &NativeTradeResult::exit_price)
        .def_readonly("direction", &NativeTradeResult::direction)
        .def_readonly("pnl", &NativeTradeResult::pnl)
        .def_readonly("pnl_pct", &NativeTradeResult::pnl_pct);

    m.def("extract_trades", &extract_trades_native, "Extract trades from prices and signals");
}

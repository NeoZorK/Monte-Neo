#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "include/metal_bridge.hpp"

namespace py = pybind11;

PYBIND11_MODULE(metal_engine, m) {
    m.doc() = "High-performance Metal backtest engine for Monte-Neo (Pure C++)";

    py::class_<monte_neo::BacktestResult>(m, "BacktestResult")
        .def_readonly("total_return", &monte_neo::BacktestResult::total_return)
        .def_readonly("trade_count", &monte_neo::BacktestResult::trade_count)
        .def_readonly("win_rate", &monte_neo::BacktestResult::win_rate)
        .def_readonly("max_drawdown", &monte_neo::BacktestResult::max_drawdown);

    py::class_<monte_neo::MetalBacktestBridge>(m, "MetalBacktestBridge")
        .def(py::init<>())
        .def("init", &monte_neo::MetalBacktestBridge::init)
        .def("run_backtest", &monte_neo::MetalBacktestBridge::run_backtest);
}

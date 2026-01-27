#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "include/metal_bridge.hpp"

namespace py = pybind11;

PYBIND11_MODULE(metal_engine, m) {
    m.doc() = "High-performance Metal backtest engine for Monte-Neo";

    py::class_<monte_neo::Candle>(m, "Candle")
        .def(py::init<float, float, float, float, float>(),
             py::arg("open"), py::arg("high"), py::arg("low"), py::arg("close"), py::arg("volume"))
        .def_readwrite("open", &monte_neo::Candle::open)
        .def_readwrite("high", &monte_neo::Candle::high)
        .def_readwrite("low", &monte_neo::Candle::low)
        .def_readwrite("close", &monte_neo::Candle::close)
        .def_readwrite("volume", &monte_neo::Candle::volume);

    py::class_<monte_neo::BacktestResult>(m, "BacktestResult")
        .def_readonly("total_return", &monte_neo::BacktestResult::total_return)
        .def_readonly("trade_count", &monte_neo::BacktestResult::trade_count)
        .def_readonly("win_rate", &monte_neo::BacktestResult::win_rate)
        .def_readonly("max_drawdown", &monte_neo::BacktestResult::max_drawdown);

    py::enum_<monte_neo::MetalBacktestBridge::Driver>(m, "Driver")
        .value("CPP", monte_neo::MetalBacktestBridge::Driver::CPP)
        .value("OBJC", monte_neo::MetalBacktestBridge::Driver::OBJC)
        .value("SWIFT", monte_neo::MetalBacktestBridge::Driver::SWIFT)
        .export_values();

    py::class_<monte_neo::MetalBacktestBridge>(m, "MetalBacktestBridge")
        .def(py::init<monte_neo::MetalBacktestBridge::Driver>(), py::arg("driver") = monte_neo::MetalBacktestBridge::Driver::CPP)
        .def("init", &monte_neo::MetalBacktestBridge::init)
        .def("run_backtest", &monte_neo::MetalBacktestBridge::run_backtest,
             py::arg("data"), py::arg("params"), py::arg("n_scenarios"))
        .def_property_readonly("driver", &monte_neo::MetalBacktestBridge::get_driver);
}

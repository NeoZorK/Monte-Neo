#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
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
        .def_readonly("max_drawdown", &monte_neo::BacktestResult::max_drawdown)
        .def_readonly("profit_factor", &monte_neo::BacktestResult::profit_factor)
        .def_readonly("sharpe_ratio", &monte_neo::BacktestResult::sharpe_ratio);

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
        .def("calculate_metrics", [](monte_neo::MetalBacktestBridge& self,
                                    py::array_t<float> close,
                                    py::array_t<float> high,
                                    py::array_t<float> low,
                                    py::array_t<int> signals,
                                    py::array_t<float> params,
                                    int n_pop, int n_scenarios, int n_time) {
            
            auto close_req = close.request();
            auto high_req = high.request();
            auto low_req = low.request();
            auto signals_req = signals.request();
            auto params_req = params.request();
            
            return self.calculate_metrics(
                (float*)close_req.ptr, (float*)high_req.ptr, (float*)low_req.ptr,
                (int*)signals_req.ptr, (float*)params_req.ptr,
                n_pop, n_scenarios, n_time,
                close_req.size, signals_req.size, params_req.size
            );
        }, py::arg("close_prices"), py::arg("high_prices"), py::arg("low_prices"), 
           py::arg("signals"), py::arg("params"), py::arg("n_pop"), 
           py::arg("n_scenarios"), py::arg("n_time"))
        .def("calculate_metrics_fast", [](monte_neo::MetalBacktestBridge& self,
                                         py::array_t<float> close,
                                         py::array_t<float> high,
                                         py::array_t<float> low,
                                         py::array_t<int> signals,
                                         py::array_t<float> params,
                                         int n_pop, int n_scenarios, int n_time) {
            
            auto close_req = close.request();
            auto high_req = high.request();
            auto low_req = low.request();
            auto signals_req = signals.request();
            auto params_req = params.request();
            
            auto results = self.calculate_metrics(
                (float*)close_req.ptr, (float*)high_req.ptr, (float*)low_req.ptr,
                (int*)signals_req.ptr, (float*)params_req.ptr,
                n_pop, n_scenarios, n_time,
                close_req.size, signals_req.size, params_req.size
            );
            
            auto result_arr = py::array_t<float>({(long)results.size(), (long)6});
            auto buf = result_arr.request();
            float* ptr = (float*)buf.ptr;
            
            for (size_t i = 0; i < results.size(); i++) {
                ptr[i * 6 + 0] = results[i].total_return;
                ptr[i * 6 + 1] = (float)results[i].trade_count;
                ptr[i * 6 + 2] = results[i].win_rate;
                ptr[i * 6 + 3] = results[i].max_drawdown;
                ptr[i * 6 + 4] = results[i].profit_factor;
                ptr[i * 6 + 5] = results[i].sharpe_ratio;
            }
            
            return result_arr;
        }, py::arg("close_prices"), py::arg("high_prices"), py::arg("low_prices"), 
           py::arg("signals"), py::arg("params"), py::arg("n_pop"), 
           py::arg("n_scenarios"), py::arg("n_time"))
        .def_property_readonly("driver", &monte_neo::MetalBacktestBridge::get_driver);
}

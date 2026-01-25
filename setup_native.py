from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "monte_neo.core.native_metrics",
        ["src/monte_neo/core/native/bindings.cpp"],
    ),
]

setup(
    name="monte-neo-native",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)

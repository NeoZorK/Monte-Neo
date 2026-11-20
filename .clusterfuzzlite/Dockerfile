# ClusterFuzzLite build image for the Python fuzz targets in this directory.
FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:21f6fab17ace4dc76e1c56de91ee95d3d03da021df94b41056ba036f6c6f55e9

COPY . $SRC/monte-neo
WORKDIR $SRC/monte-neo
COPY .clusterfuzzlite/build.sh $SRC/build.sh

# ClusterFuzzLite build image for the Python fuzz targets in this directory.
FROM gcr.io/oss-fuzz-base/base-builder-python

COPY . $SRC/monte-neo
WORKDIR $SRC/monte-neo
COPY .clusterfuzzlite/build.sh $SRC/build.sh

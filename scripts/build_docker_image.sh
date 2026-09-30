#!/usr/bin/env bash
# Build, smoke-test and push the verifier image for a release that is already on PyPI.
#   GH_TOKEN=... bash scripts/build_docker_image.sh v0.41.0
# The plain docker CLI is used on purpose: no third-party action to pin or trust.
set -euo pipefail

tag="${1:?usage: build_docker_image.sh vX.Y.Z}"
case "$tag" in v[0-9]*.[0-9]*.[0-9]*) ;; *) echo "not a release tag: $tag" >&2; exit 1 ;; esac
version="${tag#v}"
owner="${GITHUB_REPOSITORY_OWNER:-neozork}"
image="ghcr.io/${owner,,}/monte-neo-verify"

# The package index can lag a few minutes behind the release; the image builds from PyPI.
for i in 1 2 3 4 5 6 7 8 9 10; do
  if python3 -m pip download --no-deps --no-cache-dir -q -d "$(mktemp -d)" "monte-neo==$version"; then break; fi
  echo "waiting for PyPI ($i)"; sleep 30
done

docker build --build-arg "VERSION=$version" -t "$image:$version" -t "$image:latest" docker/verify
docker run --rm --network none --read-only --tmpfs /tmp "$image:latest" monte-neo --version

echo "${GH_TOKEN:?GH_TOKEN is required}" | docker login ghcr.io -u "${GITHUB_ACTOR:-neozork}" --password-stdin
docker push "$image:$version"
docker push "$image:latest"

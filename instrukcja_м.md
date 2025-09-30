#DEB
docker build -f docker/build-linux-deb.Dockerfile   --build-arg PYTHON_VERSION=3.11   --build-arg DEBIAN_RELEASE=bullseye   -t ecli-deb:py311-bullseye .

#RPM
docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .

#DEB
docker run --rm -v "$(pwd):/app" -w /app ecli-deb:py311-bullseye   bash -lc "./scripts/build-and-package-deb.sh"

#RPM
docker run --rm -v "$(pwd):/app" -w /app ecli-rpm:alma9 \
  bash -lc "./scripts/build-and-package-rpm.sh"

# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: packaging/nix/package.nix
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/

{
  pkgs,
  src ? ../..,
  version ? "0.2.0",
}:

let
  python = pkgs.python311;
  pythonEnv = python.withPackages (ps:
    [
      ps.aiohttp
      ps.attrs
      ps.cattrs
      ps.chardet
      ps.libcst
      ps.lsprotocol
      ps.packaging
      ps.pygments
      ps.pygls
      ps.pyperclip
      ps.python-dotenv
      ps.pyyaml
      ps.toml
      ps.typing-extensions
      ps.wcwidth
    ]);
in
pkgs.stdenvNoCC.mkDerivation {
  pname = "ecli-editor";
  inherit version src;

  nativeBuildInputs = [ pkgs.makeWrapper ];

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/lib/ecli" "$out/bin"
    cp -R . "$out/lib/ecli/source"
    rm -rf \
      "$out/lib/ecli/source/.git" \
      "$out/lib/ecli/source/build" \
      "$out/lib/ecli/source/dist" \
      "$out/lib/ecli/source/result"

    makeWrapper ${pythonEnv}/bin/python "$out/bin/ecli" \
      --add-flags "-m ecli" \
      --set PYTHONPATH "$out/lib/ecli/source/src"

    install -Dm644 "$out/lib/ecli/source/packaging/linux/fpm-common/ecli.desktop" \
      "$out/share/applications/ecli.desktop"
    install -Dm644 "$out/lib/ecli/source/src/ecli/assets/ecli.png" \
      "$out/share/icons/hicolor/256x256/apps/ecli.png"
    install -Dm644 "$out/lib/ecli/source/LICENSE" \
      "$out/share/licenses/ecli-editor/LICENSE"

    runHook postInstall
  '';

  meta = {
    description = "Terminal-first engineering operations workbench";
    homepage = "https://www.ecli.io";
    license = pkgs.lib.licenses.asl20;
    mainProgram = "ecli";
    platforms = [ "x86_64-linux" "aarch64-linux" ];
  };
}

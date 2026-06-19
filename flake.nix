# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: flake.nix
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/

{
  description = "ECLI terminal-first engineering operations workbench";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      packageFor = system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        pkgs.callPackage ./packaging/nix/package.nix {
          src = self;
          version = "0.2.3";
        };
    in
    {
      packages = forAllSystems (system: {
        default = packageFor system;
      });

      apps = forAllSystems (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/ecli";
        };
      });
    };
}

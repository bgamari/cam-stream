{ nixpkgs ? (import <nixpkgs> {}) }:

let
  pythonPackages = nixpkgs.python3Packages;
  camstream = pythonPackages.buildPythonApplication {
    name = "camstream";
    src = ./.;
    nativeBuildInputs = [ nixpkgs.gobjectIntrospection  ];
    propagatedBuildInputs = [
      nixpkgs.gst_all_1.gst-vaapi
      pythonPackages.gst-python
      nixpkgs.gst_all_1.gstreamer
      nixpkgs.gst_all_1.gst-plugins-good
      pythonPackages.aiohttp
      nixpkgs.libva
      nixpkgs.vaapiIntel
    ];
  };
in camstream

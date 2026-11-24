# Liz4270Terminal

Liz4270 is an open-source IBM 3270 CUT terminal. Its RP2350 firmware presents an IBM 3483-V to a controller over coax, drives DVI video over HDMI, and accepts a USB keyboard.

- [Firmware downloads and User's Guide PDFs](https://github.com/quaint-systems/Liz4270Terminal/releases)
- [Revision A board, schematics, and manufacturing files](hardware/board/README.md)
- [Enclosure source, printable parts, and assembly](hardware/case/README.md)
- [Display Station User's Guide source](docs/manual/manual.typ) and [USB keyboard map](docs/keymaps/us104.md)

## Build the firmware

Install Git, CMake 3.25 or newer, Ninja, Arm GNU Toolchain 15.3.Rel1 (`arm-none-eabi`), and picotool 2.3.1. From the repository root, run:

```sh
git submodule update --init firmware/pico-sdk firmware/Pico-PIO-USB
git -C firmware/pico-sdk submodule update --init lib/tinyusb
cd firmware
cmake --preset liz4270
cmake --build --preset liz4270
```

The firmware image is `firmware/build/liz4270/liz4270.uf2`. Put the board into BOOTSEL mode and copy this file to the RP2350 USB drive. See [versioning](docs/versions.md) for how builds are identified.

## Build the user guide

Install Typst 0.15.1 and a host C compiler. The manual build also uses Python, Pillow, and oec to check the keyboard descriptions. From the repository root, run:

```sh
git clone https://github.com/hanshuebner/oec-tcp.git ../oec-tcp
git -C ../oec-tcp checkout 3c5e812f6d2c0321e6c443dd4ed9590b7611c58a
python3 -m venv ../liz4270-docs-venv
. ../liz4270-docs-venv/bin/activate
python -m pip install -r ../oec-tcp/requirements.txt -r tools/sim/requirements.txt
PYTHONPATH=../oec-tcp python tools/manual/build.py
```

Draft PDFs for US Letter and A4 are written to `build/manual/`.

## License

- Firmware and software are licensed under [ISC](LICENSE).
- Hardware design files are licensed under [CERN-OHL-P v2](hardware/LICENSE).
- The user manual is licensed under [CC BY 4.0](docs/manual/LICENSE).
- Third-party licenses and credits are listed in [NOTICE](NOTICE).

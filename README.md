# Liz4270Terminal

Liz4270 is an open-source IBM 3270 CUT terminal. Its RP2350 firmware presents an IBM 3483-V to a controller over coax, drives DVI video over HDMI, and accepts a USB keyboard.

## What you need

- A Liz4270 Rev A board. The assembly order excludes the Murata 78602/8JC coax transformer (T1). Source it before ordering and fit it by hand. [Board design and bring-up](hardware/board/README.md) · [Ordering guide](hardware/board/jlc/README.md)
- A 3270 controller with a CUT coax port and a 93 Ω RG-62 cable with BNC connectors. The firmware was bench-tested on prototype hardware with oec and a Liz 4174 controller. Rev A and physical IBM 3174 bench results are still undocumented here. [oec](https://github.com/hanshuebner/oec-tcp) · [Liz 4174](https://github.com/quaint-systems/coax-tcp/tree/liz4174-v1/interface3)
- An HDMI monitor that accepts 640 × 480 at 60 Hz, a USB keyboard, and a 5 V USB-C power source. [USB keyboard map](docs/keymaps/us104.md)
- Firmware and the User’s Guide. The guide covers setup and updating over USB. [Downloads](https://github.com/quaint-systems/Liz4270Terminal/releases) · [Guide source](docs/manual/manual.typ)

For a printed enclosure, see the [printable parts and assembly instructions](hardware/case/README.md).

## Build the firmware

Install Git, CMake 3.25 or newer, Ninja, Arm GNU Toolchain 15.3.Rel1 (`arm-none-eabi`), and picotool 2.3.1. Use a Git checkout to fetch the firmware submodules.

```sh
git clone https://github.com/quaint-systems/Liz4270Terminal.git
cd Liz4270Terminal
git submodule update --init firmware/pico-sdk firmware/Pico-PIO-USB
git -C firmware/pico-sdk submodule update --init lib/tinyusb
cd firmware
cmake --preset liz4270
cmake --build --preset liz4270
```

The firmware image is `firmware/build/liz4270/liz4270.uf2`. Put the board into BOOTSEL mode and copy this file to the RP2350 USB drive. See [versioning](docs/versions.md) for how builds are identified.

## Build the user guide

Install Typst 0.15.1, Python 3.11 or newer, and a host C compiler. The manual build uses Pillow and oec to check the keyboard descriptions. Run these commands from the repository root.

```sh
git clone https://github.com/hanshuebner/oec-tcp.git ../oec-tcp
git -C ../oec-tcp checkout 3c5e812f6d2c0321e6c443dd4ed9590b7611c58a
python3 -m venv ../liz4270-docs-venv
. ../liz4270-docs-venv/bin/activate
python -m pip install -r ../oec-tcp/requirements.txt -r tools/sim/requirements.txt
PYTHONPATH=../oec-tcp python tools/manual/build.py
```

Draft PDFs for US Letter and A4 are written to `build/manual/`.

## Run the tests

See the [simulator test setup](tools/sim/README.md). To run the user guide tests as well, use the manual build environment above and run `PYTHONPATH=../oec-tcp python -m unittest discover -s tools/manual` from the repository root.

## License

- Firmware and software are licensed under [ISC](LICENSE).
- Hardware design files are licensed under [CERN-OHL-P v2](hardware/LICENSE).
- The user manual is licensed under [CC BY 4.0](docs/manual/LICENSE).
- Third-party licenses and credits are listed in [NOTICE](NOTICE).

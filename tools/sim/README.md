# Firmware maintenance tools

These tools build the terminal core on the host for the user guide, keymap documentation, and regression tests. They also regenerate the firmware's font and About pages.

From the repository root, install Pillow and run the retained firmware tests:

```sh
python3 -m pip install -r tools/sim/requirements.txt
python3 -m unittest discover -s tools/sim
```

| Tool | Use |
| --- | --- |
| `keymap_doc.py` | Regenerate the keymap reference in `docs/keymaps/`. |
| `bake_font.py` | Regenerate the embedded font from the upstream 3270font release. The script documents its inputs. |
| `subset_font.py` | Regenerate the 3270font subset used in the user guide and enclosure. |
| `bake_about.py` | Regenerate the firmware's About pages from the license texts and credits. |
| `about_audit.py` | Check a built firmware image with `python3 tools/sim/about_audit.py firmware/build/liz4270`. |

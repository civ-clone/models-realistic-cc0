# models-realistic-cc0

Realistic units for [civ.one](https://civ.one)'s 3D map, under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

Most of these I made for civ.one in [Meshy](https://www.meshy.ai): from each text prompt, Meshy made an image with
Google's Nano Banana, then a model from the image. The rest are Meshy community models and a molotov from OpenGameArt,
all CC0. All but the molotov are made with AI, and each file says so. The set draws 20 unit
types: Settlers, Warriors, Knights, Explorer, Sail, Crusaders, Musketmen, Riflemen, Cavalry, Dragoons, Alpine Troops,
Partisans, Spy, Marines, Engineers, Bomber, Stealth Bomber, Frigate, Ironclad and Transport.

[models-realistic-by](https://github.com/civ-clone/models-realistic-by) draws the later units made from CC BY models.
Some of these types are drawn by [models-cimpletoon](https://github.com/civ-clone/models-cimpletoon) too. civ.one's 3D
map draws each type from one set.

## What's here

- **`models/*.glb`:** one glTF binary for each model, facing `+z`, with one baked colour texture (JPEG, 512 px for
  people and 1024 px for the rest), and a PNG at half that size for its owner's colour; the Partisans have a second
  JPEG, for their molotov. Each was cut down to its budget where it was over
  (2,000 triangles for a person, 3,000 for a rider or the Settlers' group, 2,500 for an aircraft, 3,500 for a ship),
  and its colour baked into the texture. Each carries its credit in `asset.copyright`, and its credit, licence and
  what was done to it in `asset.extras`.
- **Standing and floating:** a model stands on its origin, centred across and along, at its real size in metres. A
  ship floats with its origin at the waterline, its draught under it (`extent.draught`).
- **The owner's colour:** each model takes its owner's colour on one part, as models-0ad and models-cimpletoon do:
  - **people and riders:** their coat, jacket or other main garment, the Cavalry's saddle cloth, the Knight's caparison,
    the Crusader's surcoat, caparison and shield, and the Settlers' load;
  - **sailing ships:** their sails;
  - **steamships:** a band along the hull;
  - **aircraft:** their wingtips.

  Those faces are a primitive of their own, drawn with a material that says `extras.playerColour` and a PNG at half
  the texture's size. Where the owner's colour goes, the PNG is grey, shaded as the texture is there but lifted to a
  light grey, with its alpha 0, and civ.one draws it as `rgb × mix(owner, white, alpha)`. Where a rule goes texel by
  texel (`cut`), as for bands and wingtips, and the colour ends partway across a face, the rest of that face is the
  texture's colour, solid, at that half size. The rest of each model is drawn from its JPEG as before. Where the
  colour goes is each model's `owner` rule in `roster.json`.
- **Not yet:** most people stand in an A-pose, ready to rig, but nothing is rigged.
- **`manifest.json`:** the set, as civ.one's library describes a set of models:
  - its licence, with the credit to show wherever it's used (`licence.attribution`), and its credits;
  - the scale it's drawn at, and any model's own where it isn't the set's;
  - each model's file and its SHA-256, its triangles, how far it reaches (`extent`, in metres), where it's from and
    what was done to it;
  - which unit types each model draws (`names.unit`, by the engine's names for them).
- **`roster.json`:** what's built, and how:
  - each source: its page, author and licence, where its file came from and that file's SHA-256, and, for the ones I
    made, the prompt;
  - each model: the unit types it draws, its source, how it's cut (part by part, or wrapped in one new surface), how
    it's turned and sized, how deep a ship floats, the prop put in (the Partisan's molotov), where its owner's colour
    goes, its budget, and its scale where it isn't the set's.

  The set's scale draws a 1.8 m person as tall as the other sets' people, 0.168 squares. The 3D map draws units
  bigger than life, so the rest have scales of their own, close to models-cimpletoon's sizes: riders 0.21 to 0.22
  squares long, aircraft about 0.24 across their wings, ships 0.30 to 0.38 long.
- **`tools/`:** the build (`build.py`, with the Blender scripts it runs in `tools/blender/`) and the check CI runs
  (`check.py`).
- **`CREDITS.md`:** everyone whose work is here.

## Building them again

`check.py` needs only Python 3.10 or later:

```bash
python3 -I tools/check.py
```

Building the models again needs [Blender](https://www.blender.org) (4.5 was used) and the original files, which
`roster.json` names by SHA-256. Put them in one folder, then:

```bash
python3 -I tools/build.py --blender /path/to/blender --originals /path/to/originals
```

Name models to build only those. Blender runs with its factory settings and with scripts in files turned off, and
reads the originals only as data. Without `--originals`, `build.py` only writes each model's `asset.copyright` and
`asset.extras`, the manifest and the credits.

The owner's colour goes on last, and `owner.py` won't colour a file that has it already, so a changed `owner`
rule takes effect only when its model is built again from its original. `check.py` checks each rule's form, not
that the file follows it.

The originals:
- **Mine:** generated in my Meshy account, and too big to keep here (up to 140 MB each). I've kept them.
- **Meshy community models:** each post's GLB download, which needs a Meshy account.
- **The molotov:** [`Molotov.zip`](https://opengameart.org/sites/default/files/Molotov.zip) from its OpenGameArt page.

With Blender 4.5 on the Mac they were made on, a model built again comes out the same file, or differs only in a name
inside it. Another version of Blender, or another platform, may cut or bake it a little differently.

## Licence

- **The models and the manifest** (`models/`, `manifest.json`, `CREDITS.md`) are under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): free to use for anything, with no conditions.
- **The tools, the roster and the files about the repository** (`tools/`, `roster.json`, this README and the rest)
  are mine, under the MIT licence.

See [LICENSE.md](LICENSE.md).

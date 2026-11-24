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
- **Poses:** the Riflemen, Explorer, Spy, Partisans and Marines, generated standing in an A-pose, stand with their
  arms at their sides. The Warriors, Musketmen, Alpine Troops, Engineers and the Settlers stood naturally already, and
  the riders sit their horses.

  A figure is posed by `tools/blender/stance.py`, as its `stance` in `roster.json` says: a skeleton fitted to it where
  it stands in the file, the way each bone should point, and any pieces that move whole (the Partisan's molotov, the
  Riflemen's and Marines' slung rifles). Blender weights each point to the bones near it, and the file's points and
  normals are moved; nothing else in it changes but a mark on the mesh (`extras.posed`).
- **Rigged and animated:** the Partisans, so far. `models/rigged/partisan.glb` is the model as it stands, bound to the
  skeleton it was posed with, with four clips: `idle` (3 s, breathing, looking about and shifting his weight) and
  `move` (a 1 s stride in place), which loop, and `fight` (1.5 s: he steps into the throw and the molotov leaves his
  hand at 0.5 s, back in it by the end) and `die` (1.5 s: the shot throws him back, his knees give, his left foot
  slides out and kicks up while his right stays where he stood, and he lands on his back, his head and arms after him,
  his right leg flopping out straight and his left knee falling last), which play once. The map draws what flies: the
  manifest gives each clip's shots (`rigged.shots`), each the time it leaves and the joint it leaves from (here the
  molotov's, `prop`, whose origin is the bottle's middle as he stands).

  A figure is rigged by `tools/blender/rig.py`, as its `rig` in `roster.json` says. Each point keeps the four biggest
  of the weights it was posed with (a leg's fading out above the hip, so a step doesn't drag the chest). Each clip is
  made from key poses, in the stance's terms (which way each bone points, and how it's twisted), with the whole
  figure turned where it falls, the hips moved and the feet planted (the legs bent to keep them where they're put).
  Between keys the bones turn on smooth curves; a key can be met at rest, at speed, hit at speed (a body reaching the
  ground) or snapped to (a body a shot strikes), and some bones can meet it after the rest (a head and arms landing
  after the body), or lag through the whole clip, so a movement passes from the body out to the limbs. Every frame is
  stood on the ground by its lowest point, and played in place: the map moves units from square to square itself. The
  file has a root node, `skeleton`, holding a joint for each bone (named as the stance's, which three.js reads
  without the dot: `hand.R` is `handR`), and the molotov's, `prop`, a child of his right hand's. Each clip keys every
  joint's turn, the root's place, and the molotov's size (it's 0 from just after the throw until it grows back in his
  hand). A clip that plays once starts as the model stands (its feet can be planted there from the start, so they
  don't slide as it begins), and a loop ends where it starts.
- **`manifest.json`:** the set, as civ.one's library describes a set of models:
  - its licence, with the credit to show wherever it's used (`licence.attribution`), and its credits;
  - the scale it's drawn at, and any model's own where it isn't the set's;
  - each model's file and its SHA-256, its triangles, how far it reaches (`extent`, in metres), where it's from and
    what was done to it;
  - a rigged model's rigged file, its SHA-256, its clips by role, and where its shots leave from, by clip (`rigged`);
  - which unit types each model draws (`names.unit`, by the engine's names for them).
- **`roster.json`:** what's built, and how:
  - each source: its page, author and licence, where its file came from and that file's SHA-256, and, for the ones I
    made, the prompt;
  - each model: the unit types it draws, its source, how it's cut (part by part, or wrapped in one new surface), how
    it's turned and sized, how deep a ship floats, the prop put in (the Partisan's molotov), where its owner's colour
    goes, how a figure is posed, how it's rigged and its clips, its budget, and its scale where it isn't the set's.

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

The owner's colour goes on next to last, and the pose last. `owner.py` won't colour a file that has it already, and
`stance.py` poses a figure from where it stands, so a changed `owner` rule or `stance` takes effect only when its
model is built again from its original. `check.py` checks each rule's form, not that the file follows it.

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

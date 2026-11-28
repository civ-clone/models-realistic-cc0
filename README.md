# models-realistic-cc0

Realistic units for [civ.one](https://civ.one)'s 3D map, under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

Most of these I made for civ.one in [Meshy](https://www.meshy.ai): from each text prompt, Meshy made an image with
Google's Nano Banana, then a model from the image. The rest are a Meshy community model (the Frigate), a molotov from
OpenGameArt and the Cavalry's sabre from Poly Haven, all CC0. All but the molotov and the sabre are made with AI, and
each file says so. The set draws 20 unit types: Settlers, Warriors, Knights, Explorer, Sail, Crusaders, Musketmen,
Riflemen, Cavalry, Dragoons, Alpine Troops, Partisans, Spy, Marines, Engineers, Bomber, Stealth Bomber, Frigate,
Ironclad and Transport.

[models-realistic-by](https://github.com/civ-clone/models-realistic-by) draws the later units made from CC BY models.
Some of these types are drawn by [models-cimpletoon](https://github.com/civ-clone/models-cimpletoon) too. civ.one's 3D
map draws each type from one set.

## What's here

- **`models/*.glb`:** one glTF binary for each model, facing `+z`, with one baked colour texture (JPEG, 512 px for
  people and 1024 px for the rest), and a PNG at half that size for its owner's colour; the Partisans, Riflemen,
  Marines, Musketmen, Alpine Troops, Cavalry and Dragoons have a second JPEG (256 px), for their molotov, rifle, musket,
  sabre or carbine. Each was cut
  down to its budget where it was over (2,000 triangles for a person, 3,000 for a rider or the Settlers' group, 2,500
  for an aircraft, 3,500 for a ship), and its colour baked into the texture. Each carries its credit in
  `asset.copyright`, and its credit, licence and what was done to it in `asset.extras`.
- **Standing and floating:** a model stands on its origin, centred across and along, at its real size in metres. A
  ship floats with its origin at the waterline, its draught under it (`extent.draught`).
- **The owner's colour:** each model takes its owner's colour on one part, as models-0ad and models-cimpletoon do:
  - **people and riders:** their coat, jacket or other main garment, the Cavalry's and Dragoons' saddle cloths, the
    Knight's caparison, the Crusader's surcoat, caparison and shield, and the Settlers' load;
  - **sailing ships:** their sails;
  - **steamships:** a band along the hull;
  - **aircraft:** their wingtips.

  Those faces are a primitive of their own, drawn with a material that says `extras.playerColour` and a PNG at half
  the texture's size. Where the owner's colour goes, the PNG is grey, shaded as the texture is there but lifted to a
  light grey, with its alpha 0, and civ.one draws it as `rgb × mix(owner, white, alpha)`. Where a rule goes texel by
  texel (`cut`), as for bands and wingtips, and the colour ends partway across a face, the rest of that face is the
  texture's colour, solid, at that half size. The rest of each model is drawn from its JPEG as before. Where the
  colour goes is each model's `owner` rule in `roster.json`.
- **Poses:** the Riflemen, Musketmen, Explorer, Spy, Partisans and Marines, generated standing in an A-pose, stand with
  their arms at their sides. The Riflemen and Musketmen hold their rifles or muskets upright by their right feet (order
  arms), and the Marines hold theirs by its grip, muzzle down, a carbine too short to ground at the hand. The Warriors
  and Engineers stand as they were made, their arms a little out from their sides: the Warriors with a club in the right
  hand and a round shield on the left arm, under their cloaks, and the Engineers with a rolled drawing in the left hand.
  The Alpine Troops, generated again without ski poles, stand with their arms at their sides and their rifles at the
  trail in their right hands, muzzle forward and a little up, the hand along it (grounded by the foot, its muzzle would
  run up into their thick sleeves); their skis are short, about 0.75 m, all ahead of the heel, as Meshy made them. The
  Settlers stood naturally already, and the riders sit their horses. The Cavalry trooper was generated again with his
  right arm stretched out, clear of everything: made with both hands on the reins, his right fist was one surface with
  the reins, the saddle and his left fist, so it couldn't leave them. Meshy stretched out his left arm instead, so he's
  mirrored (`stage.mirror`), which leaves his empty scabbard on his right hip. His own sabre's hilt is dropped, and he
  holds Poly Haven's sabre in his right hand at the carry, upright, its back by his right shoulder, his hand on his
  thigh. The dragoon was generated again too, his horse standing (the Meshy community model I had galloped, its
  forelegs tucked up) and both his arms held straight out, clear of the reins and saddle; they're brought down to his
  sides, his left hand forward by the reins and his right fist round the small of his carbine's stock, at the advance:
  its butt on his right thigh, upright, leaning a little forward and out. His carbine is the Musketmen's musket, its
  bayonet fixed, scaled down whole to 1.15 m (so it's slimmer too); his sabre stays sheathed at his left hip.

  A figure is posed by `tools/blender/stance.py`, as its `stance` in `roster.json` says: a skeleton fitted to it where
  it stands in the file, the way each bone should point, any pieces that move whole (the Partisan's molotov, the rifles
  and muskets in their hands, the Warriors' club and shield, the Engineers' drawing, the Cavalry's sabre, the Dragoons'
  carbine, and both riders' reins, with their horses' necks), and how a hand's fingers curl, where it's made open
  (`fingers`: the Cavalry's right hand, round his sabre's grip, and the Dragoons', round his carbine's stock;
  models-realistic-by's Fanatics' too). The Riflemen's rifle was
  split off the back it was generated slung across (`split`); the Marines' and the Alpine Troops' rifles and the
  Musketmen's musket (the Dragoons' carbine too) were generated apart from them. The Explorer's coil of rope, which
  the cut to 2,000 triangles drew as jagged slivers, was dropped before the cut (a `split` that only drops). Blender
  weights each point to the bones near it, and the file's points and normals are moved; nothing else in it changes but
  a mark on the mesh (`extras.posed`).
- **Rigged and animated:** the Partisans, Riflemen, Marines, Musketmen, Alpine Troops, Explorer, Spy, Warriors,
  Engineers, Cavalry and Dragoons, so far.
  Each `models/rigged/<model>.glb` is the model as it stands, bound to the skeleton it was posed with, with its clips.
  The Partisans': `idle` (3 s, breathing, looking about and shifting his weight) and `move` (a 1 s stride in place),
  which loop, and `fight` (1.5 s: he steps into the throw and the molotov leaves his hand at 0.5 s, back in it by the
  end) and `die` (1.5 s: the shot throws him back, his knees give, his left foot slides out and kicks up while his right
  stays where he stood, and he lands on his back, his head and arms after him, his right leg flopping out straight and
  his left knee falling last), which play once. The map draws what flies: the manifest gives each clip's shots
  (`rigged.shots`), each the time it leaves and the joint it leaves from (here the molotov's, `prop`, whose origin is
  the bottle's middle as he stands).

  The Riflemen, Marines and Musketmen keep their weapons in their hands throughout. In `idle` they shift their weight
  as the Partisans do, the weapon held as they stand. In `move` the Riflemen and Musketmen carry theirs across the
  chest at port arms, and the Marines at the low ready (the butt in the shoulder, the muzzle down ahead), both hands
  on it. In `fight` they bring it to the shoulder, the left hand on the fore-end and the head down to the stock (the
  Marines' left hand comes up to it as it reaches the shoulder, and leaves it before it's lowered). The Riflemen and
  Musketmen fire once at 0.54 s, and the Marines a three-round burst at 0.5, 0.667 and 0.833 s, each shot leaving as
  he holds still (for a frame, so the map finds the muzzle where it fired) and then kicking the muzzle up. Then they
  bring it back to where they stand. They die as the Partisans do, the weapon lying beside them. Their shots are
  bullets (`"kind": "bullet"`), leaving from the weapon's `muzzle`, a node at the middle of its top end (a musket's is
  its bayonet's tip). A rig can instead put a `muzzle` on a bone, for a weapon that's part of the figure rather than a
  prop of its own (models-realistic-by's Paratroopers' slung SMG); none here does.

  The Alpine Troops keep their rifles in their hands throughout too. Their `idle` is the Riflemen's, the rifle at the
  trail. Their `move` is a ski glide (1.2 s): both skis stay on the snow, each sliding ahead of where it stands and
  back as the other does the opposite, his hips dropping as his legs part, leaning into it, his arms swinging against
  his legs (a ski behind him lifts its tail a few centimetres). Their `fight` is the Riflemen's from the trail: he
  raises the rifle on a slant to his shoulder, fires once at 0.54 s, and lowers it to the trail again. In `die` he's
  hit as the Riflemen are, then falls sideways onto his left side (on his back, his thick rucksack would hold him off
  the ground, legs and skis in the air): his skis lie on their edges on the ground, his right leg forward of his left,
  his rucksack behind him and his rifle in front of him.

  The Explorer, the Spy and the Engineers, who don't fight, have the Partisans' `idle`, `move` and `die`, the Engineers'
  arms swinging from where they hold them. Lying dead, the Engineers' drawing lies beside them, and their heads are
  brought forward so their hard hats' brims don't hold them off the ground.

  The Warriors have the Partisans' `idle`, `move` and `die` too, their arms swinging from where they hold them (the
  shield arm half as far, the shield clear of the legs), and a `fight` of their own (1.5 s): an overhand blow with the
  club, from the Partisans' throw. He raises it behind him and over his head, its head behind him, and brings it over
  his head and down at an enemy ahead of him, his shield arm brought forward to guard him; it lands at 0.5 s (`strike`),
  its head about 1.5 m up and 1.3 m ahead of his hips, and carries on down. His back foot stays where it is as he steps
  into it. In `die` he lands a little short of flat, as his cloak's thick folds would otherwise meet the ground first,
  then settles flat, and lies with his club on the ground beside him and his shield nearly flat beside his head.

  The Cavalry are rigged horse and rider together: one skin, the horse's skeleton and the man's, his hips riding on its
  back. In `idle` (3 s) the horse lowers and raises its head and swishes its tail as he looks about. In `move` it trots
  (1 s), its legs in diagonal pairs half a stride apart, each reaching forward, taking his weight, pushing off behind
  and folding as it swings through. In `fight` (1.5 s) he raises his sabre over his right shoulder and slashes down
  and forward at his right front, the blow landing at 0.55 s (`strike`), as his horse throws its head up, then follows
  through and comes back to the carry. In `die` the horse throws its head up, its forelegs buckle, and it goes over onto
  its right side, its rider with it, thrown down at its back with his right leg under it.

  The Dragoons are rigged as the Cavalry are, and their horses idle, trot and fall as the Cavalry's do, their carbines
  kept at the advance (and in his hand as he falls). In `fight` (1.5 s) he lifts his carbine from his thigh and brings
  it to his right shoulder, its muzzle coming down ahead of him as he turns to his right, and aims it ahead and a little
  down, about 8° to the right of his horse's head (clear of it by about 17 cm), his left hand leaving the reins for its
  fore-end and his head bowed towards it. He fires once at 0.54 s, holding still for a frame and then kicking the
  muzzle up, as his horse throws its head up; he holds it aimed, and brings it back down to his thigh. His shot is a
  bullet (`"kind": "bullet"`), leaving from his carbine's `muzzle`: the tip of its bayonet, as the Musketmen's is.

  A figure is rigged by `tools/blender/rig.py`, as its `rig` in `roster.json` says. Each point keeps the four biggest of
  the weights it was posed with (a leg's fading out above the hip, so a step doesn't drag the chest). Each clip is made
  from key poses, in the stance's terms (which way each bone points, and how it's twisted), with the whole figure turned
  where it falls, the hips moved and the feet planted (the legs bent to keep them where they're put). Between keys the
  bones turn on smooth curves; a key can be met at rest, at speed, hit at speed (a body reaching the ground) or snapped
  to (a body a shot strikes), and some bones can meet it after the rest (a head and arms landing after the body), or lag
  through the whole clip, so a movement passes from the body out to the limbs. Every frame is stood on the ground by its
  lowest point, and played in place: the map moves units from square to square itself. The file has a root node,
  `skeleton`, holding a joint for each bone (named as the stance's, which three.js reads without the dot: `hand.R` is
  `handR`; a rider's horse's are named `mount_`, and its hips are the root), and, for a figure whose held piece is split
  off to move on its own (the Partisans', Riflemen's, Musketmen's, Marines', Alpine Troops' and Dragoons'), the piece's,
  `prop`, a child of his right hand's. Each clip keys every joint's turn, the root's place, and any prop's size (the
  molotov's is 0 from just after the throw until it grows back in his hand). A key can also hold the prop as it says
  rather than as the hand does: where it points, which way its back faces and where its butt goes, carried by the
  chest as it turns. The hand that holds it, and the other hand, are then bent to reach it, each lying along it as its
  forearm carries it at the keys, and every clip keys the prop's place on the hand as well. As a hold eases on or off,
  the elbow's bend is eased with it, the hand sliding along the prop to keep it so; a prop whose `slides` is false
  (the Marine's rifle, held by its pistol grip) moves with the hand instead. A prop whose `grounded` is false (as
  these weapons' are) is left out of standing the figure on the ground, so it can leave the ground, or dip into it, as
  he moves. A clip that plays once starts as the model stands (its feet can be planted there from the start, so they
  don't slide as it begins), and a loop ends where it starts.
- **`manifest.json`:** the set, as civ.one's library describes a set of models:
  - its licence, with the credit to show wherever it's used (`licence.attribution`), and its credits;
  - the scale it's drawn at, and any model's own where it isn't the set's;
  - each model's file and its SHA-256, its triangles, how far it reaches (`extent`, in metres), where it's from and
    what was done to it;
  - a rigged model's rigged file, its SHA-256, its clips by role, and its shots by clip: when each leaves, the joint
    or node it leaves from, and what flies, where the roster says (`kind`; a bottle without one); and, for a fight
    with no shots, when its blow lands (`strikes`, by clip: the Warriors' and the Cavalry's) (`rigged`);
  - which unit types each model draws (`names.unit`, by the engine's names for them).
- **`roster.json`:** what's built, and how:
  - each source: its page, author and licence, where its file came from and that file's SHA-256, and, for the ones I
    made, the prompt;
  - each model: the unit types it draws, its source, a piece its original fuses to the figure and how it's split off
    (`split`: the Rifleman's rifle, made whole from its mirror image) or what's dropped before it's cut (the Explorer's
    rope), how it's cut (part by part, or wrapped in one new surface, which can be closed over a split piece's slits),
    how it's turned (or mirrored) and sized, how deep a ship floats, the prop put in (the Partisan's molotov, a weapon generated
    apart, or the piece split off), turned to be held as the figure is posed, where its owner's colour goes, how a
    figure is posed, how it's rigged and its clips, its budget, and its scale where it isn't the set's.

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
- **The Meshy community model:** its post's GLB download, which needs a Meshy account.
- **The molotov:** [`Molotov.zip`](https://opengameart.org/sites/default/files/Molotov.zip) from its OpenGameArt page.
- **The sabre:** Poly Haven's [Wooden Handle Saber](https://polyhaven.com/a/wooden_handle_saber), as Summer Engine's
  [asset store](https://www.summerengine.com/asset-store/library-sabre) has it, in one GLB (its node and textures are
  named for it, and it has Poly Haven's 4,031 triangles).

With Blender 4.5 on the Mac they were made on, a model built again comes out the same file, or differs only in a name
inside it. Another version of Blender, or another platform, may cut or bake it a little differently.

## Licence

- **The models and the manifest** (`models/`, `manifest.json`, `CREDITS.md`) are under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): free to use for anything, with no conditions.
- **The tools, the roster and the files about the repository** (`tools/`, `roster.json`, this README and the rest)
  are mine, under the MIT licence.

See [LICENSE.md](LICENSE.md).

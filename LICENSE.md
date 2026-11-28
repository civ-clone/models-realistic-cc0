# Licence

This repository holds two kinds of work under two licences.

## The models: CC0 1.0

`models/`, `manifest.json` and `CREDITS.md` are dedicated to the public domain under the Creative Commons CC0 1.0
Universal Public Domain Dedication: https://creativecommons.org/publicdomain/zero/1.0/

They come from four kinds of source, all CC0:
- **Made for civ.one:** I generated these in [Meshy](https://www.meshy.ai) on a paid plan: from each text prompt,
  Meshy made an image with Google's Nano Banana, then a model from the image. Meshy's terms (section 3.2) make what I
  generate on a paid plan mine, and I dedicate them to the public domain. They're made with AI.
- **A Meshy community model:** the Frigate is a post on Meshy's community, CC0 under section 3.3 of Meshy's Terms of
  Service (as updated on 19 September 2026), as the post's own record says. It's made with AI.
- **Lowpoly Molotov:** by [Lucian Pavel](https://opengameart.org/content/lowpoly-molotov) on OpenGameArt, CC0.
- **Wooden Handle Saber:** by Ulan Cabanilla on [Poly Haven](https://polyhaven.com/a/wooden_handle_saber), CC0, for
  the Cavalry.

I made these changes, and dedicate them to the public domain under CC0 1.0 too:
- **Fewer triangles:** each is cut down, part by part or wrapped in one new surface, to no more than `roster.json`
  says, and its colour baked into one texture.
- **Placing:** each is turned to face `+z` (the Cavalry mirrored first), sized in metres, and stood on the ground or
  floated at its waterline.
- **Assembly:** the molotov, the sabre and the weapons I generated apart are put in hands (the Dragoons' carbine is
  the Musketmen's musket, scaled down).
- **The owner's colour:** on each model, the faces that take their owner's colour, as `roster.json` says, are a
  primitive of their own, with a PNG of their own whose alpha is 0 where the colour goes.
- **Poses and clips:** the people and riders are posed, and some rigged with clips, as the README says.
- **Format:** each is a glTF binary with JPEG textures (and that PNG), carrying its credit in `asset.copyright` and
  `asset.extras`.

You may use, change and share them, for any purpose, with no conditions. A credit, though none is needed:

> Models generated for civ.one by dom111 with Meshy, a Meshy community model, Lucian Pavel's Lowpoly Molotov and Ulan
> Cabanilla's Wooden Handle Saber (Poly Haven), all CC0 1.0: reduced, rebaked, given their owner's colour and converted
> by dom111. All but the molotov and the sabre are made with AI.
> Credits: https://github.com/civ-clone/models-realistic-cc0/blob/main/CREDITS.md

[CREDITS.md](CREDITS.md) lists every source.

CC0 covers only the rights that I, and the other sources' authors, hold. It grants nothing in anyone else's designs or
trademarks, such as those of the real aircraft and ships some of these depict.

## The tools: MIT

`tools/`, `roster.json` (what's built, and how), and the files about the repository (`README.md`, `LICENSE.md`,
`package.json`, `.github/`, `.gitignore`, `.gitattributes`) are mine:

MIT License

Copyright (c) 2026 dom111

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

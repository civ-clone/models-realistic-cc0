# Licence

This repository holds two kinds of work under two licences.

## The models: CC0 1.0

`models/`, `manifest.json` and `CREDITS.md` are dedicated to the public domain under the Creative Commons CC0 1.0
Universal Public Domain Dedication: https://creativecommons.org/publicdomain/zero/1.0/

They come from three kinds of source, all CC0:
- **Made for civ.one:** I generated these with [Meshy](https://www.meshy.ai) from text prompts, on a paid plan, which
  makes them mine under Meshy's terms, and I dedicate them to the public domain. They're made with AI.
- **Meshy community models:** the Crusader, Musketman, Dragoon and Frigate are posts on Meshy's community, CC0 under
  Meshy's Terms of Service. They're made with AI.
- **Lowpoly Molotov:** by [lucian-pavel](https://opengameart.org/content/lowpoly-molotov) on OpenGameArt, CC0.

I made these changes, and dedicate them to the public domain under CC0 1.0 too:
- **Fewer triangles:** each is cut down, part by part or wrapped in one new surface, to no more than `roster.json`
  says, and its colour baked into one texture.
- **Placing:** each is turned to face `+z`, sized in metres, and stood on the ground or floated at its waterline.
- **Assembly:** the molotov is put in the Partisan's hand.
- **Format:** each is a glTF binary with a JPEG texture, carrying its credit in `asset.extras`.

You may use, change and share them, for any purpose, with no conditions. A credit, though none is needed:

> Models generated for civ.one by dom111 with Meshy, Meshy community models and lucian-pavel's Lowpoly Molotov, all
> CC0 1.0: reduced, rebaked and converted by dom111. Some are made with AI.

[CREDITS.md](CREDITS.md) lists every source.

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

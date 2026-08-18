# Mixar Figma implementation

Pixel-faithful implementation of the supplied Figma frame (`1:2`). The exact
Figma vector export is stored locally so none of the page media relies on
temporary Figma asset URLs.

## Run locally

```sh
python3 -m http.server 4173
```

Then open <http://localhost:4173>.

The reference canvas is 1728 × 11088 px. It renders at that exact size on a
1728 px viewport and scales proportionally on narrower displays.

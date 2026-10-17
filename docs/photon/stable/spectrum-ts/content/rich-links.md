#### Rich links

Source: https://photon.codes/docs/spectrum-ts/content/rich-links.md
Documentation version: Stable

Use `richlink()` to build `Richlink` content from a URL. Spectrum carries only the URL. It does not fetch Open Graph metadata.

```ts
import { richlink } from "spectrum-ts";

await space.send(richlink("https://example.com/article"));
```

Each provider asks its native client to render or unfurl the URL. Platforms without rich-link support fall back to plain text.



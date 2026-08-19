/* Render site/tools/og.svg to site/og.png (1200x630) for link previews.
 *
 *   npm i -D @resvg/resvg-js && node site/tools/make-og.mjs
 *
 * The PNG is committed, so you only need this when og.svg changes. Crawlers do
 * not accept SVG for og:image, which is the only reason a raster step exists in
 * an otherwise build-free site.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Resvg } from "@resvg/resvg-js";

const here = dirname(fileURLToPath(import.meta.url));
const svg = readFileSync(join(here, "og.svg"), "utf8");

const resvg = new Resvg(svg, {
  fitTo: { mode: "width", value: 1200 },
  font: { loadSystemFonts: true, defaultFontFamily: "Helvetica" },
});

const out = join(here, "..", "og.png");
writeFileSync(out, resvg.render().asPng());
console.log("wrote", out);

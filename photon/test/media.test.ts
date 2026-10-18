// The supported input is a photo; HEIC and PNG become JPEG for registration.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { ffmpegExecutable, isHeif, Media } from "../src/media.js";

const has = (bin: string) => {
  try {
    execFileSync("which", [bin], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
};

test("a HEIC photo becomes JPEG", { skip: !(has("sips") && has(ffmpegExecutable)) && "needs macOS sips and ffmpeg" }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "marco-media-"));
  execFileSync(ffmpegExecutable, ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1", join(dir, "red.jpg")]);
  execFileSync("sips", ["-s", "format", "heic", join(dir, "red.jpg"), "--out", join(dir, "red.heic")], { stdio: "ignore" });
  const heic = readFileSync(join(dir, "red.heic"));
  assert.ok(isHeif(heic, "application/octet-stream"));
  const media = new Media(dir);
  const file = await media.saveImage(heic, "image/heic");
  assert.match(file, /\.jpg$/);
  assert.deepEqual([...readFileSync(media.path(file)).subarray(0, 2)], [0xff, 0xd8]);
});

test("bundled converter handles PNG without system image tools on PATH", async (t) => {
  assert.notEqual(ffmpegExecutable, "ffmpeg", "npm install must provide the converter binary");
  const dir = mkdtempSync(join(tmpdir(), "marco-no-system-ffmpeg-"));
  const png = join(dir, "photo.png");
  execFileSync(ffmpegExecutable, ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1", png]);
  const originalPath = process.env.PATH;
  t.after(() => { if (originalPath === undefined) delete process.env.PATH; else process.env.PATH = originalPath; });
  process.env.PATH = dir;
  const media = new Media(dir);
  const file = await media.saveImage(readFileSync(png), "image/png");
  assert.match(file, /\.jpg$/);
  assert.deepEqual([...readFileSync(media.path(file)).subarray(0, 2)], [0xff, 0xd8]);
});

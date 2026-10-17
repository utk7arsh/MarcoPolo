// Converts the formats an iPhone actually sends: an Opus-in-CAF voice memo and a HEIC photo.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { isHeif, Media } from "../src/media.js";

const has = (bin: string) => {
  try {
    execFileSync("which", [bin], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
};

test("an iMessage voice memo (Opus in CAF) becomes m4a", { skip: !has("ffmpeg") && "ffmpeg not installed" }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "marco-media-"));
  const caf = join(dir, "memo.caf");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "libopus", "-ar", "48000", caf]);
  const media = new Media(dir, "http://bridge.test");
  const file = await media.saveAudio(readFileSync(caf), "audio/x-caf");
  assert.match(file, /\.m4a$/);
  assert.equal(readFileSync(media.path(file)).toString("latin1", 4, 8), "ftyp");
});

test("a HEIC photo becomes JPEG", { skip: !(has("sips") && has("ffmpeg")) && "needs macOS sips and ffmpeg" }, async () => {
  const dir = mkdtempSync(join(tmpdir(), "marco-media-"));
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=red:s=64x64", "-frames:v", "1", join(dir, "red.jpg")]);
  execFileSync("sips", ["-s", "format", "heic", join(dir, "red.jpg"), "--out", join(dir, "red.heic")], { stdio: "ignore" });
  const heic = readFileSync(join(dir, "red.heic"));
  assert.ok(isHeif(heic, "application/octet-stream"));
  const media = new Media(dir, "http://bridge.test");
  const file = await media.saveImage(heic, "image/heic");
  assert.match(file, /\.jpg$/);
  assert.deepEqual([...readFileSync(media.path(file)).subarray(0, 2)], [0xff, 0xd8]);
});

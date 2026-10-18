import { execFile } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, extname, join } from "node:path";
import { promisify } from "node:util";
import bundledFfmpeg from "ffmpeg-static";
import { log } from "./log.js";

const run = promisify(execFile);
const bundledPath: unknown = bundledFfmpeg;
export const ffmpegExecutable = typeof bundledPath === "string" && existsSync(bundledPath) ? bundledPath : "ffmpeg";

const IMAGE_EXT: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/jpg": "jpg",
  "image/png": "png",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/heic": "heic",
  "image/heif": "heif",
};

const CONTENT_TYPE: Record<string, string> = {
  jpg: "image/jpeg",
  png: "image/png",
  gif: "image/gif",
  webp: "image/webp",
  heic: "image/heic",
  heif: "image/heif",
  m4a: "audio/mp4",
  caf: "audio/x-caf",
  aac: "audio/aac",
  mp3: "audio/mpeg",
  wav: "audio/wav",
  amr: "audio/amr",
  ogg: "audio/ogg",
};

const HEIF_BRANDS = new Set(["heic", "heix", "hevc", "hevx", "heim", "heis", "mif1", "msf1"]);

/** iPhone photos usually arrive as HEIC, sometimes labeled application/octet-stream. */
export function isHeif(buf: Buffer, mimeType?: string): boolean {
  if (mimeType && /^image\/hei[cf]/i.test(mimeType)) return true;
  return buf.length > 12 && buf.toString("latin1", 4, 8) === "ftyp" && HEIF_BRANDS.has(buf.toString("latin1", 8, 12));
}

export function contentTypeFor(file: string): string {
  return CONTENT_TYPE[extname(file).slice(1).toLowerCase()] ?? "application/octet-stream";
}

/**
 * Stores photos as JPEG (what POST /v1/items expects, docs/INTERFACES.md §3.3) and voice notes as m4a, which the
 * phone (AVAudioFile) and the dashboard's browser can both play.
 */
export class Media {
  readonly dir: string;

  constructor(dataDir: string) {
    this.dir = join(dataDir, "media");
    mkdirSync(this.dir, { recursive: true });
  }

  path(file: string): string {
    return join(this.dir, basename(file));
  }

  remove(file: string | null | undefined) {
    if (file) rmSync(this.path(file), { force: true });
  }

  private fresh(prefix: string, ext: string): string {
    return `${prefix}_${randomBytes(8).toString("hex")}.${ext}`;
  }

  async saveImage(buf: Buffer, mimeType: string): Promise<string> {
    if (isHeif(buf, mimeType)) {
      const jpeg = await heifToJpeg(buf);
      if (jpeg) {
        const file = this.fresh("photo", "jpg");
        writeFileSync(this.path(file), jpeg);
        return file;
      }
    }
    const ext = isJpeg(buf) ? "jpg" : (IMAGE_EXT[mimeType.toLowerCase()] ?? (isHeif(buf) ? "heic" : "jpg"));
    const file = this.fresh("photo", ext);
    writeFileSync(this.path(file), buf);
    if (ext === "jpg") return file;
    const jpg = file.replace(/\.[^.]+$/, ".jpg");
    if (await toJpeg(this.path(file), this.path(jpg))) return jpg;
    log.warn(`could not convert ${file} to JPEG; keeping the original`);
    return file;
  }

}

const isJpeg = (buf: Buffer) => buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff;

/** PNG, GIF, WebP and friends: macOS sips, else ffmpeg. */
async function toJpeg(src: string, dst: string): Promise<boolean> {
  if (process.platform === "darwin") {
    try {
      await run("sips", ["-s", "format", "jpeg", src, "--out", dst], { timeout: 15_000 });
      return true;
    } catch {
      // fall through to ffmpeg
    }
  }
  try {
    await run(ffmpegExecutable, ["-y", "-loglevel", "error", "-i", src, "-frames:v", "1", dst], { timeout: 15_000 });
    return true;
  } catch {
    return false;
  }
}

async function heifToJpeg(buf: Buffer): Promise<Buffer | null> {
  try {
    const mod = (await import("heif2jpeg")) as { heifToJpeg: (input: Buffer, options?: { quality?: number }) => Promise<Buffer> };
    return await mod.heifToJpeg(buf, { quality: 85 });
  } catch (err) {
    log.warn("heif2jpeg failed", err);
  }
  if (process.platform !== "darwin") return null;
  const base = join(tmpdir(), `marco-${randomBytes(6).toString("hex")}`);
  try {
    writeFileSync(`${base}.heic`, buf);
    await run("sips", ["-s", "format", "jpeg", `${base}.heic`, "--out", `${base}.jpg`], { timeout: 15_000 });
    return readFileSync(`${base}.jpg`);
  } catch (err) {
    log.warn("sips HEIC conversion failed", err);
    return null;
  } finally {
    rmSync(`${base}.heic`, { force: true });
    rmSync(`${base}.jpg`, { force: true });
  }
}

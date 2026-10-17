import { execFile } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, extname, join } from "node:path";
import { promisify } from "node:util";
import { log } from "./log.js";

const run = promisify(execFile);

const IMAGE_EXT: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/jpg": "jpg",
  "image/png": "png",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/heic": "heic",
  "image/heif": "heif",
};

const AUDIO_EXT: Record<string, string> = {
  "audio/x-caf": "caf",
  "audio/mp4": "m4a",
  "audio/m4a": "m4a",
  "audio/x-m4a": "m4a",
  "audio/aac": "aac",
  "audio/mpeg": "mp3",
  "audio/wav": "wav",
  "audio/x-wav": "wav",
  "audio/amr": "amr",
  "audio/ogg": "ogg",
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

/** Stores photos as JPEG and voice notes as m4a so iOS AVAudioPlayer and every browser can play them. */
export class Media {
  readonly dir: string;

  constructor(
    dataDir: string,
    private readonly publicBaseUrl: string,
  ) {
    this.dir = join(dataDir, "media");
    mkdirSync(this.dir, { recursive: true });
  }

  path(file: string): string {
    return join(this.dir, basename(file));
  }

  url(file: string | null): string | null {
    return file ? `${this.publicBaseUrl}/media/${file}` : null;
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
    const file = this.fresh("photo", IMAGE_EXT[mimeType.toLowerCase()] ?? (isHeif(buf) ? "heic" : "jpg"));
    writeFileSync(this.path(file), buf);
    return file;
  }

  async saveAudio(buf: Buffer, mimeType: string): Promise<string> {
    const original = this.fresh("voice", AUDIO_EXT[mimeType.toLowerCase()] ?? "caf");
    writeFileSync(this.path(original), buf);
    if (original.endsWith(".m4a")) return original;
    const m4a = original.replace(/\.[^.]+$/, ".m4a");
    if (await toM4a(this.path(original), this.path(m4a))) return m4a;
    log.warn(`could not convert ${original} to m4a; keeping the original`);
    return original;
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

async function toM4a(src: string, dst: string): Promise<boolean> {
  try {
    await run("ffmpeg", ["-y", "-loglevel", "error", "-i", src, "-vn", "-c:a", "aac", "-b:a", "96k", dst], { timeout: 20_000 });
    return true;
  } catch {
    // fall through to afconvert
  }
  if (process.platform !== "darwin") return false;
  try {
    await run("afconvert", ["-f", "m4af", "-d", "aac", src, dst], { timeout: 20_000 });
    return true;
  } catch {
    return false;
  }
}

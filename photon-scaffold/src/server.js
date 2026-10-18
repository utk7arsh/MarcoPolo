// @ts-check
/** The Marco server's HTTP routes and the /v1/photon WebSocket, for the bridge (docs/INTERFACES.md §5). */
import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, extname, join } from 'node:path'

const AUDIO_TYPES = { '.caf': 'audio/x-caf', '.m4a': 'audio/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.amr': 'audio/amr' }

export class ServerClient {
  /**
   * @param {string} base  e.g. https://server-mac.your-tailnet.ts.net (through `tailscale serve`)
   * @param {typeof fetch} fetchImpl
   */
  constructor(base, fetchImpl = fetch) {
    this.base = base.replace(/\/+$/, '')
    this.fetch = fetchImpl
  }

  url(path) {
    return new URL(path, this.base + '/').toString()
  }

  async check(r, what) {
    if (!r.ok) throw new Error(`${what}: HTTP ${r.status} ${(await r.text()).slice(0, 300)}`)
    return r
  }

  async getCrop(cropUrl) {
    const r = await this.check(await this.fetch(this.url(cropUrl)), 'crop')
    return new Uint8Array(await r.arrayBuffer())
  }

  /** POST /v1/labels: touch_id (label what was touched) or item_id (add to a label), name, text, audio. */
  async postLabel({ touchId, itemId, name, text, audioPath }) {
    const form = new FormData()
    if (touchId) form.append('touch_id', touchId)
    if (itemId) form.append('item_id', itemId)
    form.append('name', name)
    if (text) form.append('text', text)
    if (audioPath) {
      const type = AUDIO_TYPES[extname(audioPath).toLowerCase()] ?? 'application/octet-stream'
      form.append('audio', new Blob([await readFile(audioPath)], { type }), basename(audioPath))
    }
    const r = await this.check(await this.fetch(this.url('/v1/labels'), { method: 'POST', body: form }), 'label')
    return r.json()
  }

  /** POST /v1/items: register an item from one photo and its name (the server applies EXIF orientation). */
  async postItem(name, photoPath) {
    const form = new FormData()
    form.append('name', name)
    form.append('photo', new Blob([await readFile(photoPath)], { type: 'image/jpeg' }), basename(photoPath))
    const r = await this.check(await this.fetch(this.url('/v1/items'), { method: 'POST', body: form }), 'register')
    return r.json()
  }
}

export function socketUrl(base) {
  const u = new URL('/v1/photon', base.replace(/\/+$/, '') + '/')
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  return u.toString()
}

/** The /v1/photon WebSocket (server to bridge only), reconnecting with backoff. */
export class PhotonSocket {
  /**
   * @param {string} url
   * @param {(msg: any) => void} onMessage
   * @param {{ onState?: (up: boolean) => void, WebSocketImpl?: any }} [opts]
   */
  constructor(url, onMessage, { onState = () => {}, WebSocketImpl = globalThis.WebSocket } = {}) {
    if (!WebSocketImpl) throw new Error('no WebSocket: use Node 22 or later (or Bun)')
    this.url = url
    this.onMessage = onMessage
    this.onState = onState
    this.WebSocketImpl = WebSocketImpl
    this.backoff = 500
    this.stopped = false
    this.ws = null
  }

  connect() {
    this.stopped = false
    const ws = new this.WebSocketImpl(this.url)
    this.ws = ws
    ws.onopen = () => {
      this.backoff = 500
      this.onState(true)
    }
    ws.onmessage = (ev) => {
      try {
        this.onMessage(JSON.parse(typeof ev.data === 'string' ? ev.data : new TextDecoder().decode(ev.data)))
      } catch (e) {
        console.error('bad message from the server:', e)
      }
    }
    ws.onclose = (ev) => {
      this.onState(false)
      if (ev?.code === 1008) console.error('the server refused us (1008): is this login in TAILSCALE_ALLOWED_LOGINS?')
      if (this.stopped) return
      setTimeout(() => this.connect(), this.backoff)
      this.backoff = Math.min(this.backoff * 2, 8000)
    }
    ws.onerror = () => {}
  }

  close() {
    this.stopped = true
    this.ws?.close()
  }
}

/** Crops written to a private temp folder: iMessage sends attachments from absolute local paths. */
export class TempFiles {
  async writeTemp(name, data) {
    this.dir ??= await mkdtemp(join(tmpdir(), 'marco-photon-'))
    const path = join(this.dir, name.replace(/[^\w.-]/g, '_'))
    await writeFile(path, data)
    return path
  }
}

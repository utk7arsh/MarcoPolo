// @ts-check
/**
 * Marco's caretaker bridge as pure logic (docs/INTERFACES.md §5); main.js wires it to iMessage and the server.
 *
 *   label_request from the server     -> the crop goes to the caretaker over iMessage ("What is this?")
 *   the caretaker's text reply        -> POST /v1/labels (name, and the full reply as the spoken label)
 *   a voice note (before or after)    -> added as the label audio: the user hears the caretaker on touch
 *   a photo with a caption, unasked   -> POST /v1/items (caretaker-initiated setup)
 *
 * Only messages from the configured caretakers count. Replies answer the oldest open question first.
 */

/** @typedef {{ type: 'label_request', touch_id: string, crop_url: string, question?: string }} LabelRequest */
/** @typedef {{ path: string, mime: string }} FileRef */
/** @typedef {{ from: string, text: string | null, attachments: FileRef[] }} Incoming */
/**
 * @typedef {{
 *   getCrop(cropUrl: string): Promise<Uint8Array>,
 *   postLabel(l: { touchId?: string, itemId?: string, name: string, text?: string, audioPath?: string }): Promise<{ item_id?: string | null }>,
 *   postItem(name: string, photoPath: string): Promise<{ item_id: string | null, quality: string, reason?: string }>
 * }} ServerApi
 */
/** @typedef {{ send(to: string, text?: string, attachments?: string[]): Promise<void> }} Messenger */
/** @typedef {{ writeTemp(name: string, data: Uint8Array): Promise<string> }} Files */

export const PENDING_MS = 60 * 60 * 1000       // an unanswered "What is this?" is dropped after an hour
export const HOLD_MS = 10 * 60 * 1000          // a voice note or photo waits this long for its name
export const FOLLOWUP_MS = 2 * 60 * 1000       // a voice note this soon after a text label is added to it

/** iMessage puts U+FFFC where an attachment sits in the text. */
export function cleanText(text) {
  return (text ?? '').replace(/\uFFFC/g, '').replace(/[\u2018\u2019]/g, "'").trim()
}

/** "That's the cumin, love" -> "cumin"; "it's my blue mug!" -> "blue mug". */
export function nameFromReply(text) {
  let t = cleanText(text).split(/[,.!?;:\n]| - /)[0].trim()
  t = t.replace(/^(it'?s|it is|that'?s|that is|this is|this'?s|those are|these are|they'?re)\s+/i, '')
  t = t.replace(/^(the|a|an|your|my|our|his|her|their)\s+/i, '')
  return t.trim().toLowerCase()
}

/** Phone numbers compare on their last 10 digits; emails case-insensitively. */
export function sameHandle(a, b) {
  const digits = (s) => s.replace(/[^\d]/g, '')
  if (a.includes('@') || b.includes('@')) return a.trim().toLowerCase() === b.trim().toLowerCase()
  const da = digits(a), db = digits(b)
  return da.length >= 7 && db.length >= 7 && da.slice(-10) === db.slice(-10)
}

export class Bridge {
  /**
   * @param {{ server: ServerApi, messenger: Messenger, files: Files, caretakers: string[], now?: () => number }} deps
   */
  constructor({ server, messenger, files, caretakers, now = () => Date.now() }) {
    if (!caretakers.length) throw new Error('at least one caretaker handle is needed')
    this.server = server
    this.messenger = messenger
    this.files = files
    this.caretakers = caretakers
    this.now = now
    /** @type {{ touchId: string, at: number }[]} */
    this.pending = []
    /** @type {{ path: string, at: number } | null} */
    this.heldAudio = null
    /** @type {{ path: string, at: number } | null} */
    this.heldPhoto = null
    /** @type {{ itemId: string, name: string, text: string, at: number } | null} */
    this.recent = null
  }

  /** The server wants to know what the user is touching: send the crop to the (first) caretaker. */
  async onLabelRequest(/** @type {LabelRequest} */ r) {
    const crop = await this.server.getCrop(r.crop_url)
    const path = await this.files.writeTemp(`crop-${r.touch_id}.jpg`, crop)
    this.pending.push({ touchId: r.touch_id, at: this.now() })
    const question = r.question ?? 'What is this?'
    await this.messenger.send(this.caretakers[0],
      `Marco here. ${question} Reply with its name. Then, if you like, send a voice note: they'll hear you when they touch it.`,
      [path])
    return `asked about ${r.touch_id}`
  }

  /** A message from iMessage. Returns what was done (for the log). */
  async onMessage(/** @type {Incoming} */ m) {
    const from = this.caretakers.find((c) => sameHandle(c, m.from))
    if (!from) return `ignored: ${m.from} is not a caretaker`
    this.expire()
    const text = cleanText(m.text)
    const audio = m.attachments.find((a) => a.mime.startsWith('audio/'))
    const photo = m.attachments.find((a) => a.mime.startsWith('image/'))

    if (photo) {
      if (!text) {
        this.heldPhoto = { path: photo.path, at: this.now() }
        await this.messenger.send(from, 'Got the photo. What is it called?')
        return 'photo held for a name'
      }
      return this.register(from, nameFromReply(text) || text, photo.path)
    }

    if (audio) {
      if (this.recent && !text) {
        const r = this.recent
        this.recent = null
        await this.server.postLabel({ itemId: r.itemId, name: r.name, text: r.text, audioPath: audio.path })
        await this.messenger.send(from, `Got your voice note for the ${r.name}.`)
        return `voice note added to ${r.itemId}`
      }
      if (!this.pending.length) {
        await this.messenger.send(from, "Thanks! I wasn't asking about anything just now.")
        return 'voice note with nothing to label'
      }
      if (text) return this.label(from, text, audio.path)
      this.heldAudio = { path: audio.path, at: this.now() }
      await this.messenger.send(from, 'Got your voice note. What is it called?')
      return 'voice note held for a name'
    }

    if (!text) return 'empty message'
    if (this.heldPhoto) {
      const p = this.heldPhoto
      this.heldPhoto = null
      return this.register(from, nameFromReply(text) || text, p.path)
    }
    if (this.pending.length) return this.label(from, text, this.heldAudio?.path)
    await this.messenger.send(from,
      'Hi from Marco. To add something, send a photo of it with its name. When I send you a photo, reply with what it is.')
    return 'help sent'
  }

  async label(from, text, audioPath) {
    const req = /** @type {{ touchId: string, at: number }} */ (this.pending.shift())
    const name = nameFromReply(text) || text.toLowerCase()
    this.heldAudio = null
    const res = await this.server.postLabel({ touchId: req.touchId, name, text, audioPath })
    if (audioPath) {
      await this.messenger.send(from, `Thanks! I'll tell them it's the ${name}, in your voice.`)
    } else {
      if (res.item_id) this.recent = { itemId: res.item_id, name, text, at: this.now() }
      await this.messenger.send(from, `Thanks! I'll tell them it's the ${name}. Send a voice note too and they'll hear you when they touch it.`)
    }
    return `labelled ${req.touchId} as ${name}${audioPath ? ' with a voice note' : ''}`
  }

  async register(from, name, photoPath) {
    const r = await this.server.postItem(name, photoPath)
    if (r.quality === 'ok') {
      await this.messenger.send(from, `Saved the ${name}. Marco will look out for it.`)
      return `registered ${name} (${r.item_id})`
    }
    await this.messenger.send(from, `I can't see the ${name} clearly in that photo. Could you send another, closer and in good light?`)
    return `registration of ${name} needs a retake: ${r.reason ?? ''}`
  }

  expire() {
    const t = this.now()
    this.pending = this.pending.filter((p) => t - p.at <= PENDING_MS)
    if (this.heldAudio && t - this.heldAudio.at > HOLD_MS) this.heldAudio = null
    if (this.heldPhoto && t - this.heldPhoto.at > HOLD_MS) this.heldPhoto = null
    if (this.recent && t - this.recent.at > FOLLOWUP_MS) this.recent = null
  }
}

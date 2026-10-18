// @ts-check
/**
 * Marco's caretaker bridge on a Mac signed in to Messages (needs Full Disk Access for the terminal running it).
 *
 *   MARCO_SERVER=https://server-mac.your-tailnet.ts.net CARETAKERS=+15551234567 npm start
 *
 * Talks to the server through `tailscale serve`, so the server's allow-list sees this Mac's tailnet login.
 */
import { IMessageSDK, isAudioAttachment, isImageAttachment } from '@photon-ai/imessage-kit'

import { Bridge } from './bridge.js'
import { PhotonSocket, ServerClient, TempFiles, socketUrl } from './server.js'

const SERVER = process.env.MARCO_SERVER
const CARETAKERS = (process.env.CARETAKERS ?? '').split(',').map((s) => s.trim()).filter(Boolean)
if (!SERVER || !CARETAKERS.length) {
  console.error('Set MARCO_SERVER (the tailscale serve URL) and CARETAKERS (comma-separated phone numbers or emails).')
  process.exit(1)
}

const sdk = new IMessageSDK()
const bridge = new Bridge({
  server: new ServerClient(SERVER),
  messenger: { send: (to, text, attachments) => sdk.send({ to, text, attachments }) },
  files: new TempFiles(),
  caretakers: CARETAKERS,
})

const socket = new PhotonSocket(socketUrl(SERVER), (msg) => {
  if (msg.type !== 'label_request') return
  bridge.onLabelRequest(msg).then(console.log, (e) => console.error('label request failed:', e))
}, { onState: (up) => console.log(up ? 'connected to the Marco server' : 'disconnected from the Marco server') })
socket.connect()

/** Attachments can still be downloading when the message arrives: re-read it until they're on disk (10 s). */
async function incoming(msg) {
  for (let i = 0; i < 10 && msg.attachments.some((a) => !a.localPath); i++) {
    await new Promise((r) => setTimeout(r, 1000))
    const again = await sdk.getMessages({ chatId: msg.chatId ?? undefined, limit: 10 })
    msg = again.find((m) => m.id === msg.id) ?? msg
  }
  const attachments = msg.attachments
    .filter((a) => a.localPath && (isAudioAttachment(a) || isImageAttachment(a)))
    .map((a) => ({ path: a.localPath, mime: isAudioAttachment(a) ? (a.mimeType || 'audio/x-caf') : (a.mimeType || 'image/jpeg') }))
  return { from: msg.participant ?? '', text: msg.text, attachments }
}

await sdk.startWatching({
  onDirectMessage: async (msg) => {
    try {
      console.log(await bridge.onMessage(await incoming(msg)))
    } catch (e) {
      console.error('handling a message failed:', e)
    }
  },
  onError: (e) => console.error('iMessage watcher:', e),
})
console.log(`watching iMessage for ${CARETAKERS.join(', ')}`)

process.on('SIGINT', async () => {
  socket.close()
  await sdk.stopWatching()
  await sdk.close()
  process.exit(0)
})

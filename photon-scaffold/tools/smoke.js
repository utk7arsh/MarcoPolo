// @ts-check
// The bridge's server calls against a running Marco server, without iMessage (used by
// server/tests/test_photon_contract.py; also handy by hand against the stub).
//   node tools/smoke.js <server> <touch_id> <crop_url> <voice-note file> <photo file>
import { ServerClient } from '../src/server.js'

const [base, touchId, cropUrl, audioPath, photoPath] = process.argv.slice(2)
const c = new ServerClient(base)
const crop = await c.getCrop(cropUrl)
const label = await c.postLabel({ touchId, name: 'cumin', text: "That's the cumin, love" })
const voice = await c.postLabel({ itemId: label.item_id, name: 'cumin', text: "That's the cumin, love", audioPath })
const item = await c.postItem('keys', photoPath)
console.log(JSON.stringify({ cropBytes: crop.length, cropIsJpeg: crop[0] === 0xff && crop[1] === 0xd8, label, voice, item }))

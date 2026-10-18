// node --test test/   (Node 18+, no installs: the iMessage SDK is only loaded by src/main.js)
import assert from 'node:assert/strict'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'

import { Bridge, FOLLOWUP_MS, HOLD_MS, PENDING_MS, cleanText, nameFromReply, sameHandle } from '../src/bridge.js'
import { ServerClient, TempFiles, socketUrl } from '../src/server.js'

const MOM = '+1 (555) 123-4567'

function rig(caretakers = [MOM]) {
  let t = 1_000_000
  const calls = { crop: [], labels: [], items: [], sent: [] }
  const server = {
    getCrop: async (url) => { calls.crop.push(url); return new Uint8Array([0xff, 0xd8, 0xff]) },
    postLabel: async (l) => { calls.labels.push(l); return { status: 'ok', item_id: `item-${calls.labels.length}` } },
    postItem: async (name, path) => { calls.items.push({ name, path }); return name === 'blur' ? { item_id: null, quality: 'retake', reason: 'small' } : { item_id: 'new', quality: 'ok' } },
  }
  const messenger = { send: async (to, text, attachments) => { calls.sent.push({ to, text, attachments }) } }
  const files = { writeTemp: async (name) => `/tmp/x/${name}` }
  const bridge = new Bridge({ server, messenger, files, caretakers, now: () => t })
  return { bridge, calls, advance: (ms) => { t += ms } }
}

const fromMom = (text, attachments = []) => ({ from: '5551234567', text, attachments })

test('a label request sends the crop to the caretaker with the question', async () => {
  const { bridge, calls } = rig()
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't1', crop_url: '/v1/touch/t1/crop.jpg', question: 'What is this?' })
  assert.deepEqual(calls.crop, ['/v1/touch/t1/crop.jpg'])
  assert.equal(calls.sent.length, 1)
  assert.equal(calls.sent[0].to, MOM)
  assert.match(calls.sent[0].text, /What is this\? Reply with its name/)
  assert.deepEqual(calls.sent[0].attachments, ['/tmp/x/crop-t1.jpg'])
})

test('a text reply labels the oldest open question; a voice note right after is added to it', async () => {
  const { bridge, calls, advance } = rig()
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't1', crop_url: '/c1' })
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't2', crop_url: '/c2' })
  assert.match(await bridge.onMessage(fromMom('That’s the cumin, love')), /labelled t1 as cumin/)
  assert.deepEqual(calls.labels[0], { touchId: 't1', name: 'cumin', text: "That's the cumin, love", audioPath: undefined })
  advance(FOLLOWUP_MS - 1000)
  assert.match(await bridge.onMessage(fromMom('￼', [{ path: '/m/voice.caf', mime: 'audio/x-caf' }])), /voice note added to item-1/)
  assert.deepEqual(calls.labels[1], { itemId: 'item-1', name: 'cumin', text: "That's the cumin, love", audioPath: '/m/voice.caf' })
  assert.match(await bridge.onMessage(fromMom('paprika')), /labelled t2 as paprika/)
  assert.equal(bridge.pending.length, 0)
})

test('a voice note first waits for the name, then both go together', async () => {
  const { bridge, calls } = rig()
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't1', crop_url: '/c1' })
  assert.equal(await bridge.onMessage(fromMom(null, [{ path: '/m/v.caf', mime: 'audio/x-caf' }])), 'voice note held for a name')
  assert.match(calls.sent.at(-1).text, /What is it called/)
  assert.equal(calls.labels.length, 0)
  await bridge.onMessage(fromMom('Turmeric'))
  assert.deepEqual(calls.labels, [{ touchId: 't1', name: 'turmeric', text: 'Turmeric', audioPath: '/m/v.caf' }])
  assert.match(calls.sent.at(-1).text, /in your voice/)
})

test('a captioned photo registers an item; without a caption it waits for the name', async () => {
  const { bridge, calls } = rig()
  assert.match(await bridge.onMessage(fromMom('my keys', [{ path: '/p/keys.jpg', mime: 'image/jpeg' }])), /registered keys/)
  assert.deepEqual(calls.items[0], { name: 'keys', path: '/p/keys.jpg' })
  assert.match(calls.sent.at(-1).text, /Saved the keys/)
  assert.equal(await bridge.onMessage(fromMom('', [{ path: '/p/w.heic', mime: 'image/heic' }])), 'photo held for a name')
  await bridge.onMessage(fromMom('wallet'))
  assert.deepEqual(calls.items[1], { name: 'wallet', path: '/p/w.heic' })
  assert.match(await bridge.onMessage(fromMom('blur', [{ path: '/p/b.jpg', mime: 'image/jpeg' }])), /needs a retake/)
  assert.match(calls.sent.at(-1).text, /another, closer/)
})

test('strangers are ignored and nothing reaches the server', async () => {
  const { bridge, calls } = rig()
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't1', crop_url: '/c1' })
  assert.match(await bridge.onMessage({ from: '+44 20 7946 0000', text: 'bleach', attachments: [] }), /ignored/)
  assert.match(await bridge.onMessage({ from: 'someone@example.com', text: 'x', attachments: [{ path: '/p', mime: 'image/jpeg' }] }), /ignored/)
  assert.equal(calls.labels.length + calls.items.length, 0)
  assert.equal(bridge.pending.length, 1)
})

test('old questions and held files expire', async () => {
  const { bridge, calls, advance } = rig()
  await bridge.onLabelRequest({ type: 'label_request', touch_id: 't1', crop_url: '/c1' })
  advance(PENDING_MS + 1)
  assert.equal(await bridge.onMessage(fromMom('cumin')), 'help sent')
  await bridge.onMessage(fromMom('', [{ path: '/p/x.jpg', mime: 'image/jpeg' }]))
  advance(HOLD_MS + 1)
  assert.equal(await bridge.onMessage(fromMom('mug')), 'help sent')
  assert.equal(calls.labels.length + calls.items.length, 0)
})

test('names from replies, and handle matching', () => {
  assert.equal(nameFromReply('cumin'), 'cumin')
  assert.equal(nameFromReply("That's the cumin, love"), 'cumin')
  assert.equal(nameFromReply('it’s my blue mug!'), 'blue mug')
  assert.equal(nameFromReply('Keys'), 'keys')
  assert.equal(nameFromReply('  the remote.  '), 'remote')
  assert.equal(nameFromReply('These are the vitamins - morning ones'), 'vitamins')
  assert.equal(cleanText('￼ hi ￼'), 'hi')
  assert.ok(sameHandle('+1 (555) 123-4567', '5551234567'))
  assert.ok(sameHandle('Mom@Example.com', 'mom@example.com '))
  assert.ok(!sameHandle('+15551234567', '+15551234568'))
  assert.ok(!sameHandle('123', '123'))
  assert.throws(() => rig([]))
})

test('the server client builds the routes and forms the server expects', async () => {
  const seen = []
  const fake = async (url, init) => {
    seen.push({ url: String(url), method: init?.method ?? 'GET', form: init?.body ? Object.fromEntries(init.body.entries()) : null })
    return new Response(init ? JSON.stringify({ status: 'ok', item_id: 'i1', quality: 'ok' }) : new Uint8Array([1, 2]), { status: 200 })
  }
  const dir = await mkdtemp(join(tmpdir(), 'photon-test-'))
  await writeFile(join(dir, 'v.caf'), 'audio')
  await writeFile(join(dir, 'p.jpg'), 'jpeg')
  const c = new ServerClient('https://server.example.ts.net/', fake)
  assert.deepEqual([...await c.getCrop('/v1/touch/t1/crop.jpg')], [1, 2])
  assert.equal((await c.postLabel({ touchId: 't1', name: 'cumin', text: 'the cumin', audioPath: join(dir, 'v.caf') })).item_id, 'i1')
  await c.postItem('keys', join(dir, 'p.jpg'))
  assert.equal(seen[0].url, 'https://server.example.ts.net/v1/touch/t1/crop.jpg')
  assert.equal(seen[1].url, 'https://server.example.ts.net/v1/labels')
  assert.equal(seen[1].form.touch_id, 't1')
  assert.equal(seen[1].form.name, 'cumin')
  assert.equal(seen[1].form.audio.type, 'audio/x-caf')
  assert.equal(seen[2].form.photo.type, 'image/jpeg')
  assert.equal(socketUrl('https://server.example.ts.net'), 'wss://server.example.ts.net/v1/photon')
  assert.equal(socketUrl('http://127.0.0.1:8000/'), 'ws://127.0.0.1:8000/v1/photon')
  const tf = new TempFiles()
  const p = await tf.writeTemp('crop-a/b.jpg', new Uint8Array([9]))
  assert.match(p, /crop-a_b\.jpg$/)
})

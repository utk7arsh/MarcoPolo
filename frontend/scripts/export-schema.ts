import { readFileSync, writeFileSync } from 'node:fs'
import { z } from 'zod'
import { snapshotSchema, soundSchema } from '../src/lib/schema.ts'

// The browser's contract as JSON Schema, for the server's tests: the snapshot, and what the wearer hears.
const exports = [
  [snapshotSchema, 'dashboard.snapshot.schema.json', 'Snapshot'],
  [soundSchema, 'dashboard.sound.schema.json', 'Sound'],
] as const
for (const [zod, file, name] of exports) {
  const schema = z.toJSONSchema(zod, { target: 'draft-2020-12', io: 'input' })
  const target = new URL(`../docs/${file}`, import.meta.url)
  const contents = JSON.stringify(schema, null, 2) + '\n'
  if (process.argv.includes('--check')) {
    let current = ''
    try {
      current = readFileSync(target, 'utf8')
    } catch {
      // missing: reported below
    }
    if (current !== contents) {
      console.error(
        `${name} JSON Schema has changed. Run npm run schema:export.`,
      )
      process.exitCode = 1
    }
  } else {
    writeFileSync(target, contents)
    console.log(`Updated frontend/docs/${file}`)
  }
}

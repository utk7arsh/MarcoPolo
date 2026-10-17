import { readFileSync, writeFileSync } from 'node:fs'
import { z } from 'zod'
import { snapshotSchema } from '../src/lib/schema.ts'

const schema = z.toJSONSchema(snapshotSchema, {
  target: 'draft-2020-12',
  io: 'input',
})
const target = new URL(
  '../docs/dashboard.snapshot.schema.json',
  import.meta.url,
)
const contents = JSON.stringify(schema, null, 2) + '\n'
if (process.argv.includes('--check')) {
  if (readFileSync(target, 'utf8') !== contents) {
    console.error(
      'Snapshot JSON Schema has changed. Run npm run schema:export.',
    )
    process.exitCode = 1
  }
} else {
  writeFileSync(target, contents)
  console.log('Updated frontend/docs/dashboard.snapshot.schema.json')
}

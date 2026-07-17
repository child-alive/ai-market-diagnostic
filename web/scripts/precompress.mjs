import { promises as fs } from 'node:fs'
import path from 'node:path'
import { gzipSync } from 'node:zlib'

const outDir = path.resolve(process.cwd(), process.argv[2] || 'dist')
const queue = [outDir]
let written = 0

while (queue.length) {
  const current = queue.pop()
  for (const entry of await fs.readdir(current, { withFileTypes: true })) {
    const file = path.join(current, entry.name)
    if (entry.isDirectory()) {
      queue.push(file)
      continue
    }
    if (!/\.(?:css|html|js|json)$/.test(entry.name)) continue
    const source = await fs.readFile(file)
    if (source.byteLength < 1024) continue
    await fs.writeFile(`${file}.gz`, gzipSync(source, { level: 9 }))
    written += 1
  }
}

console.log(`precompress: wrote ${written} gzip assets to ${path.relative(process.cwd(), outDir)}`)

import { promises as fs } from 'node:fs'
import path from 'node:path'

const outDir = path.resolve(process.cwd(), process.argv[2] || 'dist')
const source = path.join(outDir, 'full-report.html')
const reportDir = path.join(outDir, 'report')

await fs.mkdir(reportDir, { recursive: true })
await fs.copyFile(source, path.join(reportDir, 'index.html'))
console.log(`prepare-static: wrote ${path.relative(process.cwd(), path.join(reportDir, 'index.html'))}`)

import { createHash } from 'node:crypto'
import { lstat, readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const helpDirectory = path.resolve(scriptDirectory, '..')
const repositoryDirectory = path.resolve(helpDirectory, '..')
const contentDirectory = path.join(helpDirectory, 'content')
const outputDirectory = path.join(helpDirectory, '.vitepress', 'dist')
const basePath = '/conflua/'
const previewOrigin = 'https://conflua.invalid'

export const expectedContentFiles = [
  'index.md',
  'guide/first-handoff.md',
  'guide/workspaces.md',
  'guide/members.md',
  'guide/routing.md',
  'guide/tracking.md',
  'guide/agents.md',
  'reference/troubleshooting.md',
  'reference/windows.md',
  'reference/macos.md',
  'illustrations/review-timeline.png',
  'illustrations/member-setup.png',
  'illustrations/workspaces.svg',
  'illustrations/routing.svg',
  'illustrations/tracking.svg',
  'illustrations/architecture.svg',
  'illustrations/handoff-sequence.svg',
]

export const expectedPageFiles = [
  'index.html',
  '404.html',
  'guide/first-handoff.html',
  'guide/workspaces.html',
  'guide/members.html',
  'guide/routing.html',
  'guide/tracking.html',
  'guide/agents.html',
  'reference/troubleshooting.html',
  'reference/windows.html',
  'reference/macos.html',
]

const expectedContentDirectories = ['guide', 'illustrations', 'reference']
const expectedFrameworkFiles = ['hashmap.json', 'vp-icons.css']
const acceptedSnapshotHash =
  '1425cb8868b00a996c2bdb290e2f64511317387c4fe20732c4c9ff86fb9afae3'
const allowedAssetExtensions = new Set(['.css', '.js', '.png', '.svg', '.woff2'])
const acceptedSnapshotFiles = [
  'docs/guide/windows-desktop.md',
  'docs/guide/macos-desktop.md',
  ...expectedContentFiles.map((file) => `help/content/${file}`),
]

function normalizedPath(value) {
  return value.split(path.sep).join('/')
}

function compareLists(label, actual, expected) {
  const actualSorted = [...actual].sort()
  const expectedSorted = [...expected].sort()
  if (
    actualSorted.length === expectedSorted.length &&
    actualSorted.every((value, index) => value === expectedSorted[index])
  ) {
    return
  }

  const actualSet = new Set(actualSorted)
  const expectedSet = new Set(expectedSorted)
  const missing = expectedSorted.filter((value) => !actualSet.has(value))
  const unexpected = actualSorted.filter((value) => !expectedSet.has(value))
  throw new Error(
    `${label} mismatch; missing: ${missing.join(', ') || 'none'}; unexpected: ${unexpected.join(', ') || 'none'}`,
  )
}

async function walkTree(rootDirectory) {
  const files = []
  const directories = []

  async function visit(relativeDirectory = '') {
    const absoluteDirectory = path.join(rootDirectory, ...relativeDirectory.split('/').filter(Boolean))
    const entries = await readdir(absoluteDirectory, { withFileTypes: true })

    for (const entry of entries) {
      const relativePath = relativeDirectory
        ? `${relativeDirectory}/${entry.name}`
        : entry.name
      const absolutePath = path.join(absoluteDirectory, entry.name)
      const entryStat = await lstat(absolutePath)
      if (entryStat.isSymbolicLink()) {
        throw new Error(`Symbolic links are not allowed: ${relativePath}`)
      }
      if (entryStat.isDirectory()) {
        directories.push(relativePath)
        await visit(relativePath)
      } else if (entryStat.isFile()) {
        files.push(relativePath)
      } else {
        throw new Error(`Unsupported filesystem entry: ${relativePath}`)
      }
    }
  }

  await visit()
  return { files: files.map(normalizedPath), directories: directories.map(normalizedPath) }
}

async function checkSourceInventory() {
  const { files, directories } = await walkTree(contentDirectory)
  compareLists('Reviewed content files', files, expectedContentFiles)
  compareLists('Reviewed content directories', directories, expectedContentDirectories)

  const records = await Promise.all(
    acceptedSnapshotFiles.map(async (relativePath) => {
      const filePath = path.join(repositoryDirectory, ...relativePath.split('/'))
      const contentHash = createHash('sha256').update(await readFile(filePath)).digest('hex')
      return `${contentHash}  ${relativePath}`
    }),
  )
  const snapshotHash = createHash('sha256')
    .update(records.sort().join('\n'), 'utf8')
    .digest('hex')

  if (snapshotHash !== acceptedSnapshotHash) {
    throw new Error(
      `T01 snapshot mismatch: expected ${acceptedSnapshotHash}, got ${snapshotHash}`,
    )
  }
}

function outputTarget(reference, sourceFile) {
  const trimmedReference = reference.trim().replaceAll('&amp;', '&')
  if (
    trimmedReference === '' ||
    trimmedReference.startsWith('#') ||
    /^(data|mailto|tel|javascript):/i.test(trimmedReference)
  ) {
    return null
  }

  let resolvedUrl
  try {
    resolvedUrl = new URL(trimmedReference, `${previewOrigin}${basePath}${sourceFile}`)
  } catch {
    throw new Error(`Invalid URL in ${sourceFile}: ${reference}`)
  }

  if (resolvedUrl.origin !== previewOrigin) {
    return null
  }
  if (!resolvedUrl.pathname.startsWith(basePath)) {
    throw new Error(`Local URL escapes ${basePath} in ${sourceFile}: ${reference}`)
  }

  let target = decodeURIComponent(resolvedUrl.pathname.slice(basePath.length))
  if (target === '' || target.endsWith('/')) {
    target = `${target}index.html`
  }
  target = path.posix.normalize(target)
  if (target === '..' || target.startsWith('../')) {
    throw new Error(`Local URL escapes the site output in ${sourceFile}: ${reference}`)
  }
  return target
}

function htmlReferences(content) {
  const references = []
  const attributePattern = /\b(?:href|src|poster)=(["'])(.*?)\1/gi
  for (const match of content.matchAll(attributePattern)) {
    references.push(match[2])
  }

  const srcsetPattern = /\bsrcset=(["'])(.*?)\1/gi
  for (const match of content.matchAll(srcsetPattern)) {
    for (const item of match[2].split(',')) {
      references.push(item.trim().split(/\s+/, 1)[0])
    }
  }
  return references
}

function cssReferences(content) {
  const references = []
  const urlPattern = /url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*?))\s*\)/gi
  for (const match of content.matchAll(urlPattern)) {
    references.push(match[1] ?? match[2] ?? match[3])
  }

  const importPattern = /@import\s+(?:"([^"]+)"|'([^']+)')/gi
  for (const match of content.matchAll(importPattern)) {
    references.push(match[1] ?? match[2])
  }
  return references
}

export async function checkOutput(directory = outputDirectory) {
  const { files, directories } = await walkTree(directory)
  const filesSet = new Set(files)
  const htmlContents = new Map()
  compareLists(
    'Generated HTML pages',
    files.filter((file) => file.endsWith('.html')),
    expectedPageFiles,
  )

  const expectedRouteDirectories = new Set(
    expectedPageFiles
      .map((file) => path.posix.dirname(file))
      .filter((directoryName) => directoryName !== '.'),
  )
  for (const directoryName of directories) {
    if (
      !expectedRouteDirectories.has(directoryName) &&
      directoryName !== 'assets' &&
      !directoryName.startsWith('assets/')
    ) {
      throw new Error(`Unexpected output directory: ${directoryName}`)
    }
  }

  for (const file of files) {
    if (
      !expectedPageFiles.includes(file) &&
      !expectedFrameworkFiles.includes(file) &&
      !file.startsWith('assets/')
    ) {
      throw new Error(`Unexpected output file: ${file}`)
    }
    if (
      file.startsWith('assets/') &&
      !allowedAssetExtensions.has(path.posix.extname(file).toLowerCase())
    ) {
      throw new Error(`Unexpected generated asset type: ${file}`)
    }
  }

  for (const frameworkFile of expectedFrameworkFiles) {
    if (!filesSet.has(frameworkFile)) {
      throw new Error(`Missing VitePress framework output: ${frameworkFile}`)
    }
  }

  for (const pageFile of expectedPageFiles) {
    const content = await readFile(path.join(directory, ...pageFile.split('/')), 'utf8')
    htmlContents.set(pageFile, content)
    for (const reference of htmlReferences(content)) {
      const target = outputTarget(reference, pageFile)
      if (target && !filesSet.has(target)) {
        throw new Error(`Missing local output referenced by ${pageFile}: ${reference}`)
      }
    }
  }

  for (const file of files.filter((candidate) => candidate.endsWith('.css'))) {
    const content = await readFile(path.join(directory, ...file.split('/')), 'utf8')
    for (const reference of cssReferences(content)) {
      const target = outputTarget(reference, file)
      if (target && !filesSet.has(target)) {
        throw new Error(`Missing local output referenced by ${file}: ${reference}`)
      }
    }
  }

  const reviewedMediaFiles = expectedContentFiles.filter((file) =>
    /\.(png|svg)$/i.test(file),
  )
  const reviewedMediaHashes = new Set()
  for (const mediaFile of reviewedMediaFiles) {
    const content = await readFile(path.join(contentDirectory, ...mediaFile.split('/')))
    reviewedMediaHashes.add(createHash('sha256').update(content).digest('hex'))

    if (mediaFile.endsWith('.svg')) {
      const embeddedSvg = `data:image/svg+xml;base64,${content.toString('base64')}`
      if (![...htmlContents.values()].some((html) => html.includes(embeddedSvg))) {
        throw new Error(`Reviewed SVG is missing from generated pages: ${mediaFile}`)
      }
    }
  }

  const emittedMediaHashes = new Set()
  for (const file of files.filter((candidate) => /\.(png|svg)$/i.test(candidate))) {
    const content = await readFile(path.join(directory, ...file.split('/')))
    const contentHash = createHash('sha256').update(content).digest('hex')
    if (!reviewedMediaHashes.has(contentHash)) {
      throw new Error(`Unreviewed image asset in site output: ${file}`)
    }
    emittedMediaHashes.add(contentHash)
  }

  for (const mediaFile of reviewedMediaFiles.filter((file) => file.endsWith('.png'))) {
    const content = await readFile(path.join(contentDirectory, ...mediaFile.split('/')))
    const contentHash = createHash('sha256').update(content).digest('hex')
    if (!emittedMediaHashes.has(contentHash)) {
      throw new Error(`Reviewed raster image is missing from output: ${mediaFile}`)
    }
  }

  return {
    pageCount: expectedPageFiles.length,
    assetCount: files.filter((file) => file.startsWith('assets/')).length,
  }
}

async function main() {
  await checkSourceInventory()
  const { pageCount, assetCount } = await checkOutput()
  console.log(
    `Verified accepted T01 snapshot; ${pageCount} HTML pages and ${assetCount} generated assets.`,
  )
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.message)
    process.exitCode = 1
  })
}

import assert from 'node:assert/strict'
import { cp, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { checkOutput } from './check-site.mjs'

const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), 'conflua-pages-check-'))
const resolvedTemporaryRoot = path.resolve(temporaryRoot)
const resolvedTemporaryParent = `${path.resolve(os.tmpdir())}${path.sep}`
const helpDirectory = path.resolve(import.meta.dirname, '..')
const builtSite = path.join(helpDirectory, '.vitepress', 'dist')
const testSite = path.join(temporaryRoot, 'site')

try {
  assert.ok(resolvedTemporaryRoot.startsWith(resolvedTemporaryParent))
  await cp(builtSite, testSite, { recursive: true })
  await checkOutput(testSite)
  await writeFile(path.join(testSite, 'unlisted-article.html'), '<h1>Extra</h1>\n')

  await assert.rejects(
    checkOutput(testSite),
    /unlisted-article\.html/,
  )
  console.log('Artifact checker rejects an unlisted article.')
} finally {
  await rm(temporaryRoot, { recursive: true, force: true })
}

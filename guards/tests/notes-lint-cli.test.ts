// Gate A item 4: the README's ten-minute demo has to run.
//
// Its third command was `npm --prefix guards run lint:notes -- examples/…`.
// `--prefix` runs the script with the working directory set to `guards/`, so a
// path written relative to the repository root does not resolve, and the
// linter died with a raw Node stack trace naming a file the reader can see is
// there. The demo is the first thing the README offers, and it failed on a
// correct checkout.
//
// Fixed in the tool rather than the prose: npm exports INIT_CWD as the
// directory it was invoked from, so a relative argument resolves against the
// place the reader typed it. That fixes the whole class, not the one command
// the README happened to print.

import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')
const DEMO_NOTES = 'examples/demo-project/literature/reading_notes/smith2024_NOTES.md'

const dirs: string[] = []
after(() => { for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true }) })

/**
 * The demo's command, run exactly as the README prints it. npm is a .cmd shim
 * on Windows and Node refuses to spawn one without a shell since the fix for
 * CVE-2024-27980, so the argument that can contain spaces is quoted there.
 */
function lintFromRepoRoot(...args: string[]) {
  const onWindows = process.platform === 'win32'
  const passed = onWindows ? args.map((a) => `"${a}"`) : args
  return spawnSync(onWindows ? 'npm.cmd' : 'npm',
    ['--prefix', 'guards', 'run', '--silent', 'lint:notes', '--', ...passed],
    { cwd: PRODUCT_ROOT, encoding: 'utf8', timeout: 300_000, shell: onWindows })
}

/** Everything a failed run said, including why a spawn never started. */
function saidBy(res: { stdout?: string; stderr?: string; error?: Error }): string {
  return `${res.stdout ?? ''}${res.stderr ?? ''}${res.error ? `\n${res.error.message}` : ''}`
}

test('the demo command lints a repo-relative path from the repository root', () => {
  const res = lintFromRepoRoot(DEMO_NOTES)
  assert.equal(res.status, 0, `the README's own command failed:\n${saidBy(res)}`)
})

test('a path that does not exist is a message, not a stack trace', () => {
  // The reader of a stack trace cannot tell a wrong path from a broken install.
  const res = lintFromRepoRoot('literature/reading_notes/no-such-file_NOTES.md')
  assert.notEqual(res.status, 0)
  const output = saidBy(res)
  assert.doesNotMatch(output, /at readFileSync|at ModuleJob|node:internal/, `raw stack trace:\n${output}`)
  assert.match(output, /no-such-file_NOTES\.md/, 'the message should name the file it could not read')
})

test('an absolute path still works, and INIT_CWD does not override it', () => {
  const dir = mkdtempSync(join(tmpdir(), 'awt-lint-cli-'))
  dirs.push(dir)
  const file = join(dir, 'absolute_NOTES.md')
  writeFileSync(file, 'not a notes file')
  const res = lintFromRepoRoot(file)
  // Content is wrong, so it fails — but on the content, having found the file.
  assert.notEqual(res.status, 0)
  assert.match(saidBy(res), /absolute_NOTES\.md/)
  assert.doesNotMatch(saidBy(res), /ENOENT/)
})

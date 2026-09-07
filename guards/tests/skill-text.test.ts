// Gate A goal 3: a skill describes the surface it is running on.
//
// Several skills still described a world that no longer exists. `/read` told
// the agent the page budget was "an advisory rule the model follows
// imperfectly, not an enforced counter" and that the guard enforcing it would
// ship "in P1" — it shipped, and denies with PAGE_BUDGET_EXCEEDED. `/note`
// named `/progress`, retired from the catalogue. The export documentation
// prescribed `/style` and `/logic-review`, which are not in it either.
//
// Prose cannot all be checked mechanically, but three things can, and each of
// them is a way the text drifts from the product without anyone noticing.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')
const SKILLS_SRC = join(PRODUCT_ROOT, '.claude', 'skills')
const SKILL_DOCS = join(PRODUCT_ROOT, 'docs', 'skills')

const CATALOGUE = readdirSync(SKILLS_SRC, { withFileTypes: true })
  .filter((e) => e.isDirectory()).map((e) => e.name).sort()

/** Every file that tells a reader or an agent which skills exist. */
function skillProse(): Array<{ where: string; body: string }> {
  const out = CATALOGUE.map((name) => ({
    where: `.claude/skills/${name}/SKILL.md`,
    body: readFileSync(join(SKILLS_SRC, name, 'SKILL.md'), 'utf8'),
  }))
  if (existsSync(SKILL_DOCS)) {
    for (const f of readdirSync(SKILL_DOCS).filter((n) => n.endsWith('.md'))) {
      out.push({ where: `docs/skills/${f}`, body: readFileSync(join(SKILL_DOCS, f), 'utf8') })
    }
  }
  return out
}

test('no skill or skill document sends the reader to a command outside the catalogue', () => {
  // A retired skill keeps working as an instruction long after it stops
  // working as a skill: nothing triggers, and the reader cannot tell whether
  // they mistyped it or the document is stale.
  const known = new Set(CATALOGUE)
  const dangling: string[] = []
  for (const { where, body } of skillProse()) {
    for (const [, name] of body.matchAll(/(?:^|[\s(`])\/([a-z][a-z0-9-]{2,})\b/g)) {
      if (!known.has(name)) dangling.push(`${where}: /${name}`)
    }
  }
  assert.deepEqual([...new Set(dangling)].sort(), [],
    `these name a skill the catalogue does not have:\n  ${[...new Set(dangling)].sort().join('\n  ')}`)
})

test('the notes template a workspace ships passes the lint /note declares mandatory', async () => {
  // `/note` calls the Evidence status line required, and the template omitted
  // it — so every notes file a new author starts from was missing the field
  // that stops an abstract-only source being cited as evidence.
  const { lintNotes } = await import(pathToFileURL(join(PRODUCT_ROOT, 'guards', 'dist', 'notes-lint.js')).href)
  const template = readFileSync(join(PRODUCT_ROOT, 'literature', 'reading_notes', '_template_NOTES.md'), 'utf8')
  const findings = lintNotes(template).map((f: { code: string; severity: string }) => `${f.severity}: ${f.code}`)
  assert.deepEqual(findings, [], `the shipped template does not satisfy its own linter:\n  ${findings.join('\n  ')}`)
})

test('a skill that instructs an interpreter is granted the tool that runs it', () => {
  // `/export` granted `Bash(python *)` while its body ran `python3`, so in a
  // host that honours the declaration the skill's own command is refused.
  const problems: string[] = []
  for (const name of CATALOGUE) {
    const body = readFileSync(join(SKILLS_SRC, name, 'SKILL.md'), 'utf8')
    const grant = /^allowed-tools:(.*)$/m.exec(body)?.[1] ?? ''
    const interpreters = new Set([...body.matchAll(/^\s*(python3|node|npm)\s+\S/gm)].map((m) => m[1]))
    if (interpreters.size === 0) continue
    if (!/\bBash\b/.test(grant)) {
      problems.push(`${name}: instructs ${[...interpreters].join(', ')} but grants no Bash`)
      continue
    }
    // A narrowed grant must cover what the body actually runs.
    for (const scoped of grant.matchAll(/Bash\(([^)]*)\)/g)) {
      const covers = [...interpreters].some((i) => scoped[1].trim().startsWith(i))
      if (!covers && !/^Bash\b(?!\()/.test(grant.trim())) {
        problems.push(`${name}: grants Bash(${scoped[1].trim()}) but instructs ${[...interpreters].join(', ')}`)
      }
    }
  }
  assert.deepEqual(problems, [], `frontmatter does not permit the skill's own commands:\n  ${problems.join('\n  ')}`)
})

test('a workspace config carries the chapter targets /map reports against', () => {
  // `/map`'s dashboard compares word counts to per-chapter targets. The
  // scaffolded config had none, so half of what the skill advertises had no
  // data source and the agent had to invent targets or silently drop them.
  //
  // Asserted against the file `init` actually writes. An earlier version of
  // this test parsed WORKSPACE_CONFIG out of the source with a non-greedy
  // match, which stopped at the first escaped backtick inside the template
  // literal and read 190 characters of a config several times that long.
  const parent = mkdtempSync(join(tmpdir(), 'awt-skill-text-'))
  try {
    const ws = join(parent, 'thesis')
    const res = spawnSync(process.execPath, [join(PRODUCT_ROOT, 'scaffold', 'awt.mjs'), 'init', ws],
      { encoding: 'utf8', timeout: 60_000 })
    assert.equal(res.status, 0, res.stderr)
    const config = readFileSync(join(ws, 'AGENTS.md'), 'utf8')
    assert.match(config, /target/i, 'the scaffolded workspace config names no chapter targets')
    assert.match(config, /\|\s*ch1\s*\|/, 'the targets are not a table /map can read')
  } finally {
    rmSync(parent, { recursive: true, force: true })
  }
})

test('the evidence-status values skills name are the ones the linter accepts', () => {
  // `/note` declares the field, the shipped template carries it, and
  // `/integrate` refuses to weave in a source that reports having been read
  // only in part. Three places naming one vocabulary is three places for it
  // to drift from the one that enforces it.
  const accepted = /const EVIDENCE_VALUES = \[([^\]]*)\]/
    .exec(readFileSync(join(PRODUCT_ROOT, 'guards', 'src', 'notes-lint.ts'), 'utf8'))?.[1]
  assert.ok(accepted, 'EVIDENCE_VALUES not found in the linter')
  const known = new Set([...accepted.matchAll(/'([a-z_]+)'/g)].map((m) => m[1]))

  const wrong: string[] = []
  for (const { where, body } of skillProse()) {
    for (const [, value] of body.matchAll(/Evidence status[`:\s]*([a-z_]{4,})/g)) {
      if (!known.has(value)) wrong.push(`${where}: ${value}`)
    }
  }
  assert.deepEqual(wrong, [], `these name a value the linter would reject:\n  ${wrong.join('\n  ')}`)
})

// Gate A item 5: yesterday's contract must not silently scope today's writes.
//
// A contract is "active" while it still carries an unchecked `- [ ] Attempt`
// line, and the skill's template ships three of them. So a contract is active
// from the moment it is written and stays active until the author ticks every
// box — which nothing told them to do. `activeContract()` then returned the
// FIRST active contract in readdir order, not the newest.
//
// The loop therefore worked on day one and denied on day two: chapter writes
// were scoped against a contract the author was not working under, and the
// denial said "the active edit contract" without naming which one, so there
// was nothing to act on.
//
// Two active contracts is not a state the guard can resolve. Picking one by
// directory order is a silent choice about what the author may edit, which is
// the kind of thing this product refuses rather than guesses.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { decideContractScope, type RepoView } from '../src/decisions.ts'

const PRODUCT_ROOT = resolve(import.meta.dirname, '..', '..')

function repo(overrides: Partial<RepoView> = {}): RepoView {
  return {
    relative: (p) => (p.startsWith('/') ? undefined : p),
    readFile: () => undefined,
    conformingSources: () => [],
    activeContracts: () => [],
    chapterFiles: () => [],
    bibText: () => undefined,
    ...overrides,
  } as RepoView
}

const YESTERDAY = { path: 'contracts/2026-09-06-ch3.md', mayChange: ['chapters/ch3.md'], mustNotChange: [] }
const TODAY = { path: 'contracts/2026-09-07-ch5.md', mayChange: ['chapters/ch5.md'], mustNotChange: [] }

test('two active contracts are a typed refusal, not a silent choice between them', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'x' } },
    repo({ activeContracts: () => [YESTERDAY, TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_AMBIGUOUS')
  // The author cannot retire one without being told which two.
  assert.match(d!.message, /2026-09-06-ch3\.md/)
  assert.match(d!.message, /2026-09-07-ch5\.md/)
})

test('the refusal comes before the scope decision, so it cannot be masked by an in-scope path', () => {
  // Writing inside YESTERDAY's scope would have passed silently while TODAY
  // was the contract the author believed they were working under.
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch3.md', content: 'x' } },
    repo({ activeContracts: () => [YESTERDAY, TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_AMBIGUOUS')
})

test('one active contract scopes as before, and the denial names it', () => {
  const d = decideContractScope(
    { tool: 'write', args: { file_path: 'chapters/ch9.md', content: 'x' } },
    repo({ activeContracts: () => [TODAY] }),
  )
  assert.equal(d?.code, 'CONTRACT_SCOPE')
  assert.match(d!.message, /2026-09-07-ch5\.md/, 'the denial must say which contract decided')
})

test('retiring one leaves the other in charge', () => {
  assert.equal(
    decideContractScope(
      { tool: 'write', args: { file_path: 'chapters/ch5.md', content: 'x' } },
      repo({ activeContracts: () => [TODAY] }),
    ),
    undefined,
  )
})

test('no active contract is still no scope restriction', () => {
  assert.equal(
    decideContractScope(
      { tool: 'write', args: { file_path: 'chapters/anything.md', content: 'x' } },
      repo({ activeContracts: () => [] }),
    ),
    undefined,
  )
})

test('the shipped contract template does not leave a finished contract active', async () => {
  // The template shipped three unchecked Attempt lines, so a contract stayed
  // active after the work was done and shadowed the next one. Whatever the
  // template ships, a contract written from it and then completed must be
  // retireable by the author without guessing how.
  const { parseContractSource } = await import(
    pathToFileURL(join(PRODUCT_ROOT, 'guards', 'dist', 'projections.js')).href
  )
  const skill = await import('node:fs').then((fs) =>
    fs.readFileSync(join(PRODUCT_ROOT, '.claude', 'skills', 'edit-contract', 'SKILL.md'), 'utf8'))
  const template = /```markdown\n([\s\S]*?)```/.exec(skill)?.[1]
  assert.ok(template, 'no contract template found in the skill')

  const unchecked = [...template.matchAll(/^- \[ \] Attempt/gm)].length
  assert.equal(unchecked, 1, `the template ships ${unchecked} pre-written attempts; a finished contract keeps every unticked one active`)
  assert.equal(parseContractSource(template).active, true, 'a fresh contract must be active')
  assert.equal(parseContractSource(template.replace('- [ ]', '- [x]')).active, false,
    'ticking the attempt must retire the contract')
  assert.match(skill, /retire|retiring/i, 'the skill must say how a contract is retired')
})

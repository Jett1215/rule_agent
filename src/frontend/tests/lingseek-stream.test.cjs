const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

function client(fetchEventSource) {
  const source = fs.readFileSync(path.join(__dirname, '../src/apis/lingseek.ts'), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', "''")
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const context = {
    exports: {}, AbortController,
    localStorage: { getItem: () => 'fake-token' },
    require: () => ({ fetchEventSource }),
  }
  vm.runInNewContext(compiled, context)
  return context.exports
}

const sseResponse = { ok: true, status: 200, headers: { get: () => 'text/event-stream; charset=utf-8' } }

test('LingSeek HTTP failure reports one error and never signals completion or retries', async () => {
  let errors = 0
  let completed = 0
  const api = client(async (_url, options) => {
    try {
      await options.onopen({ ok: false, status: 403, headers: { get: () => 'application/json' } })
    } catch (error) {
      options.onerror(error)
      assert.fail('onerror must throw to prevent fetch-event-source retry')
    }
  })
  await api.generateLingSeekGuidePromptAPI({ query: 'test' }, () => assert.fail('Unexpected message'), () => { errors++ }, () => { completed++ })
  assert.equal(errors, 1)
  assert.equal(completed, 0)
})

test('LingSeek external abort stops callbacks without reporting failure or completion', async () => {
  const controller = new AbortController()
  let callbacks = 0
  const api = client(async (_url, options) => {
    assert.equal(options.signal, controller.signal)
    await options.onopen(sseResponse)
    controller.abort()
    options.onmessage({ data: JSON.stringify({ data: { chunk: 'late chunk' } }) })
    options.onclose()
    throw new Error('aborted transport')
  })
  const callback = () => { callbacks++ }
  await api.generateLingSeekGuidePromptAPI({ query: 'test' }, callback, callback, callback, controller.signal)
  assert.equal(callbacks, 0)
})

test('LingSeek keeps guide, graph, step and final-answer event contracts', async () => {
  const received = []
  const api = client(async (_url, options) => {
    await options.onopen(sseResponse)
    for (const value of [
      { event: 'generate_tasks', data: { graph: [{ start: 'A', end: 'B' }] } },
      { event: 'step_result', data: { title: 'B', message: 'done' } },
      { event: 'task_result', data: { message: 'answer' } },
      { data: { chunk: 'chunk' } },
    ]) options.onmessage({ data: JSON.stringify(value) })
    options.onclose()
  })
  await api.startLingSeekTaskAPI({ query: 'test', guide_prompt: 'steps' },
    value => received.push(['chunk', value]),
    value => received.push(['graph', value]),
    value => received.push(['step', value]),
    value => received.push(['answer', value]),
    () => assert.fail('Unexpected stream error'),
    () => received.push(['close']))
  assert.deepEqual(JSON.parse(JSON.stringify(received)), [
    ['graph', [{ start: 'A', end: 'B' }]], ['step', { title: 'B', message: 'done' }],
    ['answer', 'answer'], ['chunk', 'chunk'], ['close'],
  ])
})

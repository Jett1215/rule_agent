const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

function client(fetchEventSource) {
  const source = fs.readFileSync(path.join(__dirname, '../src/apis/chat.ts'), 'utf8')
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
const settled = () => new Promise(resolve => setImmediate(resolve))

test('legacy Agent HTTP denial reports one failure without retry or false completion', async () => {
  let errors = 0
  let completed = 0
  const api = client(async (_url, options) => {
    try {
      await options.onopen({ ok: false, status: 403, headers: { get: () => 'application/json' } })
    } catch (error) {
      options.onerror(error)
      assert.fail('Retry must be stopped')
    }
  })
  api.sendMessage({ dialogId: 'old', userInput: 'test' }, () => {}, () => { completed++ }, () => { errors++ })
  await settled()
  assert.equal(errors, 1)
  assert.equal(completed, 0)
})

test('legacy Agent abort suppresses late text, close and rejection callbacks', async () => {
  let transport
  let reject
  let callbacks = 0
  const api = client(async (_url, options) => {
    transport = options
    await new Promise((_resolve, fail) => { reject = fail })
  })
  const callback = () => { callbacks++ }
  const controller = api.sendMessage({ dialogId: 'old', userInput: 'test' }, callback, callback, callback)
  controller.abort()
  assert.equal(transport.signal.aborted, true)
  transport.onmessage({ data: '{"type":"response_chunk","data":{"chunk":"late"}}' })
  transport.onclose()
  reject(new Error('Transport aborted'))
  await settled()
  assert.equal(callbacks, 0)
})

test('legacy Agent retains dialog and optional upload payload and streamed callback contract', async () => {
  const received = []
  const api = client(async (url, options) => {
    assert.equal(url, '/api/v1/completion')
    assert.deepEqual(JSON.parse(options.body), { dialog_id: 'old', user_input: 'test', file_url: 'fixture://upload' })
    await options.onopen({ ok: true, status: 200, headers: { get: () => 'text/event-stream' } })
    options.onmessage({ data: 'chunk' })
    options.onclose()
  })
  api.sendMessage({ dialogId: 'old', userInput: 'test', fileUrl: 'fixture://upload' }, value => received.push(value.data), () => received.push('done'), () => assert.fail('Unexpected failure'))
  await settled()
  assert.deepEqual(received, ['chunk', 'done'])
})

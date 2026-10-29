const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

function load(relativePath, dependencies = {}, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, relativePath), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', "''")
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const context = { exports: {}, require(name) { assert.ok(name in dependencies, `Unexpected dependency: ${name}`); return dependencies[name] }, ...globals }
  vm.runInNewContext(compiled, context)
  return context.exports
}
const config = load('../src/utils/workspace-config.ts')
const stream = load('../src/utils/workspace-stream.ts')
const plain = value => JSON.parse(JSON.stringify(value))

test('Agent defaults are copied and conversation overrides never mutate the Agent', () => {
  const agent = { agent_id: 'assistant', llm_id: 'model-a', tool_ids: ['weather'], mcp_ids: ['mcp-a'] }
  const selected = config.configFromAgent(agent)
  selected.plugins.length = 0
  selected.mcp_servers.push('mcp-b')
  selected.model_id = 'model-b'
  assert.deepEqual(agent, { agent_id: 'assistant', llm_id: 'model-a', tool_ids: ['weather'], mcp_ids: ['mcp-a'] })
})

test('restore the latest saved configuration including explicit empty tools and no Agent', () => {
  const contexts = [
    { config: { model_id: 'old', agent_id: 'assistant', plugins: ['weather'], mcp_servers: ['mcp-a'] } },
    { config: { model_id: 'new', agent_id: null, plugins: [], mcp_servers: [] } },
    { query: 'legacy context without config' },
  ]
  assert.deepEqual(plain(config.restoreConversationConfig(contexts)), { model_id: 'new', agent_id: null, plugins: [], mcp_servers: [] })
  assert.equal(config.restoreConversationConfig([{ query: 'legacy' }]), null)
})

test('daily stream preserves text, reasoning, MCP progress and Agent progress as distinct events', () => {
  assert.deepEqual(plain(stream.parseWorkspaceStreamMessage('{"event":"task_result","data":{"message":"回答"}}')), { kind: 'text', text: '回答' })
  assert.deepEqual(plain(stream.parseWorkspaceStreamMessage('{"event":"reasoning_chunk","data":{"chunk":"推理"}}')), { kind: 'reasoning', text: '推理' })
  assert.equal(stream.parseWorkspaceStreamMessage('{"event":"mcp_tool","data":{"id":"1","status":"START"}}').kind, 'mcp')
  assert.equal(stream.parseWorkspaceStreamMessage('{"event":"agent_event","data":{"title":"天气","status":"END"}}').kind, 'agent')
  assert.equal(stream.parseWorkspaceStreamMessage('').kind, 'ignore')
  assert.throws(() => stream.parseWorkspaceStreamMessage('{"event":"error","data":{"message":"生成失败"}}'), /生成失败/)
  assert.throws(() => stream.parseWorkspaceStreamMessage('broken json'))
})

function transport(fetchEventSource) {
  return load('../src/apis/workspace.ts', {
    '../utils/request': { request() { assert.fail('JSON request not expected') } },
    '@microsoft/fetch-event-source': { fetchEventSource },
    '../utils/workspace-stream': stream,
  }, { localStorage: { getItem() { return 'test-only-token' } } })
}

test('HTTP denial and non-SSE response fail once without closing as success or retrying', async () => {
  for (const response of [
    { ok: false, status: 403, headers: { get: () => 'application/json' } },
    { ok: true, status: 200, headers: { get: () => 'application/json' } },
  ]) {
    let attempts = 0, errors = 0, closes = 0
    const api = transport(async (_url, options) => {
      attempts++
      try { await options.onopen(response) } catch (error) { options.onerror(error) }
    })
    await assert.rejects(api.workspaceSimpleChatStreamAPI({}, () => assert.fail(), () => errors++, () => closes++))
    assert.equal(attempts, 1)
    assert.equal(errors, 1)
    assert.equal(closes, 0)
  }
})

test('business stream error rejects after partial text and never reports a successful close', async () => {
  const chunks = []
  let closed = false
  const api = transport(async (_url, options) => {
    options.onmessage({ data: '{"event":"task_result","data":{"message":"部分内容"}}' })
    options.onmessage({ data: '{"event":"error","data":{"message":"生成失败"}}' })
    options.onclose()
  })
  await assert.rejects(api.workspaceSimpleChatStreamAPI({}, text => chunks.push(text), undefined, () => { closed = true }), /生成失败/)
  assert.deepEqual(chunks, ['部分内容'])
  assert.equal(closed, false)
})

test('caller cancellation is passed to transport and does not become a request error', async () => {
  const controller = new AbortController()
  let errors = 0
  const api = transport(async (_url, options) => {
    assert.equal(options.signal, controller.signal)
    controller.abort()
    throw new Error('aborted')
  })
  await api.workspaceSimpleChatStreamAPI({}, () => assert.fail(), () => errors++, undefined, undefined, undefined, { signal: controller.signal })
  assert.equal(errors, 0)
})

test('a truncated EOF is a failure; only the persisted done event completes a conversation', async () => {
  for (const done of [false, true]) {
    let closes = 0
    const api = transport(async (_url, options) => {
      options.onmessage({ data: '{"event":"task_result","data":{"message":"回答"}}' })
      if (done) options.onmessage({ data: '{"event":"done","data":{"session_id":"test"}}' })
      options.onclose()
    })
    const request = api.workspaceSimpleChatStreamAPI({}, () => {}, undefined, () => closes++)
    if (done) await request
    else await assert.rejects(request, /连接已中断/)
    assert.equal(closes, done ? 1 : 0)
  }
})

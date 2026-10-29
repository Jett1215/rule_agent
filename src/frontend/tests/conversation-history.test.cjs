const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

function loadModule(filename, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '../src', filename), 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const context = { exports: {}, ...globals }
  vm.runInNewContext(compiled, context)
  return context.exports
}
const history = loadModule('utils/conversation-history.ts')
const plain = value => JSON.parse(JSON.stringify(value))

test('unified history retains same IDs from different stores and orders by update time', () => {
  const workspace = history.normalizeConversationHistory([
    { session_id: 'same', title: '日常问题', agent: 'simple', create_time: '2026-10-25', update_time: '2026-10-27' },
    { session_id: 'task', title: '灵寻任务', agent: 'lingseek', update_time: '2026-10-26' },
  ], 'workspace')
  const dialogs = history.normalizeConversationHistory([
    { dialog_id: 'same', name: '已有助手', update_time: '2026-10-28' },
  ], 'dialog')
  const merged = history.mergeConversationHistory(workspace, dialogs)
  assert.deepEqual(plain(merged.map(entry => entry.key)), ['dialog:same', 'workspace:same', 'workspace:task'])
  assert.deepEqual(plain(merged.map(entry => entry.mode)), ['normal', 'normal', 'lingseek'])
  assert.equal(workspace[0].key, 'workspace:same', 'sorting must not mutate source order')
})

test('legacy workspace tasks and invalid records have deterministic fallbacks', () => {
  const records = history.normalizeConversationHistory([
    null, 'invalid', {}, { session_id: 42 },
    { id: 'legacy', title: '', created_at: 'invalid-date' },
    { session_id: 'simple', agent: 'simple', title: '普通' },
  ], 'workspace')
  assert.equal(records.length, 2)
  assert.equal(records[0].mode, 'lingseek')
  assert.equal(records[0].title, '未命名会话')
  assert.equal(history.normalizeConversationHistory(null, 'dialog').length, 0)
  assert.deepEqual(plain(history.mergeConversationHistory(records).map(entry => entry.id)), ['legacy', 'simple'])
})

test('history selection routes each storage source to its original continuation path', () => {
  const daily = history.normalizeConversationHistory([{ session_id: 'd', agent: 'simple' }], 'workspace')[0]
  const task = history.normalizeConversationHistory([{ session_id: 't', agent: 'lingseek' }], 'workspace')[0]
  const agent = history.normalizeConversationHistory([{ dialog_id: 'a' }], 'dialog')[0]
  assert.deepEqual(plain(history.conversationLocation(daily)), { name: 'workspaceDefaultPage', query: { session_id: 'd', mode: 'normal' } })
  assert.deepEqual(plain(history.conversationLocation(task)), { name: 'taskGraphPage', query: { session_id: 't' } })
  assert.deepEqual(plain(history.conversationLocation(agent)), { name: 'chatPage', query: { dialog_id: 'a' } })
  assert.equal(history.selectedConversationKey({ dialog_id: 'd' }), 'dialog:d')
  assert.equal(history.selectedConversationKey({ session_id: 'd' }), 'workspace:d')
  assert.equal(history.selectedConversationKey({ session_id: ['invalid'] }), '')
})

test('existing and merged URLs resolve with the same components, query and authentication', async () => {
  const vueRouter = require('vue-router')
  const components = new Map()
  const router = loadModule('router/index.ts', {
    require(name) {
      if (name === 'vue-router') return { ...vueRouter, createWebHistory: vueRouter.createMemoryHistory }
      if (!components.has(name)) components.set(name, { name })
      return { default: components.get(name), Register: components.get(name) }
    },
    localStorage: { getItem: () => 'test-token' },
  }).default
  for (const [legacy, canonical] of [
    ['/workspace?session_id=existing', '/conversation?session_id=existing'],
    ['/workspace/workspacePage?session_id=old-task', '/conversation/workspacePage?session_id=old-task'],
    ['/workspace/taskGraph?session_id=task', '/conversation/taskGraph?session_id=task'],
  ]) {
    const oldRoute = router.resolve(legacy)
    const newRoute = router.resolve(canonical)
    assert.equal(oldRoute.name, newRoute.name)
    assert.equal(oldRoute.matched.at(-1).components.default, newRoute.matched.at(-1).components.default)
    assert.deepEqual(plain(oldRoute.query), plain(newRoute.query))
    assert.equal(oldRoute.meta.requiresAuth, true)
  }
  assert.equal(router.resolve('/conversation/chatPage?dialog_id=old-agent').name, 'chatPage')
  assert.equal(router.resolve('/conversation/chatPage').meta.current, 'conversation')
  await router.push('/')
  assert.equal(router.currentRoute.value.path, '/conversation')
})

test('a slow previous Agent history response cannot overwrite the newly selected dialog', async () => {
  const { createPinia, setActivePinia } = require('pinia')
  setActivePinia(createPinia())
  const pending = new Map()
  const { useHistoryChatStore } = loadModule('store/history_chat_msg/index.ts', {
    require(name) {
      if (name === '../../apis/history') return {
        getHistoryMsgAPI: id => new Promise(resolve => pending.set(id, resolve)),
      }
      if (name === 'element-plus') return { ElMessage: { error: () => {} } }
      return require(name)
    },
  })
  const store = useHistoryChatStore()
  const oldRequest = store.HistoryChat('old')
  const newRequest = store.HistoryChat('new')
  pending.get('new')({ data: { status_code: 200, data: [
    { role: 'user', content: 'new question' }, { role: 'assistant', content: 'new answer' },
  ] } })
  await newRequest
  pending.get('old')({ data: { status_code: 200, data: [
    { role: 'user', content: 'old question' }, { role: 'assistant', content: 'old answer' },
  ] } })
  await oldRequest
  assert.equal(store.chatArr.length, 1)
  assert.equal(store.chatArr[0].aiMessage.content, 'new answer')
  assert.equal(store.loading, false)
})

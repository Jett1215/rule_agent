const assert = require('node:assert/strict')
const { webcrypto } = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/utils/session-id.ts'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText

function generator(cryptoApi) {
  const context = { crypto: cryptoApi, exports: {} }
  vm.runInNewContext(compiled, context)
  return context.exports.generateSessionId
}

test('public HTTP can create sessions without crypto.randomUUID', () => {
  const createId = generator({ getRandomValues: webcrypto.getRandomValues.bind(webcrypto) })
  const ids = Array.from({ length: 100 }, createId)
  for (const id of ids) {
    assert.match(id, /^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$/)
  }
  assert.equal(new Set(ids).size, ids.length)
})

test('HTTPS keeps the native UUID implementation and the same session ID format', () => {
  const cryptoApi = {
    randomUUID() {
      assert.equal(this, cryptoApi)
      return 'd779b55a-bd63-4ca0-a9ad-6278cf8b6051'
    },
    getRandomValues() {
      assert.fail('Native UUID support should not need the fallback')
    },
  }
  assert.equal(generator(cryptoApi)(), 'd779b55abd634ca0a9ad6278cf8b6051')
})

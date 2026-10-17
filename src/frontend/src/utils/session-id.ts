// Match Python uuid4().hex, including when the site is served over public HTTP.
export const generateSessionId = (): string => {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID().replace(/-/g, '')
  }

  // getRandomValues is also available outside a secure context.
  const bytes = cryptoApi.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
}

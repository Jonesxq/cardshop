import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../api/adminConsole', () => ({
  fetchAdminMe: vi.fn(async () => ({
    id: 1,
    email: 'operator@example.com',
    role: 'operator',
    permissions: { can_manage_orders: true },
  })),
}))

import { fetchAdminMe } from '../api/adminConsole'
import { useAdminSessionStore } from './adminSession'

describe('admin session store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const storage = new Map()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => storage.get(key) || null),
      setItem: vi.fn((key, value) => storage.set(key, String(value))),
      removeItem: vi.fn((key) => storage.delete(key)),
    })
    localStorage.setItem('access_token', 'token-one')
  })

  it('loads admin identity once and stores permissions', async () => {
    const store = useAdminSessionStore()

    await store.load()

    expect(fetchAdminMe).toHaveBeenCalledTimes(1)
    expect(store.user.email).toBe('operator@example.com')
    expect(store.role).toBe('operator')
    expect(store.permissions.can_manage_orders).toBe(true)
  })

  it('uses cached identity unless force is requested', async () => {
    const store = useAdminSessionStore()

    await store.load()
    await store.load()
    await store.load({ force: true })

    expect(fetchAdminMe).toHaveBeenCalledTimes(2)
  })

  it('reloads admin identity when the access token changes', async () => {
    const store = useAdminSessionStore()

    await store.load()
    expect(store.accessToken).toBe('token-one')

    localStorage.setItem('access_token', 'token-two')
    await store.load()

    expect(fetchAdminMe).toHaveBeenCalledTimes(2)
    expect(store.accessToken).toBe('token-two')
  })

  it('clears the cached access token on reset', async () => {
    const store = useAdminSessionStore()

    await store.load()
    store.reset()

    expect(store.accessToken).toBe('')
  })
})

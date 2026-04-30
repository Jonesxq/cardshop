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
})

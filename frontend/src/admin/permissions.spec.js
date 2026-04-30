import { describe, expect, it } from 'vitest'

import { adminMenusForSession, canUseAdminAction } from './permissions'

describe('admin permissions', () => {
  it('shows operator operations menus and announcement content but hides finance and staff menus', () => {
    const session = {
      role: 'operator',
      permissions: {
        can_manage_orders: true,
        can_manage_products: true,
        can_manage_inventory: true,
        can_view_payments: false,
        can_manage_users: false,
        can_view_logs: true,
      },
    }

    const keys = adminMenusForSession(session).map((item) => item.key)

    expect(keys).toContain('orders')
    expect(keys).toContain('inventory')
    expect(keys).toContain('logs')
    expect(keys).toContain('content')
    expect(keys).not.toContain('payments')
    expect(keys).not.toContain('users')
    expect(canUseAdminAction(session, 'can_manage_inventory')).toBe(true)
  })

  it('shows content menu to settings managers', () => {
    const session = {
      role: 'superadmin',
      permissions: {
        can_manage_settings: true,
      },
    }

    const keys = adminMenusForSession(session).map((item) => item.key)

    expect(keys).toContain('content')
  })

  it('hides content menu without announcement or settings permissions', () => {
    const session = {
      role: 'finance',
      permissions: {
        can_manage_products: false,
        can_manage_settings: false,
      },
    }

    const keys = adminMenusForSession(session).map((item) => item.key)

    expect(keys).not.toContain('content')
  })
})

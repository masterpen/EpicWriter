import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getToken, setToken, clearAuth } from '../api'

// localStorage mock — jsdom 提供了 localStorage，但我们需要在每个测试前清空
describe('api token 管理', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('getToken', () => {
    it('未设置 token 时返回 null', () => {
      expect(getToken()).toBeNull()
    })

    it('设置后返回 token', () => {
      setToken('my-jwt-token')
      expect(getToken()).toBe('my-jwt-token')
    })
  })

  describe('setToken', () => {
    it('存储 token 到 localStorage', () => {
      setToken('abc123')
      expect(localStorage.getItem('epicwriter_token')).toBe('abc123')
    })

    it('传入 null 时移除 token', () => {
      setToken('abc123')
      setToken(null)
      expect(localStorage.getItem('epicwriter_token')).toBeNull()
    })
  })

  describe('clearAuth', () => {
    it('清除已存储的 token', () => {
      setToken('will-be-cleared')
      clearAuth()
      expect(getToken()).toBeNull()
    })

    it('未设置 token 时也不报错', () => {
      expect(() => clearAuth()).not.toThrow()
    })
  })
})

describe('fetchApi 注入 Authorization 头', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('有 token 时请求头包含 Bearer token', async () => {
    setToken('test-bearer-token')

    // 捕获 fetch 调用的 headers
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    // 动态导入以获取已设置的 token
    const { api } = await import('../api')
    await api.getAllBooks()

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const [, init] = fetchSpy.mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer test-bearer-token')

    fetchSpy.mockRestore()
  })

  it('无 token 时请求头不含 Authorization', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const { api } = await import('../api')
    await api.getAllBooks()

    const [, init] = fetchSpy.mock.calls[0]
    const headers = init?.headers as Record<string, string>
    expect(headers['Authorization']).toBeUndefined()

    fetchSpy.mockRestore()
  })

  it('响应非 2xx 时抛出包含 detail 的错误', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const { api } = await import('../api')
    await expect(api.getBook('123')).rejects.toThrow('Not found')

    fetchSpy.mockRestore()
  })
})

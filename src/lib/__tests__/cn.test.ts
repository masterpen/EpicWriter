import { describe, it, expect } from 'vitest'
import { cn } from '../cn'

describe('cn (className utility)', () => {
  it('合并多个字符串', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('过滤 falsy 值 (false/null/undefined/空串)', () => {
    expect(cn('foo', false, null, undefined, '', 'bar')).toBe('foo bar')
  })

  it('处理条件对象', () => {
    expect(cn({ active: true, disabled: false })).toBe('active')
  })

  it('混合字符串与条件对象', () => {
    expect(cn('btn', { primary: true, large: false })).toBe('btn primary')
  })

  it('空输入返回空字符串', () => {
    expect(cn()).toBe('')
  })

  it('Tailwind 冲突类名后者覆盖前者', () => {
    // twMerge 应让后写的 px-4 覆盖 px-2
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })

  it('Tailwind 非冲突类名全部保留', () => {
    expect(cn('text-red-500', 'font-bold')).toBe('text-red-500 font-bold')
  })

  it('嵌套数组展平', () => {
    expect(cn(['foo', ['bar', 'baz']])).toBe('foo bar baz')
  })
})

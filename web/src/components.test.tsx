import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { EngineBanner, StatusPicker, ThemeToggle, VerdictBadge } from './components'

describe('ThemeToggle', () => {
  it('follows the device until a theme is picked, then remembers it', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: 'Match device' })).toHaveProperty('ariaChecked', 'true')

    fireEvent.click(screen.getByRole('radio', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')

    fireEvent.click(screen.getByRole('radio', { name: 'Match device' }))
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('starts from the saved choice', () => {
    localStorage.setItem('theme', 'light')
    render(<ThemeToggle />)
    expect(screen.getByRole('radio', { name: 'Light' })).toHaveProperty('ariaChecked', 'true')
  })
})

describe('StatusPicker', () => {
  it('reports the status picked', () => {
    const onChange = vi.fn()
    render(<StatusPicker value="h1b" onChange={onChange} />)
    expect(screen.getByRole('radio', { name: 'Needs H-1B' })).toHaveProperty('ariaChecked', 'true')
    fireEvent.click(screen.getByRole('radio', { name: 'EAD' }))
    expect(onChange).toHaveBeenCalledWith('ead')
  })
})

describe('VerdictBadge', () => {
  it('always shows the verdict in words, not only color', () => {
    render(<VerdictBadge label="blocked" />)
    expect(screen.getByText('Blocked')).toBeTruthy()
  })
})

describe('EngineBanner', () => {
  it('says nothing while live', () => {
    const { container } = render(<EngineBanner state="live" />)
    expect(container.textContent).toBe('')
  })

  it('explains why recordings are shown', () => {
    const { rerender } = render(<EngineBanner state="waking" recorded="2026-10-28" />)
    expect(screen.getByRole('status').textContent).toMatch(/Waking the engine/)
    rerender(<EngineBanner state="ended" />)
    expect(screen.getByRole('status').textContent).toMatch(/live demo ended after hackathon judging/)
    rerender(<EngineBanner state="offline" />)
    expect(screen.getByRole('status').textContent).toMatch(/can't be reached/)
  })
})

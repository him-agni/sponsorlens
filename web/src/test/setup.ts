import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  localStorage.clear()
  delete document.documentElement.dataset.theme
  window.history.replaceState(null, '', '/')
})

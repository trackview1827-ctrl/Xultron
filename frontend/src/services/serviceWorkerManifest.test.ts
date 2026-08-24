import { describe, expect, it } from 'vitest'
import { serviceWorkerSource } from './serviceWorkerManifest'

describe('service worker build manifest', () => {
  it('injects every hashed asset into the install-time shell and derives a new cache version', () => {
    const assets = ['assets/index-ui123.css', 'assets/index-code456.js']
    const source = serviceWorkerSource(assets)
    expect(source).toContain('const BUILD_ASSETS = ["/assets/index-ui123.css","/assets/index-code456.js"]')
    expect(source).toContain("const CACHE = 'xultron-shell-indexui123css-indexcode456js'")
    expect(source).toContain('cache.addAll(SHELL)')
    for (const asset of assets) expect(source).toContain(`/${asset}`)
  })
})

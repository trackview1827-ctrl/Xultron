import { describe, expect, it, vi } from 'vitest'
import { tasksApi } from './tasksApi'

describe('tasksApi', () => {
  it('sends custom instructions as task creation payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ task: { id: 'tsk_1' } }), { status: 201 })))
    const result = await tasksApi.create('Research', 'Use only approved sources')
    expect(result.task.id).toBe('tsk_1')
    expect(fetch).toHaveBeenCalledWith('/api/v1/tasks', expect.objectContaining({ body: JSON.stringify({ title: 'Research', instruction: 'Use only approved sources' }) }))
    vi.unstubAllGlobals()
  })
})

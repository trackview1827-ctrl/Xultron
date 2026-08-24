import { useEffect, useState } from 'react'
import type { DataUsage } from '../types'
import { getDataUsage, subscribeDataUsage } from '../services/apiClient'

export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => { const on = () => setOnline(true); const off = () => setOnline(false); addEventListener('online', on); addEventListener('offline', off); return () => { removeEventListener('online', on); removeEventListener('offline', off) } }, [])
  return online
}

export function useDataUsage(): DataUsage {
  const [usage, setUsage] = useState(getDataUsage)
  useEffect(() => subscribeDataUsage(setUsage), [])
  return usage
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(2)} MB`
}

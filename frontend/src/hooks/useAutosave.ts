import { useEffect, useRef } from 'react'
import { useAppStore } from '../store/useAppStore'

export function useAutosave() {
  const papersCount = useAppStore((s) => s.papers.length)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    if (papersCount === 0) return

    intervalRef.current = setInterval(() => {
      useAppStore.getState().autosave()
    }, 60000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [papersCount])
}

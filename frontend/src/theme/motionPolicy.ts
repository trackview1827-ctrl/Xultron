export interface MotionPreferences {
  reducedMotion: boolean
  lowDataMode: boolean
}

export function conservesMotion(preferences: MotionPreferences): boolean {
  return preferences.reducedMotion || preferences.lowDataMode
}

export function timelineScrollBehavior(preferences: MotionPreferences): ScrollBehavior {
  return conservesMotion(preferences) ? 'auto' : 'smooth'
}

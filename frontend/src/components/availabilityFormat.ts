/** Чистые функции форматирования доступности — без React, чтобы их можно было тестировать. */

export const WEEKDAYS = [0, 1, 2, 3, 4]
export const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]

export const DayNamesShort = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] as const

export interface AvailLike {
  day_of_week: number
  start_time: string
  end_time: string
}

export function sameDays(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort((x, y) => x - y)
  const sb = [...b].sort((x, y) => x - y)
  return sa.every((v, i) => v === sb[i])
}

/** Пн–Пт, Сб–Вс, Пн, Ср — вместо «Понедельник, Вторник, ...». */
export function dayRanges(days: number[]): string {
  const sorted = [...new Set(days)].sort((a, b) => a - b)
  const parts: string[] = []
  let i = 0
  while (i < sorted.length) {
    let j = i
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j += 1
    const from = sorted[i]
    const to = sorted[j]
    parts.push(from === to ? DayNamesShort[from] : `${DayNamesShort[from]}–${DayNamesShort[to]}`)
    i = j + 1
  }
  return parts.join(', ')
}

/**
 * Описание доступности — по строке на набор дней.
 * Раньше окна склеивались запятыми в одну простыню («Пн 08:00–21:00, 08:00–12:00,
 * ... · Вс ...»), в которой невозможно ничего разобрать.
 */
export function describeWindow(items: AvailLike[]): string[] {
  const byDay = new Map<number, string[]>()
  for (const item of items) {
    const list = byDay.get(item.day_of_week) ?? []
    const window = `${item.start_time}–${item.end_time}`
    if (!list.includes(window)) list.push(window)
    list.sort((a, b) => a.localeCompare(b))
    byDay.set(item.day_of_week, list)
  }
  const groups = new Map<string, number[]>()
  for (const [day, windows] of byDay) {
    const signature = windows.join(', ')
    groups.set(signature, [...(groups.get(signature) ?? []), day])
  }
  return [...groups.entries()]
    .sort((a, b) => a[1][0] - b[1][0])
    .map(([signature, days]) => `${dayRanges(days)} — ${signature}`)
}

/** Сколько чипов рисовать до ограничения: сотни чипов подвешивают страницу. */
export const MAX_CHIPS = 40

export function clampChips<T>(items: T[], max: number = MAX_CHIPS): { visible: T[]; hidden: number } {
  return { visible: items.slice(0, max), hidden: Math.max(0, items.length - max) }
}

/**
 * Переключение дня в мультивыборе. Возвращает новый массив без дублей,
 * по возрастанию; последний снятый день даёт пустой массив.
 */
export function toggleDay(selected: number[], day: number): number[] {
  const next = selected.includes(day) ? selected.filter((d) => d !== day) : [...selected, day]
  return [...new Set(next)].sort((a, b) => a - b)
}
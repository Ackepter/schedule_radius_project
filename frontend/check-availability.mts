// Проверка чистых функций форматирования на реальных данных backup-2026-10-02.json
import { existsSync, readFileSync } from 'node:fs'
import {
  clampChips,
  dayRanges,
  describeWindow,
  sameDays,
  toggleDay,
  WEEKDAYS,
} from './src/components/availabilityFormat.ts'

const BACKUP = 'C:/Users/Ackepter/Downloads/backup-2026-10-02.json'
// бэкап нужен только для показа на реальных данных; без него проверки
// форматирования всё равно выполняются на синтетическом эквиваленте
const backup = existsSync(BACKUP)
  ? JSON.parse(readFileSync(BACKUP, 'utf-8'))
  : { teachers: [{ availability: Array.from({ length: 7 }, (_, d) => ({ day_of_week: d, start_time: '08:00', end_time: '21:00' })) }] }
if (!existsSync(BACKUP)) console.log(`backup не найден (${BACKUP}), используется синтетический набор\n`)

let failed = 0
function check(name: string, actual: unknown, expected: unknown) {
  const a = JSON.stringify(actual)
  const e = JSON.stringify(expected)
  const ok = a === e
  if (!ok) failed += 1
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}`)
  if (!ok) console.log(`     получено: ${a}\n     ожидалось: ${e}`)
}

// ── данные бэкапа: 7 дней 08:00–21:00 у каждого педагога ──────────────────
const teacher = backup.teachers[0]
const items = teacher.availability.map((a: any, i: number) => ({ id: i, ...a }))

const lines = describeWindow(items)
console.log('\nОписание доступности педагога:')
for (const l of lines) console.log('   ' + l)
console.log('')

// было бы: "Пн 08:00–21:00 · Вт 08:00–21:00 · ... · Вс 08:00–21:00"
check('одна строка на одинаковые дни', lines.length, 1)
check('диапазон Пн–Вс', lines[0], 'Пн–Вс — 08:00–21:00')
check('нет запятой-простыни', lines[0].includes('·'), false)

// ── два разных набора окон (реальный случай «много запятых») ───────────────
const messy = [
  ...[0, 1, 2, 3, 4, 5, 6].map((d) => ({ id: d, day_of_week: d, start_time: '08:00', end_time: '21:00' })),
  ...[0, 1, 2, 3, 4].map((d) => ({ id: 100 + d, day_of_week: d, start_time: '09:00', end_time: '18:00' })),
]
const messyLines = describeWindow(messy)
console.log('Два набора окон:')
for (const l of messyLines) console.log('   ' + l)
console.log('')
check('два набора -> две строки', messyLines.length, 2)
check('Пн–Пт с двумя окнами', messyLines[0], 'Пн–Пт — 08:00–21:00, 09:00–18:00')
check('Сб–Вс с одним окном', messyLines[1], 'Сб–Вс — 08:00–21:00')

// ── дубликаты схлопываются ────────────────────────────────────────────────
const dupes = [
  { id: 1, day_of_week: 0, start_time: '09:00', end_time: '18:00' },
  { id: 2, day_of_week: 0, start_time: '09:00', end_time: '18:00' },
  { id: 3, day_of_week: 0, start_time: '09:00', end_time: '18:00' },
]
check('дубликаты не размножаются в тексте', describeWindow(dupes), ['Пн — 09:00–18:00'])

// ── дни ───────────────────────────────────────────────────────────────────
check('ручной выбор: Пн–Пт снять Пт', toggleDay(WEEKDAYS, 4), [0, 1, 2, 3])
check('ручной выбор: добавить Сб', toggleDay([0, 1, 2, 3, 4], 5), [0, 1, 2, 3, 4, 5])
check('снять последний день -> пусто', toggleDay([2], 2), [])
check('повторный клик возвращает день', toggleDay(toggleDay([0], 0), 0), [0])
check('двойной клик не оставляет дублей', toggleDay([0, 0], 0), [])
check('порядок по возрастанию', toggleDay([3], 0), [0, 3])
check('дни без дублей даже при повторе', toggleDay([0, 0], 1), [0, 1])

check('Пн–Пт -> Пн–Пт', dayRanges([0, 1, 2, 3, 4]), 'Пн–Пт')
check('разреженные дни', dayRanges([0, 2, 3, 6]), 'Пн, Ср–Чт, Вс')
check('один день', dayRanges([5]), 'Сб')
check('выходные', dayRanges([5, 6]), 'Сб–Вс')
check('все дни', dayRanges([0, 1, 2, 3, 4, 5, 6]), 'Пн–Вс')
check('дни не по порядку', dayRanges([4, 0, 3, 1, 2]), 'Пн–Пт')
check('пусто', dayRanges([]), '')
check('с дублями', dayRanges([1, 1, 1]), 'Вт')

// ── пресеты ───────────────────────────────────────────────────────────────
check('пресет Пн–Пт совпадает с ручным выбором', sameDays(WEEKDAYS, [4, 0, 3, 1, 2]), true)
check('разные наборы не равны', sameDays(WEEKDAYS, [0, 1, 2, 3]), false)

// ── ограничение чипов ─────────────────────────────────────────────────────
const many = Array.from({ length: 500 }, (_, i) => ({
  id: i,
  day_of_week: i % 7,
  start_time: '09:00',
  end_time: '18:00',
}))
const clamped = clampChips(many)
check('чипов не больше лимита', clamped.visible.length, 40)
check('остаток посчитан', clamped.hidden, 460)

console.log(failed === 0 ? '\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ' : `\nПРОВАЛОВ: ${failed}`)
process.exit(failed === 0 ? 0 : 1)
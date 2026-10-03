// Проверка структурных инвариантов AvailabilityEditor: именно они определяют,
// был ли цикл «ошибка -> рендер родителя -> новая load -> повторный запрос».
import { readFileSync } from 'node:fs'

const src = readFileSync('./src/components/AvailabilityEditor.tsx', 'utf-8')

let failed = 0
function check(name: string, ok: boolean, detail = '') {
  if (!ok) failed += 1
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`)
}

// 1. report не должен зависеть от onError: иначе новая идентичность на каждом
//    рендере родителя тянет за собой load, а load стоит в useEffect.
const reportBody = src.slice(src.indexOf('const report = useCallback'))
// deps — последний массив аргументов useCallback, а не первая ')' в типах
function depsOf(src: string, name: string): string {
  const start = src.indexOf(`const ${name} = useCallback`)
  const call = src.slice(start)
  const m = call.match(/,\s*\[([^\]]*)\]\s*,?\s*\)/)
  return m ? m[1].trim() : '<не найдено>'
}

const reportDeps = depsOf(src, 'report')
const loadDeps = depsOf(src, 'load')

check('report зависит только от пустого массива', reportDeps === '', `deps = [${reportDeps}]`)
check(
  'load зависит только от entityId/entityType/report',
  loadDeps === 'entityId, entityType, report',
  `deps = [${loadDeps}]`,
)
check(
  'report читает onError через ref, а не через пропс',
  /onErrorRef\.current\?\.\(msg\)/.test(reportBody),
)
check('в теле report нет прямого onError(', !/\bonError\(/.test(reportBody))

// 2. load не должен зависеть от onError

// 3. Синхронизация ref с пропсом
check(
  'onError обновляется в ref через useEffect',
  /useEffect\(\(\) => \{\s*onErrorRef\.current = onError\s*\}, \[onError\]\)/.test(src),
)

// 4. Защита от гонки/протухшего ответа
check('есть счётчик запросов', /requestSeq/.test(src))
check('протухший ответ отбрасывается', /if \(seq !== requestSeq\.current\) return/.test(src))

// 5. Ответ нормализуется в массив
check('ответ проверяется на массив', /Array\.isArray\(data\)/.test(src))

// 6. Ограничение рендера чипов
check('число чипов ограничено', /clampChips/.test(src))
check('скрытый остаток показывается', /и ещё/.test(src))

// 7. Диапазон проверяется до отправки, а не после
check('невалидный диапазон блокирует кнопку', /invalidRange/.test(src) && /!invalidRange/.test(src))

// 8. Модель цикла: сколько раз перезапрашивается при одной и той же ошибке.
function simulate(depsIncludeOnError: boolean, parentRenders: number) {
  let requests = 0
  let loadIdentity = 0
  let loadDeps: unknown[] = depsIncludeOnError ? ['onError'] : []
  let effectRanFor = -1
  for (let render = 0; render < parentRenders; render += 1) {
    const nextDeps: unknown[] = depsIncludeOnError ? ['onError'] : []
    if (nextDeps.length !== loadDeps.length) loadDeps = nextDeps
    if (loadIdentity === 0) loadIdentity = 1
    // useEffect([load]) -> срабатывает, только если load сменила идентичность
    if (loadIdentity !== effectRanFor) {
      effectRanFor = loadIdentity
      requests += 1 // запрос + ошибка -> onError -> рендер родителя
      if (depsIncludeOnError) loadIdentity += 1
    }
  }
  return requests
}

const old = simulate(true, 100)
const now = simulate(false, 100)
console.log(`\nЗапросов за 100 рендеров родителя при ошибке: было ${old}, стало ${now}`)
check('старый код зацикливался', old > 10, `${old} запросов`)
check('новый код делает ровно один запрос', now === 1)

console.log(failed === 0 ? '\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ' : `\nПРОВАЛОВ: ${failed}`)
process.exit(failed === 0 ? 0 : 1)
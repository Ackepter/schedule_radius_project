import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControlLabel,
  Snackbar,
  Switch,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import api from '../api/client'
import type { Availability as AvailType, EntityType, OptimizerSettings } from '../api/types'
import { DayNames, DayNamesFull } from '../api/types'

const WEEKDAYS = [0, 1, 2, 3, 4]
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]

interface DayPreset {
  label: string
  days: number[]
}

const PRESETS: DayPreset[] = [
  { label: 'Пн–Пт', days: WEEKDAYS },
  { label: 'Пн–Сб', days: [0, 1, 2, 3, 4, 5] },
  { label: 'Вся неделя', days: ALL_DAYS },
  { label: 'Выходные', days: [5, 6] },
  { label: 'Пн–Чт', days: [0, 1, 2, 3] },
]

interface Props {
  entityType: EntityType
  entityId: number | null
  defaultStart?: string
  defaultEnd?: string
  /** Куда сообщать об ошибках — родитель обычно показывает свой Snackbar. */
  onError?: (message: string) => void
}

function pad(h: number): string {
  return `${String(h).padStart(2, '0')}:00`
}

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return (h || 0) * 60 + (m || 0)
}

function sameDays(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort((x, y) => x - y)
  const sb = [...b].sort((x, y) => x - y)
  return sa.every((v, i) => v === sb[i])
}

function describeWindow(items: AvailType[]): string {
  const byDay = new Map<number, AvailType[]>()
  for (const item of items) {
    const list = byDay.get(item.day_of_week) ?? []
    list.push(item)
    byDay.set(item.day_of_week, list)
  }
  return [...byDay.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([day, list]) => {
      const windows = list
        .slice()
        .sort((a, b) => a.start_time.localeCompare(b.start_time))
        .map((w) => `${w.start_time}–${w.end_time}`)
        .join(', ')
      return `${DayNames[day]} ${windows}`
    })
    .join(' · ')
}

/**
 * Редактор доступности: один интервал можно заполнить сразу на несколько дней
 * недели (например, Пн–Пт 08:00–19:00), либо точечно по одному дню.
 */
export default function AvailabilityEditor({
  entityType,
  entityId,
  defaultStart = '09:00',
  defaultEnd = '18:00',
  onError,
}: Props) {
  const [items, setItems] = useState<AvailType[]>([])
  const [selectedDays, setSelectedDays] = useState<number[]>(WEEKDAYS)
  const [start, setStart] = useState(defaultStart)
  const [end, setEnd] = useState(defaultEnd)
  const [replace, setReplace] = useState(false)
  const [saving, setSaving] = useState(false)
  const [windowHours, setWindowHours] = useState<{ from: string; to: string } | null>(null)
  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false,
    msg: '',
    severity: 'success',
  })

  const report = useCallback(
    (msg: string, severity: 'success' | 'error') => {
      if (severity === 'error' && onError) onError(msg)
      setSnackbar({ open: true, msg, severity })
    },
    [onError],
  )

  const load = useCallback(async () => {
    if (!entityId) {
      setItems([])
      return
    }
    try {
      const res = await api.get(
        `/availabilities?entity_type=${entityType}&entity_id=${entityId}`,
      )
      setItems(res.data as AvailType[])
    } catch {
      setItems([])
      report('Ошибка загрузки доступности', 'error')
    }
  }, [entityId, entityType, report])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    let cancelled = false
    api
      .get('/optimizer-settings')
      .then((res) => {
        if (cancelled) return
        const s = res.data as OptimizerSettings
        setWindowHours({ from: pad(s.early_hour), to: pad(s.late_hour) })
      })
      .catch(() => {
        /* настройки ещё не созданы — предупреждение не показываем */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const outsideWindow =
    windowHours !== null &&
    (toMinutes(start) < toMinutes(windowHours.from) || toMinutes(end) > toMinutes(windowHours.to))

  const sortedItems = useMemo(
    () =>
      items
        .slice()
        .sort((a, b) => a.day_of_week - b.day_of_week || a.start_time.localeCompare(b.start_time)),
    [items],
  )

  const daysLabel = useMemo(() => {
    if (selectedDays.length === 0) return 'дни не выбраны'
    return [...selectedDays]
      .sort((a, b) => a - b)
      .map((d) => DayNamesFull[d])
      .join(', ')
  }, [selectedDays])

  const activePreset = useMemo(
    () => PRESETS.find((p) => sameDays(p.days, selectedDays))?.label ?? null,
    [selectedDays],
  )

  const canSubmit = entityId !== null && selectedDays.length > 0 && !saving

  const toggleDay = (_e: React.MouseEvent<HTMLElement>, value: number | null) => {
    if (value === null) return
    setSelectedDays((prev) =>
      prev.includes(value) ? prev.filter((d) => d !== value) : [...prev, value].sort((a, b) => a - b),
    )
  }

  const addBulk = async () => {
    if (!entityId) return
    if (selectedDays.length === 0) {
      report('Выберите хотя бы один день недели', 'error')
      return
    }
    if (start >= end) {
      report('Время начала должно быть раньше времени окончания', 'error')
      return
    }
    setSaving(true)
    try {
      const res = await api.post('/availabilities/bulk', {
        entity_type: entityType,
        entity_id: entityId,
        days: selectedDays,
        start_time: start,
        end_time: end,
        replace,
      })
      const data = res.data as { created: number; skipped: number; removed: number }
      const parts: string[] = []
      if (data.removed > 0) parts.push(`удалено прежних записей: ${data.removed}`)
      parts.push(`добавлено: ${data.created}`)
      if (data.skipped > 0) parts.push(`уже было: ${data.skipped}`)
      report(`Доступность обновлена (${parts.join(', ')})`, 'success')
      setReplace(false)
      await load()
    } catch (err: unknown) {
      const detail = err as { response?: { data?: { detail?: string } } }
      const msg =
        detail?.response?.data?.detail ?? 'Не удалось сохранить доступность'
      report(msg, 'error')
    } finally {
      setSaving(false)
    }
  }

  const removeOne = async (id: number | null | undefined) => {
    if (id == null) return
    try {
      await api.delete(`/availabilities/${id}`)
      setItems((prev) => prev.filter((a) => a.id !== id))
    } catch (err: unknown) {
      const detail = err as { response?: { data?: { detail?: string } } }
      report(detail?.response?.data?.detail ?? 'Ошибка удаления', 'error')
    }
  }

  const clearAll = async () => {
    if (!entityId) return
    if (!confirm('Удалить всю доступность?')) return
    try {
      await api.delete(`/availabilities/bulk?entity_type=${entityType}&entity_id=${entityId}`)
      setItems([])
      report('Доступность удалена', 'success')
    } catch (err: unknown) {
      const detail = err as { response?: { data?: { detail?: string } } }
      report(detail?.response?.data?.detail ?? 'Ошибка удаления', 'error')
    }
  }

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Текущая доступность
      </Typography>
      {sortedItems.length === 0 ? (
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          Не задана — доступны все часы работы центра
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.5 }}>
          {sortedItems.map((a) => (
            <Chip
              key={a.id}
              size="small"
              color="primary"
              variant="outlined"
              label={`${DayNames[a.day_of_week]} ${a.start_time}–${a.end_time}`}
              onDelete={() => void removeOne(a.id)}
            />
          ))}
        </Box>
      )}
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
        {describeWindow(sortedItems) || '—'}
      </Typography>

      <Typography variant="subtitle2" gutterBottom>
        Заполнить одни и те же часы
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
        {PRESETS.map((p) => (
          <Chip
            key={p.label}
            size="small"
            label={p.label}
            color={activePreset === p.label ? 'primary' : 'default'}
            variant={activePreset === p.label ? 'filled' : 'outlined'}
            onClick={() => setSelectedDays(p.days)}
          />
        ))}
      </Box>

      <ToggleButtonGroup
        value={selectedDays}
        onChange={toggleDay}
        size="small"
        sx={{ mb: 2, flexWrap: 'wrap', gap: 0.5, '& .MuiToggleButtonGroup-grouped': { border: '1px solid !important', borderRadius: '18px !important', margin: '0 !important' } }}
      >
        {ALL_DAYS.map((d) => (
          <ToggleButton key={d} value={d} sx={{ px: 1.5 }}>
            {DayNames[d]}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 1 }}>
        <TextField
          label="Начало"
          type="time"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 130 }}
        />
        <TextField
          label="Конец"
          type="time"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          slotProps={{ inputLabel: { shrink: true } }}
          sx={{ width: 130 }}
        />
        <FormControlLabel
          control={
            <Switch checked={replace} onChange={(e) => setReplace(e.target.checked)} size="small" />
          }
          label={<Typography variant="body2">Заменить всё</Typography>}
        />
        <Button
          variant="contained"
          onClick={addBulk}
          disabled={!canSubmit}
          startIcon={saving ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Заполнить
        </Button>
        <Button
          variant="outlined"
          color="error"
          onClick={clearAll}
          disabled={items.length === 0}
          startIcon={<DeleteSweepIcon />}
        >
          Очистить всё
        </Button>
      </Box>

      <Alert severity="info" icon={false} sx={{ py: 0 }}>
        Будет сохранено {start}–{end} для дней: {daysLabel}
        {windowHours && (
          <>
            {' '}
            Расписание строится в интервале {windowHours.from}–{windowHours.to}; время вне него
            будет проигнорировано.
          </>
        )}
      </Alert>

      {outsideWindow && windowHours && (
        <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
          Интервал выходит за рабочие часы центра ({windowHours.from}–{windowHours.to}) —{' '}
          {toMinutes(start) < toMinutes(windowHours.from)
            ? `раньше ${windowHours.from} занятия не будут поставлены`
            : `позже ${windowHours.to} занятия не будут поставлены`}
          . Измените часы центра в настройках оптимизатора или подберите интервал внутри окна.
        </Alert>
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        >
          {snackbar.msg}
        </Alert>
      </Snackbar>
    </Box>
  )
}
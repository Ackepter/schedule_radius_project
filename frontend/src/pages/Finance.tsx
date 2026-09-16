import { useEffect, useState, useCallback } from 'react'
import {
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Card,
  CardContent,
  Grid,
  Snackbar,
  Alert,
  CircularProgress,
} from '@mui/material'
import api from '../api/client'
import type { ScheduleBase, FinanceSummary } from '../api/types'

export default function Finance() {
  const [schedules, setSchedules] = useState<ScheduleBase[]>([])
  const [selectedScheduleId, setSelectedScheduleId] = useState<number>(0)
  const [summary, setSummary] = useState<FinanceSummary | null>(null)
  const [loading, setLoading] = useState(false)

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'error',
  })

  const loadSchedules = useCallback(async () => {
    try {
      const res = await api.get('/schedules')
      setSchedules(res.data as ScheduleBase[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }, [])

  useEffect(() => { loadSchedules() }, [loadSchedules])

  const loadSummary = useCallback(async (scheduleId: number) => {
    if (!scheduleId) return
    setLoading(true)
    try {
      const res = await api.get(`/finance/summary?schedule_id=${scheduleId}`)
      setSummary(res.data as FinanceSummary)
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки финансов', severity: 'error' })
      setSummary(null)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (selectedScheduleId) loadSummary(selectedScheduleId)
  }, [selectedScheduleId, loadSummary])

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Финансы
      </Typography>

      <FormControl sx={{ minWidth: 300, mb: 3 }}>
        <InputLabel>Расписание</InputLabel>
        <Select
          value={selectedScheduleId}
          label="Расписание"
          onChange={(e) => setSelectedScheduleId(Number(e.target.value))}
        >
          {schedules.map((s) => (
            <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
          ))}
        </Select>
      </FormControl>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : summary ? (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h3" color="primary">
                  {summary.total_revenue.toLocaleString('ru-RU')} ₽
                </Typography>
                <Typography color="text.secondary">Общая выручка</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h3">{summary.total_lessons}</Typography>
                <Typography color="text.secondary">Всего занятий</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h3">{summary.individual_lessons}</Typography>
                <Typography color="text.secondary">Индивидуальных</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Card>
              <CardContent>
                <Typography variant="h3">{summary.group_lessons}</Typography>
                <Typography color="text.secondary">Групповых</Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Выручка по предметам</Typography>
                {Object.entries(summary.revenue_by_subject).length === 0 ? (
                  <Typography color="text.secondary">Нет данных</Typography>
                ) : (
                  Object.entries(summary.revenue_by_subject).map(([name, amount]) => (
                    <Box key={name} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography>{name}</Typography>
                      <Typography sx={{ fontWeight: 'bold' }}>{Number(amount).toLocaleString('ru-RU')} ₽</Typography>
                    </Box>
                  ))
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Выручка по типу</Typography>
                {Object.entries(summary.revenue_by_lesson_type).length === 0 ? (
                  <Typography color="text.secondary">Нет данных</Typography>
                ) : (
                  Object.entries(summary.revenue_by_lesson_type).map(([type, amount]) => (
                    <Box key={type} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography>{type === 'individual' ? 'Индивидуальные' : 'Групповые'}</Typography>
                      <Typography sx={{ fontWeight: 'bold' }}>{Number(amount).toLocaleString('ru-RU')} ₽</Typography>
                    </Box>
                  ))
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6 }}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Доп. информация</Typography>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography>Средняя цена занятия:</Typography>
                  <Typography sx={{ fontWeight: 'bold' }}>{summary.average_lesson_price.toLocaleString('ru-RU')} ₽</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography>Студенто-часов:</Typography>
                  <Typography sx={{ fontWeight: 'bold' }}>{summary.total_student_hours}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                  <Typography>Период:</Typography>
                  <Typography sx={{ fontWeight: 'bold' }}>{summary.period_start} — {summary.period_end}</Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : selectedScheduleId ? (
        <Typography color="text.secondary">Выберите расписание для просмотра финансов</Typography>
      ) : (
        <Typography color="text.secondary">Выберите расписание</Typography>
      )}

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

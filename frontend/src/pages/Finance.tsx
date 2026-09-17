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
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Tooltip,
  Chip,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import api from '../api/client'
import type {
  ScheduleBase,
  FinanceSummary,
  Subject,
  Teacher,
  Price,
  TeacherRate,
} from '../api/types'

interface PriceForm {
  subject_id: number
  lesson_type: string
  min_participants: number
  max_participants: number
  price_per_student: number
}

interface RateForm {
  teacher_id: number | ''
  subject_id: number
  lesson_type: string
  rate_per_lesson: number
}

const emptyPriceForm: PriceForm = {
  subject_id: 0,
  lesson_type: 'individual',
  min_participants: 1,
  max_participants: 1,
  price_per_student: 0,
}

const emptyRateForm: RateForm = {
  teacher_id: '',
  subject_id: 0,
  lesson_type: 'individual',
  rate_per_lesson: 0,
}

function errMsg(err: unknown): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } } }
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail
  }
  return err instanceof Error ? err.message : 'Ошибка'
}

const fmt = (v: number) => `${Number(v).toLocaleString('ru-RU')} ₽`

export default function Finance() {
  const [tab, setTab] = useState(0)
  const [schedules, setSchedules] = useState<ScheduleBase[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [prices, setPrices] = useState<Price[]>([])
  const [rates, setRates] = useState<TeacherRate[]>([])
  const [selectedScheduleId, setSelectedScheduleId] = useState<number>(0)
  const [summary, setSummary] = useState<FinanceSummary | null>(null)
  const [loading, setLoading] = useState(false)

  const [priceOpen, setPriceOpen] = useState(false)
  const [priceForm, setPriceForm] = useState<PriceForm>(emptyPriceForm)
  const [priceEditId, setPriceEditId] = useState<number | null>(null)

  const [rateOpen, setRateOpen] = useState(false)
  const [rateForm, setRateForm] = useState<RateForm>(emptyRateForm)
  const [rateEditId, setRateEditId] = useState<number | null>(null)

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const loadBase = useCallback(async () => {
    const [sch, subj, teach, pr, rt] = await Promise.all([
      api.get('/schedules'),
      api.get('/subjects'),
      api.get('/teachers'),
      api.get('/prices'),
      api.get('/finance/teacher-rates'),
    ])
    setSchedules(sch.data as ScheduleBase[])
    setSubjects(subj.data as Subject[])
    setTeachers(teach.data as Teacher[])
    setPrices(pr.data as Price[])
    setRates(rt.data as TeacherRate[])
  }, [])

  useEffect(() => {
    loadBase().catch(() =>
      setSnackbar({ open: true, msg: 'Ошибка загрузки данных', severity: 'error' }),
    )
  }, [loadBase])

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

  const subjectName = (id: number) => (subjects ?? []).find((s) => s.id === id)?.name ?? '—'
  const teacherName = (id: number) => {
    const t = (teachers ?? []).find((tt) => tt.id === id)
    return t ? `${t.last_name} ${t.first_name}` : '—'
  }
  const typeLabel = (t: string) =>
    t === 'individual' ? 'Индивидуальное' : t === 'group' ? 'Групповое' : t

  // ── Тарифы учеников ─────────────────────────────────────────────────
  const openPriceDialog = (row?: Price) => {
    if (row) {
      setPriceEditId(row.id)
      setPriceForm({
        subject_id: row.subject_id,
        lesson_type: row.lesson_type,
        min_participants: row.min_participants,
        max_participants: row.max_participants,
        price_per_student: row.price_per_student,
      })
    } else {
      setPriceEditId(null)
      setPriceForm({
        ...emptyPriceForm,
        subject_id: subjects[0]?.id ?? 0,
      })
    }
    setPriceOpen(true)
  }

  const savePrice = async () => {
    const body = {
      subject_id: priceForm.subject_id,
      lesson_type: priceForm.lesson_type,
      min_participants: priceForm.min_participants,
      max_participants: priceForm.max_participants,
      price_per_student: priceForm.price_per_student,
    }
    try {
      if (priceEditId != null) {
        await api.put(`/prices/${priceEditId}`, body)
      } else {
        await api.post('/prices', body)
      }
      setPriceOpen(false)
      setSnackbar({ open: true, msg: 'Тариф сохранён', severity: 'success' })
      const pr = await api.get('/prices')
      setPrices(pr.data as Price[])
    } catch (err) {
      setSnackbar({ open: true, msg: errMsg(err), severity: 'error' })
    }
  }

  const deletePrice = async (id: number) => {
    if (!confirm('Удалить тариф?')) return
    try {
      await api.delete(`/prices/${id}`)
      const pr = await api.get('/prices')
      setPrices(pr.data as Price[])
      setSnackbar({ open: true, msg: 'Тариф удалён', severity: 'success' })
    } catch (err) {
      setSnackbar({ open: true, msg: errMsg(err), severity: 'error' })
    }
  }

  // ── Оплата педагогам ─────────────────────────────────────────────────
  const openRateDialog = (row?: TeacherRate) => {
    if (row) {
      setRateEditId(row.id)
      setRateForm({
        teacher_id: row.teacher_id ?? '',
        subject_id: row.subject_id,
        lesson_type: row.lesson_type,
        rate_per_lesson: row.rate_per_lesson,
      })
    } else {
      setRateEditId(null)
      setRateForm({
        ...emptyRateForm,
        subject_id: subjects[0]?.id ?? 0,
      })
    }
    setRateOpen(true)
  }

  const saveRate = async () => {
    const body: {
      teacher_id: number | null
      subject_id: number
      lesson_type: string
      rate_per_lesson: number
    } = {
      teacher_id: rateForm.teacher_id === '' ? null : Number(rateForm.teacher_id),
      subject_id: rateForm.subject_id,
      lesson_type: rateForm.lesson_type,
      rate_per_lesson: rateForm.rate_per_lesson,
    }
    try {
      if (rateEditId != null) {
        await api.put(`/finance/teacher-rates/${rateEditId}`, {
          rate_per_lesson: body.rate_per_lesson,
        })
      } else {
        await api.post('/finance/teacher-rates', body)
      }
      setRateOpen(false)
      setSnackbar({ open: true, msg: 'Ставка сохранена', severity: 'success' })
      const rt = await api.get('/finance/teacher-rates')
      setRates(rt.data as TeacherRate[])
    } catch (err) {
      setSnackbar({ open: true, msg: errMsg(err), severity: 'error' })
    }
  }

  const deleteRate = async (id: number) => {
    if (!confirm('Удалить ставку?')) return
    try {
      await api.delete(`/finance/teacher-rates/${id}`)
      const rt = await api.get('/finance/teacher-rates')
      setRates(rt.data as TeacherRate[])
      setSnackbar({ open: true, msg: 'Ставка удалена', severity: 'success' })
    } catch (err) {
      setSnackbar({ open: true, msg: errMsg(err), severity: 'error' })
    }
  }

  const defaultRates = (rates ?? []).filter((r) => r.is_default)
  const teacherRates = (rates ?? []).filter((r) => !r.is_default)

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Финансы
      </Typography>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Отчёт" />
        <Tab label="Тарифы учеников" />
        <Tab label="Оплата педагогам" />
      </Tabs>

      {/* ───────────── Отчёт ───────────── */}
      {tab === 0 && (
        <Box>
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
                    <Typography variant="h5" color="primary">
                      {fmt(summary.total_revenue)}
                    </Typography>
                    <Typography color="text.secondary">Выручка центра (оплата детей)</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card>
                  <CardContent>
                    <Typography variant="h5" color="warning.main">
                      {fmt(summary.teacher_pay_total)}
                    </Typography>
                    <Typography color="text.secondary">На оплату педагогам</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card>
                  <CardContent>
                    <Typography variant="h5" color="success.main">
                      {fmt(summary.net_revenue)}
                    </Typography>
                    <Typography color="text.secondary">Чистая прибыль центра</Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <Card>
                  <CardContent>
                    <Typography variant="h3">{summary.total_lessons}</Typography>
                    <Typography color="text.secondary">
                      Занятий ({summary.individual_lessons} индивид. / {summary.group_lessons} групп.)
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              {summary.warnings.length > 0 && (
                <Grid size={{ xs: 12 }}>
                  <Paper sx={{ p: 2, bgcolor: '#fff8e1', borderLeft: '4px solid #ed6c02' }}>
                    <Typography variant="h6" color="warning.dark" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <WarningAmberIcon /> Требует внимания
                    </Typography>
                    {summary.warnings.map((w, i) => (
                      <Typography key={i} variant="body2" sx={{ py: 0.3 }}>
                        • {w}
                      </Typography>
                    ))}
                  </Paper>
                </Grid>
              )}

              <Grid size={{ xs: 12, md: 6 }}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>Кто сколько заработал (педагоги)</Typography>
                  {(summary.teacher_breakdown ?? []).length === 0 ? (
                    <Typography color="text.secondary">Нет данных</Typography>
                  ) : (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Педагог</TableCell>
                            <TableCell>Индивид.</TableCell>
                            <TableCell>Групп.</TableCell>
                            <TableCell align="right">К выплате</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {summary.teacher_breakdown.map((t) => (
                            <TableRow key={t.teacher_id}>
                              <TableCell>{t.teacher_name}</TableCell>
                              <TableCell>{t.individual_lessons}</TableCell>
                              <TableCell>{t.group_lessons}</TableCell>
                              <TableCell align="right" sx={{ fontWeight: 'bold' }}>{fmt(t.total_pay)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Paper>
              </Grid>

              <Grid size={{ xs: 12, md: 6 }}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>Кто сколько отдал (ученики)</Typography>
                  {(summary.student_breakdown ?? []).length === 0 ? (
                    <Typography color="text.secondary">Нет данных</Typography>
                  ) : (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Ученик</TableCell>
                            <TableCell>Индивид.</TableCell>
                            <TableCell>Групп.</TableCell>
                            <TableCell align="right">Оплачено</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {summary.student_breakdown.map((st) => (
                            <TableRow key={st.student_id}>
                              <TableCell>{st.student_name}</TableCell>
                              <TableCell>{st.individual_lessons}</TableCell>
                              <TableCell>{st.group_lessons}</TableCell>
                              <TableCell align="right" sx={{ fontWeight: 'bold' }}>{fmt(st.total_paid)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </Paper>
              </Grid>

              <Grid size={{ xs: 12 }}>
                <Paper sx={{ p: 2 }}>
                  <Typography variant="h6" gutterBottom>Выручка по предметам и типам</Typography>
                  <Grid container spacing={2}>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      {Object.keys(summary.revenue_by_subject ?? {}).length === 0 ? (
                        <Typography color="text.secondary">Нет данных</Typography>
                      ) : (
                        Object.entries(summary.revenue_by_subject ?? {}).map(([name, amount]) => (
                          <Box key={name} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                            <Typography>{name}</Typography>
                            <Typography sx={{ fontWeight: 'bold' }}>{fmt(amount)}</Typography>
                          </Box>
                        ))
                      )}
                    </Grid>
                    <Grid size={{ xs: 12, sm: 6 }}>
                      {Object.keys(summary.revenue_by_lesson_type ?? {}).length === 0 ? (
                        <Typography color="text.secondary">Нет данных</Typography>
                      ) : (
                        Object.entries(summary.revenue_by_lesson_type ?? {}).map(([type, amount]) => (
                          <Box key={type} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                            <Typography>{typeLabel(type)}</Typography>
                            <Typography sx={{ fontWeight: 'bold' }}>{fmt(amount)}</Typography>
                          </Box>
                        ))
                      )}
                    </Grid>
                  </Grid>
                </Paper>
              </Grid>
            </Grid>
          ) : selectedScheduleId ? (
            <Typography color="text.secondary">Выберите расписание для просмотра финансов</Typography>
          ) : (
            <Typography color="text.secondary">Выберите расписание</Typography>
          )}
        </Box>
      )}

      {/* ───────────── Тарифы учеников ───────────── */}
      {tab === 1 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, alignItems: 'center' }}>
            <Typography variant="h6">Стоимость занятий для учеников</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => openPriceDialog()}>
              Добавить тариф
            </Button>
          </Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Индивидуальное занятие — цена за одно занятие с ребёнка. Групповое — цена с одного
            участника в зависимости от размера группы (например: 2 чел. — 800 ₽, 3–4 чел. — 700 ₽, 5–8 чел. — 550 ₽).
          </Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Направление</TableCell>
                  <TableCell>Тип</TableCell>
                  <TableCell>Участников</TableCell>
                  <TableCell align="right">Цена с ученика</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(prices ?? []).map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>{subjectName(p.subject_id)}</TableCell>
                    <TableCell><Chip size="small" label={typeLabel(p.lesson_type)} /></TableCell>
                    <TableCell>{p.min_participants === p.max_participants ? p.min_participants : `${p.min_participants}–${p.max_participants}`}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>{fmt(p.price_per_student)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => openPriceDialog(p)}><EditIcon fontSize="small" /></IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" onClick={() => deletePrice(p.id)}><DeleteIcon fontSize="small" color="error" /></IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {(prices ?? []).length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} align="center" color="text.secondary">Нет тарифов — добавьте хотя бы один</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ───────────── Оплата педагогам ───────────── */}
      {tab === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, alignItems: 'center' }}>
            <Typography variant="h6">Ставки оплаты педагогам за одно занятие</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => openRateDialog()}>
              Добавить ставку
            </Button>
          </Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Ставка — сумма, которую центр платит педагогу за одно занятие по направлению.
            Ставка не может превышать выручку центра с занятия. «По умолчанию» применяется ко всем
            педагогам, у которых нет индивидуальной ставки.
          </Typography>

          <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>По умолчанию (все педагоги)</Typography>
          <TableContainer component={Paper} sx={{ mb: 3 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Направление</TableCell>
                  <TableCell>Тип</TableCell>
                  <TableCell align="right">Ставка за занятие</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {defaultRates.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{subjectName(r.subject_id)}</TableCell>
                    <TableCell><Chip size="small" label={typeLabel(r.lesson_type)} /></TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>{fmt(r.rate_per_lesson)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => openRateDialog(r)}><EditIcon fontSize="small" /></IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" onClick={() => deleteRate(r.id)}><DeleteIcon fontSize="small" color="error" /></IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {defaultRates.length === 0 && (
                  <TableRow><TableCell colSpan={4} align="center">Нет ставок по умолчанию</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>

          <Typography variant="subtitle1" gutterBottom>Индивидуальные ставки педагогов</Typography>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Педагог</TableCell>
                  <TableCell>Направление</TableCell>
                  <TableCell>Тип</TableCell>
                  <TableCell align="right">Ставка за занятие</TableCell>
                  <TableCell align="right">Действия</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {teacherRates.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.teacher_id != null ? teacherName(r.teacher_id) : '—'}</TableCell>
                    <TableCell>{subjectName(r.subject_id)}</TableCell>
                    <TableCell><Chip size="small" label={typeLabel(r.lesson_type)} /></TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>{fmt(r.rate_per_lesson)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                      <Tooltip title="Редактировать">
                        <IconButton size="small" onClick={() => openRateDialog(r)}><EditIcon fontSize="small" /></IconButton>
                      </Tooltip>
                      <Tooltip title="Удалить">
                        <IconButton size="small" onClick={() => deleteRate(r.id)}><DeleteIcon fontSize="small" color="error" /></IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {teacherRates.length === 0 && (
                  <TableRow><TableCell colSpan={5} align="center">Индивидуальных ставок нет</TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ── Диалог тарифа учеников ── */}
      <Dialog open={priceOpen} onClose={() => setPriceOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{priceEditId != null ? 'Редактировать тариф' : 'Новый тариф'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <FormControl fullWidth>
            <InputLabel>Направление</InputLabel>
            <Select
              value={priceForm.subject_id}
              label="Направление"
              onChange={(e) => setPriceForm({ ...priceForm, subject_id: Number(e.target.value) })}
            >
              {(subjects ?? []).map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Тип занятия</InputLabel>
            <Select
              value={priceForm.lesson_type}
              label="Тип занятия"
              onChange={(e) => {
                const t = e.target.value
                const base = { ...priceForm, lesson_type: t }
                if (t === 'individual') {
                  setPriceForm({ ...base, min_participants: 1, max_participants: 1 })
                } else {
                  setPriceForm({ ...base, min_participants: Math.max(priceForm.min_participants, 2), max_participants: Math.max(priceForm.max_participants, priceForm.min_participants, 2) })
                }
              }}
            >
              <MenuItem value="individual">Индивидуальное (1 чел.)</MenuItem>
              <MenuItem value="group">Групповое</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Мин. участников"
            type="number"
            value={priceForm.min_participants}
            onChange={(e) => setPriceForm({ ...priceForm, min_participants: Number(e.target.value) })}
            fullWidth
          />
          <TextField
            label="Макс. участников"
            type="number"
            value={priceForm.max_participants}
            onChange={(e) => setPriceForm({ ...priceForm, max_participants: Number(e.target.value) })}
            fullWidth
          />
          <TextField
            label="Цена с ученика за занятие (₽)"
            type="number"
            value={priceForm.price_per_student}
            onChange={(e) => setPriceForm({ ...priceForm, price_per_student: Number(e.target.value) })}
            fullWidth
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPriceOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={savePrice}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      {/* ── Диалог ставки педагога ── */}
      <Dialog open={rateOpen} onClose={() => setRateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{rateEditId != null ? 'Редактировать ставку' : 'Новая ставка'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <FormControl fullWidth>
            <InputLabel>Педагог</InputLabel>
            <Select
              value={rateForm.teacher_id}
              label="Педагог"
              onChange={(e) => {
                const v = e.target.value as unknown as string
                setRateForm({ ...rateForm, teacher_id: v === '' ? '' : Number(v) })
              }}
            >
              <MenuItem value="">По умолчанию (все педагоги)</MenuItem>
              {(teachers ?? []).map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.last_name} {t.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Направление</InputLabel>
            <Select
              value={rateForm.subject_id}
              label="Направление"
              onChange={(e) => setRateForm({ ...rateForm, subject_id: Number(e.target.value) })}
            >
              {(subjects ?? []).map((s) => <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>)}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Тип занятия</InputLabel>
            <Select
              value={rateForm.lesson_type}
              label="Тип занятия"
              onChange={(e) => setRateForm({ ...rateForm, lesson_type: e.target.value })}
            >
              <MenuItem value="individual">Индивидуальное</MenuItem>
              <MenuItem value="group">Групповое</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Ставка за занятие (₽)"
            type="number"
            value={rateForm.rate_per_lesson}
            onChange={(e) => setRateForm({ ...rateForm, rate_per_lesson: Number(e.target.value) })}
            fullWidth
          />
          {rateForm.rate_per_lesson > 0 && (
            <Typography variant="caption" color="text.secondary">
              Проверка: ставка не должна превышать выручку центра с занятия. При нарушении сохранение будет отклонено.
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRateOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={saveRate}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}
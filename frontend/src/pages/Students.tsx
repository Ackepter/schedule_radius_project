import { useEffect, useState, useCallback } from 'react'
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Snackbar,
  Alert,
  Switch,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Tabs,
  Tab,
  Chip as MuiChip,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import CloseIcon from '@mui/icons-material/Close'
import api from '../api/client'
import type { StudentBase, StudentList, Parent, Subject, Teacher, Availability as AvailType } from '../api/types'
import { LessonTypeEnum, DayNames } from '../api/types'
import type { LessonRequestBase } from '../api/types'

interface StudentForm {
  first_name: string
  last_name: string
  birth_date: string
  comment: string
  is_active: boolean
  parent_id: number | ''
}

const emptyForm: StudentForm = {
  first_name: '',
  last_name: '',
  birth_date: '',
  comment: '',
  is_active: true,
  parent_id: '',
}

interface LessonReqForm {
  student_id: number
  subject_id: number
  lesson_type: string
  lessons_per_week: number
  duration_minutes: number
  preferred_teacher_id: number | ''
  teacher_is_required: boolean
  priority: number
  notes: string
  excluded_student_ids: number[]
}

function makeEmptyLR(studentId: number): LessonReqForm {
  return {
    student_id: studentId,
    subject_id: 0,
    lesson_type: LessonTypeEnum.individual,
    lessons_per_week: 1,
    duration_minutes: 60,
    preferred_teacher_id: '',
    teacher_is_required: false,
    priority: 1,
    notes: '',
    excluded_student_ids: [],
  }
}

function lessonTypeLabel(t: string): string {
  if (t === LessonTypeEnum.both) return 'Индивидуально и в группе'
  if (t === LessonTypeEnum.group) return 'Групповое'
  return 'Индивидуальное'
}

export default function Students() {
  const [items, setItems] = useState<StudentList[]>([])
  const [parents, setParents] = useState<Parent[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<StudentForm>(emptyForm)
  const [editId, setEditId] = useState<number | null>(null)

  const [lrOpen, setLrOpen] = useState(false)
  const [lrForm, setLrForm] = useState<LessonReqForm>(makeEmptyLR(0))
  const [lrEditId, setLrEditId] = useState<number | null>(null)

  const [detailOpen, setDetailOpen] = useState(false)
  const [detail, setDetail] = useState<StudentList | null>(null)
  const [detailTab, setDetailTab] = useState(0)
  const [availabilities, setAvailabilities] = useState<AvailType[]>([])
  const [newAvailDay, setNewAvailDay] = useState(0)
  const [newAvailStart, setNewAvailStart] = useState('09:00')
  const [newAvailEnd, setNewAvailEnd] = useState('12:00')

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const load = useCallback(async () => {
    try {
      const [sRes, pRes, subRes, tRes] = await Promise.all([
        api.get('/students'),
        api.get('/parents'),
        api.get('/subjects'),
        api.get('/teachers'),
      ])
      setItems(sRes.data as StudentList[])
      setParents(pRes.data as Parent[])
      setSubjects(subRes.data as Subject[])
      setTeachers(tRes.data as Teacher[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    const payload: Record<string, unknown> = {
      first_name: form.first_name,
      last_name: form.last_name,
      comment: form.comment || null,
      is_active: form.is_active,
      parent_id: form.parent_id === '' ? null : form.parent_id,
    }
    if (form.birth_date) payload.birth_date = form.birth_date

    try {
      if (editId !== null) {
        await api.put(`/students/${editId}`, payload)
      } else {
        await api.post('/students', payload)
      }
      setOpen(false)
      setSnackbar({ open: true, msg: 'Сохранено', severity: 'success' })
      load()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить ученика?')) return
    try {
      await api.delete(`/students/${id}`)
      setSnackbar({ open: true, msg: 'Удалено', severity: 'success' })
      load()
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка удаления', severity: 'error' })
    }
  }

  const openCreate = () => {
    setForm({ ...emptyForm })
    setEditId(null)
    setOpen(true)
  }

  const openEdit = (item: StudentBase) => {
    setForm({
      first_name: item.first_name,
      last_name: item.last_name,
      birth_date: item.birth_date || '',
      comment: item.comment || '',
      is_active: item.is_active,
      parent_id: item.parent_id ?? '',
    })
    setEditId(item.id)
    setOpen(true)
  }

  const openDetail = async (id: number) => {
    try {
      const res = await api.get(`/students/${id}`)
      setDetail(res.data as StudentList)
      setDetailTab(0)
      setDetailOpen(true)
      loadAvailabilities(id)
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }

  const loadAvailabilities = async (studentId: number) => {
    try {
      const res = await api.get(`/availabilities?entity_type=student&entity_id=${studentId}`)
      setAvailabilities(res.data as AvailType[])
    } catch {
      // ignore
    }
  }

  const addAvailability = async () => {
    if (!detail) return
    try {
      await api.post('/availabilities', {
        entity_type: 'student',
        entity_id: detail.id,
        day_of_week: newAvailDay,
        start_time: newAvailStart,
        end_time: newAvailEnd,
      })
      setSnackbar({ open: true, msg: 'Доступность добавлена', severity: 'success' })
      loadAvailabilities(detail.id)
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка добавления доступности', severity: 'error' })
    }
  }

  const deleteAvailability = async (availId: number | null | undefined) => {
    if (availId == null) return
    if (!confirm('Удалить эту доступность?')) return
    try {
      await api.delete(`/availabilities/${availId}`)
      setSnackbar({ open: true, msg: 'Доступность удалена', severity: 'success' })
      setAvailabilities((prev) => prev.filter((a) => a.id !== availId))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка удаления'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const deleteAllAvailability = async () => {
    if (!detail) return
    if (!confirm('Удалить всю доступность?')) return
    try {
      await api.delete(`/availabilities/bulk?entity_type=student&entity_id=${detail.id}`)
      setSnackbar({ open: true, msg: 'Доступность удалена', severity: 'success' })
      loadAvailabilities(detail.id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка удаления'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const openLRCreate = (studentId: number) => {
    setLrForm(makeEmptyLR(studentId))
    setLrEditId(null)
    setLrOpen(true)
  }

  const openLREdit = (lr: LessonRequestBase) => {
    setLrForm({
      student_id: lr.student_id,
      subject_id: lr.subject_id,
      lesson_type: lr.lesson_type,
      lessons_per_week: lr.lessons_per_week,
      duration_minutes: lr.duration_minutes,
      preferred_teacher_id: lr.preferred_teacher_id ?? '',
      teacher_is_required: lr.teacher_is_required,
      priority: lr.priority,
      notes: lr.notes || '',
      excluded_student_ids: (lr.excluded_students ?? []).map((s) => s.id),
    })
    setLrEditId(lr.id)
    setLrOpen(true)
  }

  const handleLRSave = async () => {
    const payload: Record<string, unknown> = {
      student_id: lrForm.student_id,
      subject_id: lrForm.subject_id,
      lesson_type: lrForm.lesson_type,
      lessons_per_week: lrForm.lessons_per_week,
      duration_minutes: lrForm.duration_minutes,
      preferred_teacher_id: lrForm.preferred_teacher_id === '' ? null : lrForm.preferred_teacher_id,
      teacher_is_required: lrForm.teacher_is_required,
      priority: lrForm.priority,
      notes: lrForm.notes || null,
      excluded_student_ids: lrForm.excluded_student_ids,
    }
    try {
      if (lrEditId !== null) {
        await api.put(`/lesson-requests/${lrEditId}`, payload)
      } else {
        await api.post('/lesson-requests', payload)
      }
      setLrOpen(false)
      setSnackbar({ open: true, msg: 'Требование сохранено', severity: 'success' })
      if (detail) openDetail(detail.id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const handleLRDelete = async (id: number) => {
    if (!confirm('Удалить требование?')) return
    try {
      await api.delete(`/lesson-requests/${id}`)
      setSnackbar({ open: true, msg: 'Удалено', severity: 'success' })
      if (detail) openDetail(detail.id)
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка удаления', severity: 'error' })
    }
  }

  const getParentName = (parentId: number | null | undefined) => {
    if (!parentId) return '—'
    const p = parents.find((pp) => pp.id === parentId)
    return p ? `${p.last_name} ${p.first_name}` : '—'
  }

  const getSubjectName = (id: number) => subjects.find((s) => s.id === id)?.name || '—'
  const getTeacherName = (id: number | null | undefined) => {
    if (!id) return '—'
    const t = teachers.find((tt) => tt.id === id)
    return t ? `${t.last_name} ${t.first_name}` : '—'
  }
  const getStudentName = (id: number) => {
    const st = items.find((s) => s.id === id)
    return st ? `${st.last_name} ${st.first_name}` : '(удалён)'
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Ученики</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Добавить
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ФИО</TableCell>
              <TableCell>Дата рождения</TableCell>
              <TableCell>Родитель</TableCell>
              <TableCell>Активен</TableCell>
              <TableCell>Требования</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id} hover sx={{ cursor: 'pointer' }} onClick={() => openDetail(item.id)}>
                <TableCell>{item.last_name} {item.first_name}</TableCell>
                <TableCell>{item.birth_date || '—'}</TableCell>
                <TableCell>{getParentName(item.parent_id)}</TableCell>
                <TableCell>{item.is_active ? 'Да' : 'Нет'}</TableCell>
                <TableCell>
                  {item.lesson_requests.length > 0 ? (
                    <Chip size="small" label={`${item.lesson_requests.length} требований`} />
                  ) : (
                    <MuiChip size="small" label="Нет" variant="outlined" />
                  )}
                </TableCell>
                <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                  <IconButton onClick={() => openEdit(item)} size="small">
                    <EditIcon />
                  </IconButton>
                  <IconButton onClick={() => handleDelete(item.id)} size="small" color="error">
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editId !== null ? 'Редактировать ученика' : 'Новый ученик'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField label="Фамилия" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} fullWidth />
          <TextField label="Имя" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} fullWidth />
          <TextField label="Дата рождения" type="date" value={form.birth_date} onChange={(e) => setForm({ ...form, birth_date: e.target.value })} fullWidth slotProps={{ inputLabel: { shrink: true } }} />
          <FormControl fullWidth>
            <InputLabel>Родитель</InputLabel>
            <Select
              value={form.parent_id}
              label="Родитель"
              onChange={(e) => {
                const v = String(e.target.value)
                setForm({ ...form, parent_id: v === '' ? '' : Number(v) })
              }}
            >
              <MenuItem value="">Не указан</MenuItem>
              {parents.map((p) => (
                <MenuItem key={p.id} value={p.id}>{p.last_name} {p.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField label="Комментарий" value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} fullWidth multiline rows={2} />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Switch checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            <Typography>Активен</Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={lrOpen} onClose={() => setLrOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{lrEditId !== null ? 'Редактировать требование' : 'Новое требование'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <FormControl fullWidth>
            <InputLabel>Предмет</InputLabel>
            <Select value={lrForm.subject_id} label="Предмет" onChange={(e) => setLrForm({ ...lrForm, subject_id: Number(e.target.value) })}>
              {subjects.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Тип занятия</InputLabel>
            <Select value={lrForm.lesson_type} label="Тип занятия" onChange={(e) => setLrForm({ ...lrForm, lesson_type: e.target.value })}>
              <MenuItem value="individual">Индивидуальное</MenuItem>
              <MenuItem value="group">Групповое</MenuItem>
              <MenuItem value="both">Индивидуально и в группе</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Не заниматься в группе с</InputLabel>
            <Select
              multiple
              value={lrForm.excluded_student_ids}
              label="Не заниматься в группе с"
              onChange={(e) => {
                const value = e.target.value
                setLrForm({
                  ...lrForm,
                  excluded_student_ids: Array.isArray(value) ? value.map(Number) : [],
                })
              }}
              renderValue={(selected) =>
                selected.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">Нет ограничений</Typography>
                ) : (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {(selected as number[]).map((id) => (
                      <Chip key={id} size="small" label={getStudentName(id)} />
                    ))}
                  </Box>
                )
              }
            >
              {items
                .filter((s) => s.id !== lrForm.student_id)
                .map((s) => (
                  <MenuItem key={s.id} value={s.id}>
                    {s.last_name} {s.first_name}
                  </MenuItem>
                ))}
            </Select>
          </FormControl>
          <TextField label="Занятий в неделю" type="number" value={lrForm.lessons_per_week} onChange={(e) => setLrForm({ ...lrForm, lessons_per_week: Number(e.target.value) })} fullWidth />
          <TextField label="Длительность (мин)" type="number" value={lrForm.duration_minutes} onChange={(e) => setLrForm({ ...lrForm, duration_minutes: Number(e.target.value) })} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Предпочтительный педагог</InputLabel>
            <Select
              value={lrForm.preferred_teacher_id}
              label="Предпочтительный педагог"
              onChange={(e) => {
                const v = String(e.target.value)
                setLrForm({ ...lrForm, preferred_teacher_id: v === '' ? '' : Number(v) })
              }}
            >
              <MenuItem value="">Не указан</MenuItem>
              {teachers.map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.last_name} {t.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Switch checked={lrForm.teacher_is_required} onChange={(e) => setLrForm({ ...lrForm, teacher_is_required: e.target.checked })} />
            <Typography>Педагог обязателен</Typography>
          </Box>
          <FormControl fullWidth>
            <InputLabel>Приоритет</InputLabel>
            <Select value={lrForm.priority} label="Приоритет" onChange={(e) => setLrForm({ ...lrForm, priority: Number(e.target.value) })}>
              <MenuItem value={1}>1 (низкий)</MenuItem>
              <MenuItem value={2}>2 (средний)</MenuItem>
              <MenuItem value={3}>3 (высокий)</MenuItem>
            </Select>
          </FormControl>
          <TextField label="Заметки" value={lrForm.notes} onChange={(e) => setLrForm({ ...lrForm, notes: e.target.value })} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLrOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleLRSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {detail ? `${detail.last_name} ${detail.first_name}` : 'Ученик'}
        </DialogTitle>
        <DialogContent>
          <Tabs value={detailTab} onChange={(_, v) => setDetailTab(v)} sx={{ mb: 2 }}>
            <Tab label="Требования" />
            <Tab label="Доступность" />
          </Tabs>

          {detailTab === 0 && detail && (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                <Button size="small" startIcon={<AddIcon />} onClick={() => openLRCreate(detail.id)}>
                  Добавить требование
                </Button>
              </Box>
              {detail.lesson_requests.length === 0 ? (
                <Typography color="text.secondary">Нет требований</Typography>
              ) : (
                detail.lesson_requests.map((lr) => (
                  <Paper key={lr.id} sx={{ p: 2, mb: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography variant="subtitle1">
                        {getSubjectName(lr.subject_id)} — {lessonTypeLabel(lr.lesson_type)}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {lr.lessons_per_week} раз(а) в неделю, {lr.duration_minutes} мин.
                        {lr.preferred_teacher_id && ` · Педагог: ${getTeacherName(lr.preferred_teacher_id)}`}
                        {lr.teacher_is_required && ' (обязательный)'}
                        {' · Приоритет: '}{lr.priority}
                        {(lr.excluded_students?.length ?? 0) > 0 && (
                          <span>
                            {' · Вне группы: '}
                            {lr.excluded_students!.map((s) => `${s.last_name} ${s.first_name}`).join(', ')}
                          </span>
                        )}
                      </Typography>
                    </Box>
                    <Box>
                      <IconButton onClick={() => openLREdit(lr)} size="small"><EditIcon /></IconButton>
                      <IconButton onClick={() => handleLRDelete(lr.id)} size="small" color="error"><DeleteIcon /></IconButton>
                    </Box>
                  </Paper>
                ))
              )}
            </Box>
          )}

          {detailTab === 1 && detail && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>Доступные дни/время:</Typography>
              {availabilities.length === 0 ? (
                <Typography color="text.secondary">Нет доступности</Typography>
              ) : (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {availabilities.map((a) => (
                    <Chip
                      key={a.id}
                      label={`${DayNames[a.day_of_week]}: ${a.start_time}–${a.end_time}`}
                      onDelete={() => void deleteAvailability(a.id)}
                      deleteIcon={<CloseIcon />}
                    />
                  ))}
                </Box>
              )}
              <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                <FormControl sx={{ minWidth: 120 }}>
                  <InputLabel>День</InputLabel>
                  <Select value={newAvailDay} label="День" onChange={(e) => setNewAvailDay(Number(e.target.value))}>
                    {DayNames.map((d, i) => (
                      <MenuItem key={i} value={i}>{d}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <TextField
                  label="Начало"
                  type="time"
                  value={newAvailStart}
                  onChange={(e) => setNewAvailStart(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ width: 120 }}
                />
                <TextField
                  label="Конец"
                  type="time"
                  value={newAvailEnd}
                  onChange={(e) => setNewAvailEnd(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  sx={{ width: 120 }}
                />
                <Button variant="outlined" size="small" onClick={addAvailability}>Добавить</Button>
                <Button variant="outlined" size="small" color="error" onClick={deleteAllAvailability}>Очистить</Button>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailOpen(false)}>Закрыть</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

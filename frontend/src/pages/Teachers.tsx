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
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import api from '../api/client'
import type { Teacher, Subject, Availability as AvailType } from '../api/types'
import { DayNames } from '../api/types'

interface TeacherForm {
  first_name: string
  last_name: string
  comment: string
  is_active: boolean
  max_weekly_hours: number | ''
  subject_ids: number[]
}

const emptyForm: TeacherForm = {
  first_name: '',
  last_name: '',
  comment: '',
  is_active: true,
  max_weekly_hours: '',
  subject_ids: [],
}

export default function Teachers() {
  const [items, setItems] = useState<Teacher[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<TeacherForm>(emptyForm)
  const [editId, setEditId] = useState<number | null>(null)

  const [availOpen, setAvailOpen] = useState(false)
  const [availTeacherId, setAvailTeacherId] = useState<number | null>(null)
  const [availabilities, setAvailabilities] = useState<AvailType[]>([])
  const [newAvailDay, setNewAvailDay] = useState(0)
  const [newAvailStart, setNewAvailStart] = useState('09:00')
  const [newAvailEnd, setNewAvailEnd] = useState('18:00')

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const load = useCallback(async () => {
    try {
      const [tRes, sRes] = await Promise.all([
        api.get('/teachers'),
        api.get('/subjects'),
      ])
      setItems(tRes.data as Teacher[])
      setSubjects(sRes.data as Subject[])
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
      max_weekly_hours: form.max_weekly_hours === '' ? null : form.max_weekly_hours,
      subject_ids: form.subject_ids,
    }
    try {
      if (editId !== null) {
        await api.put(`/teachers/${editId}`, payload)
      } else {
        await api.post('/teachers', payload)
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
    if (!confirm('Удалить педагога?')) return
    try {
      await api.delete(`/teachers/${id}`)
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

  const openEdit = (item: Teacher) => {
    setForm({
      first_name: item.first_name,
      last_name: item.last_name,
      comment: item.comment || '',
      is_active: item.is_active,
      max_weekly_hours: item.max_weekly_hours ?? '',
      subject_ids: item.subjects.map((s) => s.id),
    })
    setEditId(item.id)
    setOpen(true)
  }

  const openAvail = async (teacherId: number) => {
    setAvailTeacherId(teacherId)
    try {
      const res = await api.get(`/availabilities?entity_type=teacher&entity_id=${teacherId}`)
      setAvailabilities(res.data as AvailType[])
    } catch {
      setAvailabilities([])
    }
    setAvailOpen(true)
  }

  const addAvailability = async () => {
    if (!availTeacherId) return
    try {
      await api.post('/availabilities', {
        entity_type: 'teacher',
        entity_id: availTeacherId,
        day_of_week: newAvailDay,
        start_time: newAvailStart,
        end_time: newAvailEnd,
      })
      const res = await api.get(`/availabilities?entity_type=teacher&entity_id=${availTeacherId}`)
      setAvailabilities(res.data as AvailType[])
      setSnackbar({ open: true, msg: 'Доступность добавлена', severity: 'success' })
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка', severity: 'error' })
    }
  }

  const deleteAvailability = async (availId: number) => {
    try {
      await api.delete(`/availabilities/${availId}`)
      setAvailabilities((prev) => prev.filter((a) => a.id !== availId))
    } catch {
      // ignore
    }
  }

  const deleteAllAvailability = async () => {
    if (!availTeacherId) return
    if (!confirm('Удалить всю доступность?')) return
    try {
      await api.delete(`/availabilities/bulk?entity_type=teacher&entity_id=${availTeacherId}`)
      setAvailabilities([])
    } catch {
      // ignore
    }
  }

  const getSubjectNames = (teacherSubjects: Subject[]) =>
    teacherSubjects.map((s) => s.name).join(', ') || '—'

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Педагоги</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Добавить
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>ФИО</TableCell>
              <TableCell>Предметы</TableCell>
              <TableCell>Макс. часов/нед</TableCell>
              <TableCell>Активен</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.last_name} {item.first_name}</TableCell>
                <TableCell>{getSubjectNames(item.subjects)}</TableCell>
                <TableCell>{item.max_weekly_hours ?? '—'}</TableCell>
                <TableCell>{item.is_active ? 'Да' : 'Нет'}</TableCell>
                <TableCell align="right">
                  <IconButton onClick={() => openEdit(item)} size="small"><EditIcon /></IconButton>
                  <IconButton onClick={() => openAvail(item.id)} size="small">🕐</IconButton>
                  <IconButton onClick={() => handleDelete(item.id)} size="small" color="error"><DeleteIcon /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editId !== null ? 'Редактировать педагога' : 'Новый педагог'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField label="Фамилия" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} fullWidth />
          <TextField label="Имя" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Предметы</InputLabel>
            <Select
              multiple
              value={form.subject_ids}
              label="Предметы"
              onChange={(e) => setForm({ ...form, subject_ids: e.target.value as number[] })}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {(selected as number[]).map((id) => {
                    const s = subjects.find((ss) => ss.id === id)
                    return <Chip key={id} label={s?.name || id} size="small" />
                  })}
                </Box>
              )}
            >
              {subjects.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Макс. часов в неделю"
            type="number"
            value={form.max_weekly_hours}
            onChange={(e) => setForm({ ...form, max_weekly_hours: e.target.value === '' ? '' : Number(e.target.value) })}
            fullWidth
          />
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

      <Dialog open={availOpen} onClose={() => setAvailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Доступность педагога</DialogTitle>
        <DialogContent>
          {availabilities.length === 0 ? (
            <Typography color="text.secondary" sx={{ mb: 2 }}>Нет доступности</Typography>
          ) : (
            availabilities.map((a) => (
              <Chip
                key={a.id}
                label={`${DayNames[a.day_of_week]}: ${a.start_time}–${a.end_time}`}
                sx={{ mr: 1, mb: 1 }}
                onDelete={() => deleteAvailability(a.id!)}
              />
            ))
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
            <TextField label="Начало" type="time" value={newAvailStart} onChange={(e) => setNewAvailStart(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} sx={{ width: 120 }} />
            <TextField label="Конец" type="time" value={newAvailEnd} onChange={(e) => setNewAvailEnd(e.target.value)} slotProps={{ inputLabel: { shrink: true } }} sx={{ width: 120 }} />
            <Button variant="outlined" size="small" onClick={addAvailability}>Добавить</Button>
            <Button variant="outlined" size="small" color="error" onClick={deleteAllAvailability}>Очистить</Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAvailOpen(false)}>Закрыть</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

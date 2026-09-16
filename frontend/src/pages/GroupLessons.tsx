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
import type { GroupLesson, StudentBase, Subject, Teacher } from '../api/types'

interface GroupLessonForm {
  title: string
  subject_id: number
  teacher_id: number | ''
  teacher_is_required: boolean
  duration_minutes: number
  lessons_per_week: number
  max_size: number
  comment: string
  participant_ids: number[]
}

const emptyForm: GroupLessonForm = {
  title: '',
  subject_id: 0,
  teacher_id: '',
  teacher_is_required: false,
  duration_minutes: 60,
  lessons_per_week: 1,
  max_size: 6,
  comment: '',
  participant_ids: [],
}

export default function GroupLessons() {
  const [items, setItems] = useState<GroupLesson[]>([])
  const [students, setStudents] = useState<StudentBase[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<GroupLessonForm>(emptyForm)
  const [editId, setEditId] = useState<number | null>(null)

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const load = useCallback(async () => {
    try {
      const [gRes, sRes, subRes, tRes] = await Promise.all([
        api.get('/group-lessons'),
        api.get('/students'),
        api.get('/subjects'),
        api.get('/teachers'),
      ])
      setItems(gRes.data as GroupLesson[])
      setStudents(sRes.data as StudentBase[])
      setSubjects(subRes.data as Subject[])
      setTeachers(tRes.data as Teacher[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    const payload: Record<string, unknown> = {
      title: form.title,
      subject_id: form.subject_id,
      teacher_id: form.teacher_id === '' ? null : form.teacher_id,
      teacher_is_required: form.teacher_is_required,
      duration_minutes: form.duration_minutes,
      lessons_per_week: form.lessons_per_week,
      max_size: form.max_size,
      comment: form.comment || null,
      participant_ids: form.participant_ids,
    }
    try {
      if (editId !== null) {
        await api.put(`/group-lessons/${editId}`, payload)
      } else {
        await api.post('/group-lessons', payload)
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
    if (!confirm('Удалить групповое занятие?')) return
    try {
      await api.delete(`/group-lessons/${id}`)
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

  const openEdit = (item: GroupLesson) => {
    setForm({
      title: item.title,
      subject_id: item.subject_id,
      teacher_id: item.teacher_id ?? '',
      teacher_is_required: item.teacher_is_required,
      duration_minutes: item.duration_minutes,
      lessons_per_week: item.lessons_per_week,
      max_size: item.max_size,
      comment: item.comment || '',
      participant_ids: item.participants.map((p) => p.id),
    })
    setEditId(item.id)
    setOpen(true)
  }

  const getSubjectName = (id: number) => subjects.find((s) => s.id === id)?.name || '—'
  const getTeacherName = (id: number | null | undefined) => {
    if (!id) return 'Не назначен'
    const t = teachers.find((tt) => tt.id === id)
    return t ? `${t.last_name} ${t.first_name}` : '—'
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Групповые занятия</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Добавить
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Предмет</TableCell>
              <TableCell>Педагог</TableCell>
              <TableCell>Длительность</TableCell>
              <TableCell>Раз/нед</TableCell>
              <TableCell>Участники</TableCell>
              <TableCell>Макс. размер</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.title}</TableCell>
                <TableCell>{getSubjectName(item.subject_id)}</TableCell>
                <TableCell>{getTeacherName(item.teacher_id)}</TableCell>
                <TableCell>{item.duration_minutes} мин</TableCell>
                <TableCell>{item.lessons_per_week}</TableCell>
                <TableCell>
                  <Chip size="small" label={`${item.participants.length} чел.`} />
                </TableCell>
                <TableCell>{item.max_size}</TableCell>
                <TableCell align="right">
                  <IconButton onClick={() => openEdit(item)} size="small"><EditIcon /></IconButton>
                  <IconButton onClick={() => handleDelete(item.id)} size="small" color="error"><DeleteIcon /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editId !== null ? 'Редактировать группу' : 'Новая группа'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField label="Название" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Предмет</InputLabel>
            <Select value={form.subject_id} label="Предмет" onChange={(e) => setForm({ ...form, subject_id: Number(e.target.value) })}>
              {subjects.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Педагог</InputLabel>
            <Select
              value={form.teacher_id}
              label="Педагог"
              onChange={(e) => {
                const v = String(e.target.value)
                setForm({ ...form, teacher_id: v === '' ? '' : Number(v) })
              }}
            >
              <MenuItem value="">Не назначен</MenuItem>
              {teachers.map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.last_name} {t.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Switch checked={form.teacher_is_required} onChange={(e) => setForm({ ...form, teacher_is_required: e.target.checked })} />
            <Typography>Педагог обязателен</Typography>
          </Box>
          <TextField label="Длительность (мин)" type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} fullWidth />
          <TextField label="Занятий в неделю" type="number" value={form.lessons_per_week} onChange={(e) => setForm({ ...form, lessons_per_week: Number(e.target.value) })} fullWidth />
          <TextField label="Максимальный размер" type="number" value={form.max_size} onChange={(e) => setForm({ ...form, max_size: Number(e.target.value) })} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Участники</InputLabel>
            <Select
              multiple
              value={form.participant_ids}
              label="Участники"
              onChange={(e) => setForm({ ...form, participant_ids: e.target.value as number[] })}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {(selected as number[]).map((id) => {
                    const s = students.find((ss) => ss.id === id)
                    return <Chip key={id} label={s ? `${s.last_name} ${s.first_name}` : id} size="small" />
                  })}
                </Box>
              )}
            >
              {students.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.last_name} {s.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField label="Комментарий" value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

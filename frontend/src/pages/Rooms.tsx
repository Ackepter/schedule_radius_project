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
import type { Room, Subject, Availability as AvailType } from '../api/types'
import { DayNames } from '../api/types'

interface RoomForm {
  name: string
  capacity: number
  comment: string
  allowed_subject_ids: number[]
}

const emptyForm: RoomForm = { name: '', capacity: 1, comment: '', allowed_subject_ids: [] }

export default function Rooms() {
  const [items, setItems] = useState<Room[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<RoomForm>(emptyForm)
  const [editId, setEditId] = useState<number | null>(null)

  const [availOpen, setAvailOpen] = useState(false)
  const [availRoomId, setAvailRoomId] = useState<number | null>(null)
  const [availabilities, setAvailabilities] = useState<AvailType[]>([])
  const [newAvailDay, setNewAvailDay] = useState(0)
  const [newAvailStart, setNewAvailStart] = useState('09:00')
  const [newAvailEnd, setNewAvailEnd] = useState('21:00')

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const load = useCallback(async () => {
    try {
      const [rRes, sRes] = await Promise.all([
        api.get('/rooms'),
        api.get('/subjects'),
      ])
      setItems(rRes.data as Room[])
      setSubjects(sRes.data as Subject[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    const payload: Record<string, unknown> = {
      name: form.name,
      capacity: form.capacity,
      comment: form.comment || null,
      allowed_subject_ids: form.allowed_subject_ids,
    }
    try {
      if (editId !== null) {
        await api.put(`/rooms/${editId}`, payload)
      } else {
        await api.post('/rooms', payload)
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
    if (!confirm('Удалить кабинет?')) return
    try {
      await api.delete(`/rooms/${id}`)
      setSnackbar({ open: true, msg: 'Удалено', severity: 'success' })
      load()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка удаления'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const openCreate = () => {
    setForm({ ...emptyForm })
    setEditId(null)
    setOpen(true)
  }

  const openEdit = (item: Room) => {
    setForm({
      name: item.name,
      capacity: item.capacity,
      comment: item.comment || '',
      allowed_subject_ids: item.allowed_subjects.map((s) => s.id),
    })
    setEditId(item.id)
    setOpen(true)
  }

  const openAvail = async (roomId: number) => {
    setAvailRoomId(roomId)
    try {
      const res = await api.get(`/availabilities?entity_type=room&entity_id=${roomId}`)
      setAvailabilities(res.data as AvailType[])
    } catch {
      setAvailabilities([])
    }
    setAvailOpen(true)
  }

  const addAvailability = async () => {
    if (!availRoomId) return
    try {
      await api.post('/availabilities', {
        entity_type: 'room',
        entity_id: availRoomId,
        day_of_week: newAvailDay,
        start_time: newAvailStart,
        end_time: newAvailEnd,
      })
      const res = await api.get(`/availabilities?entity_type=room&entity_id=${availRoomId}`)
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка удаления'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const deleteAllAvailability = async () => {
    if (!availRoomId) return
    if (!confirm('Удалить всю доступность?')) return
    try {
      await api.delete(`/availabilities/bulk?entity_type=room&entity_id=${availRoomId}`)
      setAvailabilities([])
      setSnackbar({ open: true, msg: 'Доступность удалена', severity: 'success' })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка удаления'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Кабинеты</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Добавить
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Вместимость</TableCell>
              <TableCell>Разрешённые предметы</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.name}</TableCell>
                <TableCell>{item.capacity}</TableCell>
                <TableCell>
                  {item.allowed_subjects.length > 0
                    ? item.allowed_subjects.map((s) => s.name).join(', ')
                    : 'Все'}
                </TableCell>
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
        <DialogTitle>{editId !== null ? 'Редактировать кабинет' : 'Новый кабинет'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField label="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} fullWidth />
          <TextField label="Вместимость" type="number" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Разрешённые предметы</InputLabel>
            <Select
              multiple
              value={form.allowed_subject_ids}
              label="Разрешённые предметы"
              onChange={(e) => setForm({ ...form, allowed_subject_ids: e.target.value as number[] })}
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
          <TextField label="Комментарий" value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} fullWidth multiline rows={2} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={availOpen} onClose={() => setAvailOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Доступность кабинета</DialogTitle>
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

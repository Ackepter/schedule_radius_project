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
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import api from '../api/client'
import type { Subject } from '../api/types'

const emptySubject: Partial<Subject> = {
  name: '',
  description: '',
  default_duration_minutes: 60,
  is_active: true,
}

export default function Subjects() {
  const [items, setItems] = useState<Subject[]>([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<Partial<Subject>>(emptySubject)
  const [editId, setEditId] = useState<number | null>(null)
  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const load = useCallback(async () => {
    try {
      const res = await api.get('/subjects')
      setItems(res.data as Subject[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки', severity: 'error' })
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    try {
      if (editId !== null) {
        await api.put(`/subjects/${editId}`, form)
      } else {
        await api.post('/subjects', form)
      }
      setOpen(false)
      setSnackbar({ open: true, msg: 'Сохранено', severity: 'success' })
      load()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка сохранения'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить направление?')) return
    try {
      await api.delete(`/subjects/${id}`)
      setSnackbar({ open: true, msg: 'Удалено', severity: 'success' })
      load()
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка удаления', severity: 'error' })
    }
  }

  const openCreate = () => {
    setForm({ ...emptySubject })
    setEditId(null)
    setOpen(true)
  }

  const openEdit = (item: Subject) => {
    setForm({ ...item })
    setEditId(item.id)
    setOpen(true)
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h4">Направления</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          Добавить
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Описание</TableCell>
              <TableCell>Стандартная длительность (мин)</TableCell>
              <TableCell>Активно</TableCell>
              <TableCell align="right">Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>{item.name}</TableCell>
                <TableCell>{item.description || '—'}</TableCell>
                <TableCell>{item.default_duration_minutes}</TableCell>
                <TableCell>{item.is_active ? 'Да' : 'Нет'}</TableCell>
                <TableCell align="right">
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
        <DialogTitle>{editId !== null ? 'Редактировать направление' : 'Новое направление'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <TextField
            label="Название"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            fullWidth
          />
          <TextField
            label="Описание"
            value={form.description || ''}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            fullWidth
            multiline
            rows={2}
          />
          <TextField
            label="Стандартная длительность (мин)"
            type="number"
            value={form.default_duration_minutes || 60}
            onChange={(e) => setForm({ ...form, default_duration_minutes: Number(e.target.value) })}
            fullWidth
          />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Switch
              checked={form.is_active ?? true}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            <Typography>Активно</Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
          {snackbar.msg}
        </Alert>
      </Snackbar>
    </Box>
  )
}

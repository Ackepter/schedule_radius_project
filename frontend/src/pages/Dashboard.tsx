import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Box,
  Snackbar,
  Alert,
} from '@mui/material'
import SchoolIcon from '@mui/icons-material/School'
import PersonIcon from '@mui/icons-material/Person'
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom'
import GroupsIcon from '@mui/icons-material/Groups'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import AddIcon from '@mui/icons-material/Add'
import api from '../api/client'

interface Stats {
  students: number
  teachers: number
  rooms: number
  groupRequests: number
}

async function getStats(): Promise<Stats> {
  const [s, t, r] = await Promise.all([
    api.get('/students'),
    api.get('/teachers'),
    api.get('/rooms'),
  ])
  const students = s.data as Array<{ lesson_requests: Array<{ lesson_type: string }> }>
  const groupRequests = students.reduce(
    (sum, st) =>
      sum +
      (st.lesson_requests ?? []).filter(
        (lr) => lr.lesson_type === 'group' || lr.lesson_type === 'both',
      ).length,
    0,
  )
  return {
    students: s.data.length,
    teachers: t.data.length,
    rooms: r.data.length,
    groupRequests,
  }
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<Stats>({ students: 0, teachers: 0, rooms: 0, groupRequests: 0 })
  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  useEffect(() => {
    const load = async () => {
      try {
        setStats(await getStats())
      } catch {
        setSnackbar({ open: true, msg: 'Ошибка загрузки статистики', severity: 'error' })
      }
    }
    load()
  }, [])

  const handleSeed = async () => {
    try {
      await api.post('/seed')
      setSnackbar({ open: true, msg: 'Тестовые данные загружены', severity: 'success' })
      setStats(await getStats())
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки тестовых данных', severity: 'error' })
    }
  }

  const statCards = [
    { label: 'Ученики', value: stats.students, icon: <SchoolIcon sx={{ fontSize: 40 }} />, color: '#1565c0' },
    { label: 'Педагоги', value: stats.teachers, icon: <PersonIcon sx={{ fontSize: 40 }} />, color: '#2e7d32' },
    { label: 'Кабинеты', value: stats.rooms, icon: <MeetingRoomIcon sx={{ fontSize: 40 }} />, color: '#e65100' },
    { label: 'Групповые запросы', value: stats.groupRequests, icon: <GroupsIcon sx={{ fontSize: 40 }} />, color: '#6a1b9a' },
  ]

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Панель управления
      </Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        {statCards.map((card) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={card.label}>
            <Card>
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ color: card.color }}>{card.icon}</Box>
                <Box>
                  <Typography variant="h4">{card.value}</Typography>
                  <Typography color="text.secondary">{card.label}</Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Typography variant="h5" gutterBottom>
        Быстрые действия
      </Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <Button
          variant="contained"
          startIcon={<CalendarMonthIcon />}
          onClick={() => navigate('/schedule')}
        >
          Составить расписание
        </Button>
        <Button
          variant="outlined"
          startIcon={<SchoolIcon />}
          onClick={() => navigate('/students')}
        >
          Управление учениками
        </Button>
        <Button
          variant="outlined"
          startIcon={<PersonIcon />}
          onClick={() => navigate('/teachers')}
        >
          Управление педагогами
        </Button>
        <Button
          variant="outlined"
          color="secondary"
          startIcon={<AddIcon />}
          onClick={handleSeed}
        >
          Загрузить тестовые данные
        </Button>
      </Box>

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
import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Box,
  Typography,
  Button,
  Paper,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  CircularProgress,
  IconButton,
  Divider,
} from '@mui/material'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import FileDownloadIcon from '@mui/icons-material/FileDownload'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import ScheduleIcon from '@mui/icons-material/Schedule'
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom'
import PersonIcon from '@mui/icons-material/Person'
import GroupsIcon from '@mui/icons-material/Groups'
import SchoolIcon from '@mui/icons-material/School'
import api from '../api/client'
import type {
  ScheduledLessonDetail,
  ScheduleList,
  Teacher,
  Room,
  StudentBase,
  ConflictDetail,
  Price,
} from '../api/types'
import { DayNames, DayNamesFull } from '../api/types'

const HOUR_START = 9
const HOUR_END = 20
const TOTAL_HOURS = HOUR_END - HOUR_START
const SLOT_HEIGHT = 56

interface DragData {
  lessonId: number
  originalDay: number
  originalStart: string
  originalEnd: string
}

function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

function minutesToTime(mins: number): string {
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function timeToOffsetMinutes(t: string): number {
  const mins = timeToMinutes(t)
  return mins - HOUR_START * 60
}

function getHeight(start: string, end: string): number {
  return ((timeToMinutes(end) - timeToMinutes(start)) / 15) * (SLOT_HEIGHT / 4)
}

export default function Schedule() {
  const [schedules, setSchedules] = useState<ScheduleList[]>([])
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | ''>('')
  const [lessons, setLessons] = useState<ScheduledLessonDetail[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [rooms, setRooms] = useState<Room[]>([])
  const [students, setStudents] = useState<StudentBase[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [prices, setPrices] = useState<Price[]>([])

  const [detailOpen, setDetailOpen] = useState(false)
  const [detailLesson, setDetailLesson] = useState<ScheduledLessonDetail | null>(null)

  const [editOpen, setEditOpen] = useState(false)
  const [editForm, setEditForm] = useState({
    day_of_week: 0,
    start_time: '09:00',
    end_time: '10:00',
    teacher_id: 0,
    room_id: 0,
  })
  const [editLessonId, setEditLessonId] = useState<number | null>(null)
  const [conflicts, setConflicts] = useState<ConflictDetail[]>([])
  const [conflictDialogOpen, setConflictDialogOpen] = useState(false)

  const [unscheduledOpen, setUnscheduledOpen] = useState(false)
  const [unscheduledReport, setUnscheduledReport] = useState('')
  const [unscheduledItems, setUnscheduledItems] = useState<Array<{ identifier: string; name?: string; reason: string }>>([])

  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })

  const dragRef = useRef<DragData | null>(null)
  const gridRef = useRef<HTMLDivElement>(null)

  const loadSchedules = useCallback(async () => {
    try {
      const res = await api.get('/schedules')
      const list = res.data as ScheduleList[]
      setSchedules(list)
      if (list.length > 0 && selectedScheduleId === '') {
        setSelectedScheduleId(list[0].id)
      }
    } catch {
      // ignore
    }
  }, [selectedScheduleId])

  const loadLessons = useCallback(async () => {
    if (!selectedScheduleId) return
    setLoading(true)
    try {
      const [lRes, tRes, rRes, sRes, pRes] = await Promise.all([
        api.get(`/schedules/${selectedScheduleId}/lessons`),
        api.get('/teachers'),
        api.get('/rooms'),
        api.get('/students'),
        api.get('/prices'),
      ])
      setLessons(lRes.data as ScheduledLessonDetail[])
      setTeachers(tRes.data as Teacher[])
      setRooms(rRes.data as Room[])
      setStudents(sRes.data as StudentBase[])
      setPrices(pRes.data as Price[])
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки расписания', severity: 'error' })
    }
    setLoading(false)
  }, [selectedScheduleId])

  useEffect(() => { loadSchedules() }, [loadSchedules])
  useEffect(() => { loadLessons() }, [loadLessons])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await api.post('/schedules/generate')
      const data = res.data as {
        schedule_id: number
        scheduled_count: number
        unscheduled_count: number
        unscheduled_report?: string | null
        unscheduled?: Array<{ identifier: string; name?: string; reason: string }>
      }
      setSnackbar({
        open: true,
        msg: `Расписание создано: ${data.scheduled_count} занятий размещено, ${data.unscheduled_count} не размещено`,
        severity: data.unscheduled_count > 0 ? 'error' : 'success',
      })
      await loadSchedules()
      setSelectedScheduleId(data.schedule_id)
      if (data.unscheduled_count > 0) {
        setUnscheduledReport(data.unscheduled_report || '')
        setUnscheduledItems(data.unscheduled || [])
        setUnscheduledOpen(true)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Ошибка генерации'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
    setGenerating(false)
  }

  const handleExport = async (format: string) => {
    if (!selectedScheduleId) return
    try {
      const url = `/api/export/${selectedScheduleId}?format=${format}`
      const link = document.createElement('a')
      link.href = url
      link.download = `schedule_${selectedScheduleId}.${format}`
      link.click()
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка экспорта', severity: 'error' })
    }
  }

  const openEditDialog = (lesson: ScheduledLessonDetail) => {
    setEditLessonId(lesson.id)
    setEditForm({
      day_of_week: lesson.day_of_week,
      start_time: lesson.start_time,
      end_time: lesson.end_time,
      teacher_id: lesson.teacher_id,
      room_id: lesson.room_id,
    })
    setConflicts([])
    setEditOpen(true)
  }

  const handleEditSave = async () => {
    if (!editLessonId) return
    try {
      const res = await api.put(`/schedules/scheduled-lessons/${editLessonId}`, {
        day_of_week: editForm.day_of_week,
        start_time: editForm.start_time,
        end_time: editForm.end_time,
        teacher_id: editForm.teacher_id,
        room_id: editForm.room_id,
      })
      setEditOpen(false)
      setSnackbar({ open: true, msg: 'Занятие обновлено', severity: 'success' })
      loadLessons()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { conflicts?: ConflictDetail[] } } }
        if (axiosErr.response?.status === 409 && axiosErr.response?.data?.conflicts) {
          setConflicts(axiosErr.response.data.conflicts)
          setConflictDialogOpen(true)
          return
        }
      }
      setSnackbar({ open: true, msg: 'Ошибка сохранения', severity: 'error' })
    }
  }

  const handleDeleteLesson = async (lessonId: number) => {
    if (!confirm('Удалить занятие из расписания?')) return
    try {
      await api.delete(`/schedules/scheduled-lessons/${lessonId}`)
      setSnackbar({ open: true, msg: 'Занятие удалено', severity: 'success' })
      loadLessons()
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка удаления', severity: 'error' })
    }
  }

  const handleDragStart = (e: React.DragEvent, lesson: ScheduledLessonDetail) => {
    dragRef.current = {
      lessonId: lesson.id,
      originalDay: lesson.day_of_week,
      originalStart: lesson.start_time,
      originalEnd: lesson.end_time,
    }
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(lesson.id))
    const el = e.currentTarget as HTMLElement
    el.style.opacity = '0.5'
  }

  const handleDragEnd = (e: React.DragEvent) => {
    const el = e.currentTarget as HTMLElement
    el.style.opacity = '1'
    dragRef.current = null
  }

  const handleDrop = async (e: React.DragEvent, targetDay: number) => {
    e.preventDefault()
    if (!dragRef.current || !selectedScheduleId) return

    const gridEl = gridRef.current
    if (!gridEl) return
    const rect = gridEl.getBoundingClientRect()
    const y = e.clientY - rect.top
    const minutesFromTop = Math.round((y / SLOT_HEIGHT) * 15 / 15) * 15
    const totalMinutes = HOUR_START * 60 + minutesFromTop

    const duration = timeToMinutes(dragRef.current.originalEnd) - timeToMinutes(dragRef.current.originalStart)
    const snappedStart = Math.round(totalMinutes / 15) * 15
    const snappedEnd = snappedStart + duration

    if (snappedEnd > HOUR_END * 60) {
      setSnackbar({ open: true, msg: 'Не помещается в расписание', severity: 'error' })
      return
    }

    const startTime = minutesToTime(snappedStart)
    const endTime = minutesToTime(snappedEnd)

    try {
      const res = await api.put(`/schedules/scheduled-lessons/${dragRef.current.lessonId}`, {
        day_of_week: targetDay,
        start_time: startTime,
        end_time: endTime,
      })
      setSnackbar({ open: true, msg: 'Занятие перемещено', severity: 'success' })
      loadLessons()
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { conflicts?: ConflictDetail[] } } }
        if (axiosErr.response?.status === 409 && axiosErr.response?.data?.conflicts) {
          setConflicts(axiosErr.response.data.conflicts)
          setConflictDialogOpen(true)
          return
        }
      }
      setSnackbar({ open: true, msg: 'Ошибка перемещения', severity: 'error' })
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const getTeacherName = (id: number) => {
    const t = teachers.find((tt) => tt.id === id)
    return t ? `${t.last_name} ${t.first_name}` : '—'
  }
  const getRoomName = (id: number) => {
    const r = rooms.find((rr) => rr.id === id)
    return r ? r.name : '—'
  }
  const getStudentName = (id: number | null | undefined) => {
    if (!id) return ''
    const s = students.find((ss) => ss.id === id)
    return s ? `${s.last_name} ${s.first_name}` : ''
  }
  const getSubjectFromLesson = (lesson: ScheduledLessonDetail) => {
    if (lesson.lesson_request?.subject) return lesson.lesson_request.subject.name
    if (lesson.group_lesson?.subject) return lesson.group_lesson.subject.name
    return '—'
  }
  const getParticipantsNames = (lesson: ScheduledLessonDetail) => {
    if (lesson.group_lesson?.participants) {
      return lesson.group_lesson.participants.map((p) => `${p.last_name} ${p.first_name}`).join(', ')
    }
    return ''
  }
  const openDetailDialog = (lesson: ScheduledLessonDetail) => {
    setDetailLesson(lesson)
    setDetailOpen(true)
  }
  const formatMoney = (v: number) => `${v.toLocaleString('ru-RU')} ₽`
  const getLessonPrice = (lesson: ScheduledLessonDetail) => {
    const subjectId = lesson.lesson_request?.subject_id ?? lesson.group_lesson?.subject_id ?? null
    if (subjectId === null) return null
    const candidates = prices.filter(
      (p) => p.subject_id === subjectId && p.lesson_type === lesson.lesson_type,
    )
    if (lesson.lesson_type === 'individual') {
      const p = candidates.find((c) => c.min_participants <= 1 && c.max_participants >= 1) ?? candidates[0]
      return p ? { perStudent: p.price_per_student, count: 1, total: p.price_per_student } : null
    }
    const count = lesson.group_lesson?.participants?.length ?? 0
    const p = candidates.find((c) => count >= c.min_participants && count <= c.max_participants) ?? candidates[0]
    return p ? { perStudent: p.price_per_student, count, total: p.price_per_student * count } : null
  }

  const currentSchedule = schedules.find((s) => s.id === selectedScheduleId)

  const timeSlots: string[] = []
  for (let h = HOUR_START; h < HOUR_END; h++) {
    for (let m = 0; m < 60; m += 15) {
      timeSlots.push(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`)
    }
  }
  const hourLabels: string[] = []
  for (let h = HOUR_START; h < HOUR_END; h++) {
    hourLabels.push(`${String(h).padStart(2, '0')}:00`)
  }

  const lessonsByDay: Record<number, ScheduledLessonDetail[]> = {}
  for (let d = 0; d < 6; d++) lessonsByDay[d] = []
  for (const lesson of lessons) {
    if (lesson.day_of_week < 6) {
      lessonsByDay[lesson.day_of_week].push(lesson)
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2, alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="h4">Расписание</Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel>Расписание</InputLabel>
            <Select
              value={selectedScheduleId}
              label="Расписание"
              onChange={(e) => setSelectedScheduleId(Number(e.target.value))}
            >
              {schedules.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name} ({s.status === 'active' ? 'Активное' : 'Черновик'})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="contained"
            startIcon={generating ? <CircularProgress size={20} color="inherit" /> : <CalendarMonthIcon />}
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? 'Генерация...' : 'Составить расписание'}
          </Button>
          <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={() => handleExport('png')}>
            PNG
          </Button>
          <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={() => handleExport('pdf')}>
            PDF
          </Button>
          <Button variant="outlined" startIcon={<FileDownloadIcon />} onClick={() => handleExport('xlsx')}>
            XLSX
          </Button>
        </Box>
      </Box>

      {currentSchedule && (
        <Typography variant="subtitle1" sx={{ mb: 1 }} color="text.secondary">
          {currentSchedule.name} · {lessons.length} занятий
          {currentSchedule.unscheduled_report && (
            <Button size="small" sx={{ ml: 2 }} onClick={() => setUnscheduledOpen(true)}>
              Неразмещённые занятия
            </Button>
          )}
        </Typography>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <Box sx={{ display: 'flex', overflowX: 'auto' }}>
          <Box sx={{ minWidth: 60, flexShrink: 0 }}>
            <Box sx={{ height: 40 }} />
            {hourLabels.map((label, i) => (
              <Box
                key={i}
                sx={{
                  height: SLOT_HEIGHT,
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'flex-end',
                  pr: 1,
                  pt: 0.5,
                  fontSize: 12,
                  color: 'text.secondary',
                }}
              >
                {label}
              </Box>
            ))}
          </Box>

          {[0, 1, 2, 3, 4, 5].map((day) => (
            <Box
              key={day}
              sx={{
                flex: 1,
                minWidth: 150,
                borderLeft: '1px solid #e0e0e0',
              }}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, day)}
            >
              <Box
                sx={{
                  height: 40,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'primary.main',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: 14,
                }}
              >
                {DayNamesFull[day]}
              </Box>
              <Box ref={day === 0 ? gridRef : undefined} sx={{ position: 'relative' }}>
                {hourLabels.map((_, i) => (
                  <Box
                    key={i}
                    sx={{
                      height: SLOT_HEIGHT,
                      borderBottom: '1px solid #f0f0f0',
                    }}
                  />
                ))}
                {lessonsByDay[day].map((lesson) => {
                  const offset = timeToOffsetMinutes(lesson.start_time)
                  const top = (offset / 15) * (SLOT_HEIGHT / 4)
                  const height = getHeight(lesson.start_time, lesson.end_time)
                  const subject = getSubjectFromLesson(lesson)
                  return (
                    <Paper
                      key={lesson.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, lesson)}
                      onDragEnd={handleDragEnd}
                      onClick={() => { if (!dragRef.current) openDetailDialog(lesson) }}
                      title="Нажмите, чтобы увидеть подробности"
                      sx={{
                        position: 'absolute',
                        top: `${top}px`,
                        left: 2,
                        right: 2,
                        height: `${Math.max(height, 40)}px`,
                        bgcolor: lesson.lesson_type === 'individual' ? '#e3f2fd' : '#f3e5f5',
                        borderLeft: lesson.lesson_type === 'individual' ? '4px solid #1565c0' : '4px solid #6a1b9a',
                        overflow: 'hidden',
                        cursor: 'grab',
                        userSelect: 'none',
                        '&:hover': { boxShadow: 3 },
                        p: 0.5,
                        fontSize: 11,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Typography variant="caption" sx={{ fontWeight: 'bold', lineHeight: 1.2 }}>
                          {lesson.start_time}–{lesson.end_time}
                        </Typography>
                        <Box>
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); openDetailDialog(lesson) }}
                            sx={{ p: 0 }}
                            title="Подробнее"
                          >
                            <InfoOutlinedIcon sx={{ fontSize: 14 }} />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); openEditDialog(lesson) }}
                            sx={{ p: 0 }}
                          >
                            <EditIcon sx={{ fontSize: 14 }} />
                          </IconButton>
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); handleDeleteLesson(lesson.id) }}
                            sx={{ p: 0 }}
                          >
                            <DeleteIcon sx={{ fontSize: 14 }} color="error" />
                          </IconButton>
                        </Box>
                      </Box>
                      <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', lineHeight: 1.2 }}>
                        {subject}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.2, color: 'text.secondary' }}>
                        {lesson.lesson_type === 'individual' ? 'Индивид.' : 'Групп.'} · {getTeacherName(lesson.teacher_id)}
                      </Typography>
                      <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.2, color: 'text.secondary' }}>
                        {getRoomName(lesson.room_id)}
                      </Typography>
                      {lesson.student && (
                        <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.2 }}>
                          {getStudentName(lesson.student_id)}
                        </Typography>
                      )}
                      {lesson.group_lesson && height > 70 && (
                        <Typography variant="caption" sx={{ display: 'block', lineHeight: 1.2, fontSize: 10, color: 'text.secondary' }}>
                          {getParticipantsNames(lesson)}
                        </Typography>
                      )}
                    </Paper>
                  )
                })}
              </Box>
            </Box>
          ))}
        </Box>
      )}

      <Dialog open={detailOpen} onClose={() => setDetailOpen(false)} maxWidth="sm" fullWidth>
        {detailLesson && (
          <>
            <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', pb: 1 }}>
              <Chip
                label={detailLesson.lesson_type === 'individual' ? 'Индивидуальное' : `Групповое${detailLesson.group_lesson?.participants?.length ? ` · ${detailLesson.group_lesson.participants.length} чел.` : ''}`}
                color={detailLesson.lesson_type === 'individual' ? 'primary' : 'secondary'}
                size="small"
              />
              <Typography variant="h6">{getSubjectFromLesson(detailLesson)}</Typography>
            </DialogTitle>
            <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.2 }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <ScheduleIcon fontSize="small" color="action" />
                <Typography>
                  {DayNamesFull[detailLesson.day_of_week]} · {detailLesson.start_time}–{detailLesson.end_time}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <PersonIcon fontSize="small" color="action" />
                <Typography>
                  Педагог:{' '}
                  {detailLesson.teacher
                    ? `${detailLesson.teacher.last_name} ${detailLesson.teacher.first_name}`
                    : getTeacherName(detailLesson.teacher_id)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                <MeetingRoomIcon fontSize="small" color="action" />
                <Typography>
                  Кабинет: {detailLesson.room ? detailLesson.room.name : getRoomName(detailLesson.room_id)}
                </Typography>
              </Box>
              {detailLesson.lesson_type === 'individual' && detailLesson.student && (
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <SchoolIcon fontSize="small" color="action" />
                  <Typography>
                    Ребёнок: {detailLesson.student.last_name} {detailLesson.student.first_name}
                  </Typography>
                </Box>
              )}
              {detailLesson.lesson_type === 'group' && detailLesson.group_lesson && (
                <Box>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                    <GroupsIcon fontSize="small" color="action" />
                    <Typography>Участники ({detailLesson.group_lesson.participants.length}):</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {detailLesson.group_lesson.participants.map((p) => (
                      <Chip key={p.id} size="small" label={`${p.last_name} ${p.first_name}`} />
                    ))}
                  </Box>
                </Box>
              )}
              {(() => {
                const pr = getLessonPrice(detailLesson)
                if (!pr) return null
                return (
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 1 }}>
                    <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                      {detailLesson.lesson_type === 'group'
                        ? `${formatMoney(pr.perStudent)} / чел. · всего ${formatMoney(pr.total)}`
                        : `Стоимость: ${formatMoney(pr.total)}`}
                    </Typography>
                  </Box>
                )
              })()}
              {detailLesson.group_lesson?.comment && (
                <Typography variant="body2" color="text.secondary">
                  Комментарий: {detailLesson.group_lesson.comment}
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailOpen(false)}>Закрыть</Button>
              <Button color="error" onClick={() => { setDetailOpen(false); handleDeleteLesson(detailLesson.id) }}>
                Удалить
              </Button>
              <Button variant="contained" onClick={() => { setDetailOpen(false); openEditDialog(detailLesson) }}>
                Редактировать
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      <Dialog open={editOpen} onClose={() => setEditOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Редактировать занятие</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '16px !important' }}>
          <FormControl fullWidth>
            <InputLabel>День недели</InputLabel>
            <Select value={editForm.day_of_week} label="День недели" onChange={(e) => setEditForm({ ...editForm, day_of_week: Number(e.target.value) })}>
              {DayNames.map((d, i) => (
                <MenuItem key={i} value={i}>{d}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField label="Время начала" type="time" value={editForm.start_time} onChange={(e) => setEditForm({ ...editForm, start_time: e.target.value })} fullWidth slotProps={{ inputLabel: { shrink: true } }} />
          <TextField label="Время окончания" type="time" value={editForm.end_time} onChange={(e) => setEditForm({ ...editForm, end_time: e.target.value })} fullWidth slotProps={{ inputLabel: { shrink: true } }} />
          <FormControl fullWidth>
            <InputLabel>Педагог</InputLabel>
            <Select value={editForm.teacher_id} label="Педагог" onChange={(e) => setEditForm({ ...editForm, teacher_id: Number(e.target.value) })}>
              {teachers.map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.last_name} {t.first_name}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Кабинет</InputLabel>
            <Select value={editForm.room_id} label="Кабинет" onChange={(e) => setEditForm({ ...editForm, room_id: Number(e.target.value) })}>
              {rooms.map((r) => (
                <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditOpen(false)}>Отмена</Button>
          <Button variant="contained" onClick={handleEditSave}>Сохранить</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={conflictDialogOpen} onClose={() => setConflictDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ color: 'error.main' }}>Конфликт</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>Не удалось сохранить изменения из-за конфликтов:</Typography>
          {conflicts.map((c, i) => (
            <Chip key={i} label={c.message} color="error" sx={{ mr: 1, mb: 1 }} />
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConflictDialogOpen(false)}>Закрыть</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={unscheduledOpen} onClose={() => setUnscheduledOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Неразмещённые занятия</DialogTitle>
        <DialogContent>
          {unscheduledReport && (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mb: 2 }}>
              {unscheduledReport}
            </Typography>
          )}
          {unscheduledItems.map((item, i) => (
            <Paper key={i} sx={{ p: 1.5, mb: 1, borderLeft: '4px solid #f44336' }}>
              <Typography variant="subtitle2">{item.identifier}</Typography>
              {item.name && <Typography variant="body2">{item.name}</Typography>}
              <Typography variant="body2" color="text.secondary">{item.reason}</Typography>
            </Paper>
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUnscheduledOpen(false)}>Закрыть</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={snackbar.open} autoHideDuration={3000} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar((s) => ({ ...s, open: false }))}>{snackbar.msg}</Alert>
      </Snackbar>
    </Box>
  )
}

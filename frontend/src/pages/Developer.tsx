import { useRef, useState } from 'react'
import {
  Box,
  Typography,
  Paper,
  Button,
  Card,
  CardContent,
  Stack,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  Snackbar,
  Grow,
  Alert,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import DeleteForeverIcon from '@mui/icons-material/DeleteForever'
import StorageIcon from '@mui/icons-material/Storage'
import api from '../api/client'

interface ImportResult {
  message: string
  counts: Record<string, number>
  warnings: string[]
}

export default function Developer() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [snackbar, setSnackbar] = useState<{ open: boolean; msg: string; severity: 'success' | 'error' }>({
    open: false, msg: '', severity: 'success',
  })
  const [result, setResult] = useState<ImportResult | null>(null)

  const handleExport = async () => {
    try {
      const res = await api.get('/dev/export')
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `backup-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setSnackbar({ open: true, msg: 'Данные выгружены в JSON-файл', severity: 'success' })
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка выгрузки данных', severity: 'error' })
    }
  }

  const handleImportClick = () => fileRef.current?.click()

  const handleImportFile = async (file: File | undefined) => {
    if (!file) return
    if (!confirm(`Загрузить файл «${file.name}»?\n\nВнимание: текущие данные будут удалены и заменены данными из файла.`)) {
      return
    }
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      const res = await api.post('/dev/import', parsed)
      setResult(res.data as ImportResult)
      setSnackbar({ open: true, msg: 'Импорт выполнен успешно', severity: 'success' })
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Ошибка импорта'
      setSnackbar({ open: true, msg, severity: 'error' })
    }
  }

  const handleWipe = async () => {
    if (!confirm('Удалить ВСЕ данные? (ученики, педагоги, направления, кабинеты, цены, расписания)\nЭто действие необратимо.')) return
    try {
      await api.post('/dev/wipe')
      setSnackbar({ open: true, msg: 'Все данные удалены', severity: 'success' })
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка удаления данных', severity: 'error' })
    }
  }

  const handleSeed = async () => {
    if (!confirm('Заполнить базу демонстрационными данными? Текущие данные будут удалены.')) return
    try {
      await api.post('/seed')
      setSnackbar({ open: true, msg: 'Демо-данные загружены', severity: 'success' })
    } catch {
      setSnackbar({ open: true, msg: 'Ошибка загрузки демо-данных', severity: 'error' })
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h5">Раздел разработчика</Typography>
      <Typography variant="body2" color="text.secondary">
        Инструменты для работы с данными: выгрузка/загрузка JSON и полная очистка базы.
        Формат JSON описан в файле <code>AI_IMPORT_GUIDE.md</code> в корне проекта —
        его можно составлять вручную или с помощью ИИ по рукописным записям.
      </Typography>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
        <Card sx={{ flex: '1 1 280px' }}>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Chip icon={<DownloadIcon />} label="Экспорт данных" color="primary" variant="outlined" sx={{ width: 'fit-content' }} />
            <Typography variant="body2" color="text.secondary">
              Выгружает всю базу (справочники, цены, требования, расписания) в файл{' '}
              <code>backup-Дата.json</code>.
            </Typography>
            <Button variant="contained" startIcon={<DownloadIcon />} onClick={handleExport}>
              Выгрузить JSON
            </Button>
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 280px' }}>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Chip icon={<UploadFileIcon />} label="Импорт данных" color="secondary" variant="outlined" sx={{ width: 'fit-content' }} />
            <Typography variant="body2" color="text.secondary">
              Загрузка JSON полностью заменяет текущие данные. Связи указываются по именам.
            </Typography>
            <Button variant="contained" color="secondary" startIcon={<UploadFileIcon />} onClick={handleImportClick}>
              Выбрать JSON-файл
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              style={{ display: 'none' }}
              onChange={(e) => { void handleImportFile(e.target.files?.[0]); e.target.value = '' }}
            />
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 280px' }}>
          <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Chip icon={<DeleteForeverIcon />} label="Очистка базы" color="error" variant="outlined" sx={{ width: 'fit-content' }} />
            <Typography variant="body2" color="text.secondary">
              Полное удаление всех данных. Можно снова наполнить базу демо-данными.
            </Typography>
            <Button variant="outlined" color="error" startIcon={<DeleteForeverIcon />} onClick={handleWipe}>
              Удалить все данные
            </Button>
            <Button variant="text" size="small" startIcon={<StorageIcon />} onClick={handleSeed} title="Заполнить базу демонстрационными данными">
              Заполнить демо-данными
            </Button>
          </CardContent>
        </Card>
      </Box>

      {result && (
        <Grow in={Boolean(result)} mountOnEnter unmountOnExit>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Результат импорта
            </Typography>
            <Stack direction="row" useFlexGap sx={{ gap: 1, mb: 1, flexWrap: 'wrap' }}>
              {Object.entries(result.counts).map(([k, v]) => (
                <Chip key={k} size="small" label={`${k}: ${v}`} />
              ))}
            </Stack>
            {result.warnings.length > 0 && (
              <Alert severity="warning" sx={{ mt: 1 }}>
                <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold' }}>
                  Замечания ({result.warnings.length}):
                </Typography>
                <List dense disablePadding>
                  {result.warnings.map((w, i) => (
                    <ListItem key={i} disablePadding sx={{ py: 0.2 }}>
                      <ListItemIcon sx={{ minWidth: 20 }}>•</ListItemIcon>
                      <Typography variant="body2">{w}</Typography>
                    </ListItem>
                  ))}
                </List>
              </Alert>
            )}
            <Button size="small" sx={{ mt: 1 }} onClick={() => setResult(null)}>
              Закрыть
            </Button>
          </Paper>
        </Grow>
      )}

      <Snackbar open={snackbar.open} autoHideDuration={4000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} variant="filled" sx={{ width: '100%' }}>
          {snackbar.msg}
        </Alert>
      </Snackbar>
    </Box>
  )
}
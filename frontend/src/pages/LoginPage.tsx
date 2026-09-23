import type { FormEvent } from 'react'
import { useState } from 'react'
import { Button, Stack, TextField, Typography, Box, Paper, Alert } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? 'Не удалось войти. Попробуйте позже.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
      }}
    >
      <Paper sx={{ p: 4, width: 360 }} elevation={3}>
        <Stack spacing={2}>
          <Typography variant="h5" align="center">
            Центр детских занятий
          </Typography>
          <Typography variant="body2" align="center" color="text.secondary">
            Вход в систему
          </Typography>
          <form onSubmit={handleSubmit}>
            <Stack spacing={2}>
              <TextField
                label="Имя пользователя"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
                fullWidth
              />
              <TextField
                label="Пароль"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                fullWidth
              />
              {error && <Alert severity="error">{error}</Alert>}
              <Button
                type="submit"
                variant="contained"
                disabled={submitting}
                fullWidth
              >
                Войти
              </Button>
            </Stack>
          </form>
        </Stack>
      </Paper>
    </Box>
  )
}
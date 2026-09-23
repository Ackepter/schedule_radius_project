import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
  withCredentials: true,
})

client.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data === 'object' && !(res.data instanceof Blob)) {
      if ('data' in res.data) {
        res.data = (res.data as { data: unknown }).data
      } else if ('items' in res.data) {
        res.data = (res.data as { items: unknown }).items
      }
    }
    return res
  },
  (error) => {
    const status: number = error?.response?.status
    const url: string = error?.config?.url ?? ''

    if (status === 401 && !url.includes('/auth/login') && !url.includes('/auth/logout')) {
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    const detail: unknown = error?.response?.data?.detail
    if (typeof detail === 'string' && detail) {
      error.message = detail
    } else if (Array.isArray(detail) && detail.length) {
      error.message = detail.map((d: { msg?: string }) => d?.msg ?? '').filter(Boolean).join('; ')
    }
    return Promise.reject(error)
  },
)

export default client

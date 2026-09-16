import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
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

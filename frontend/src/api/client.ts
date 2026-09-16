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
  (err) => Promise.reject(err),
)

export default client

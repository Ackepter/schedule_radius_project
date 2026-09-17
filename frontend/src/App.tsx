import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Box,
  Divider,
} from '@mui/material'
import DashboardIcon from '@mui/icons-material/Dashboard'
import SchoolIcon from '@mui/icons-material/School'
import PersonIcon from '@mui/icons-material/Person'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom'
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import DeveloperModeIcon from '@mui/icons-material/DeveloperMode'
import Dashboard from './pages/Dashboard'
import Students from './pages/Students'
import Teachers from './pages/Teachers'
import Subjects from './pages/Subjects'
import Rooms from './pages/Rooms'
import Schedule from './pages/Schedule'
import Finance from './pages/Finance'
import Developer from './pages/Developer'

const DRAWER_WIDTH = 260

const MAIN_NAV_ITEMS = [
  { label: 'Главная', path: '/', icon: <DashboardIcon /> },
  { label: 'Ученики', path: '/students', icon: <SchoolIcon /> },
  { label: 'Педагоги', path: '/teachers', icon: <PersonIcon /> },
  { label: 'Направления', path: '/subjects', icon: <MenuBookIcon /> },
  { label: 'Кабинеты', path: '/rooms', icon: <MeetingRoomIcon /> },
  { label: 'Расписание', path: '/schedule', icon: <CalendarMonthIcon /> },
  { label: 'Финансы', path: '/finance', icon: <AccountBalanceIcon /> },
]

const DEV_NAV_ITEMS = [
  { label: 'Для разработчика', path: '/developer', icon: <DeveloperModeIcon /> },
]

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap sx={{ flexGrow: 1 }}>
            Центр детских занятий — Расписание
          </Typography>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
      >
        <Toolbar />
        <List>
          {MAIN_NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.path}
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
        <Divider />
        <List>
          {DEV_NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.path}
              selected={location.pathname === item.path}
              onClick={() => navigate(item.path)}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, ml: `${DRAWER_WIDTH}px` }}>
        <Toolbar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/students" element={<Students />} />
          <Route path="/teachers" element={<Teachers />} />
          <Route path="/subjects" element={<Subjects />} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/finance" element={<Finance />} />
          <Route path="/developer" element={<Developer />} />
        </Routes>
      </Box>
    </Box>
  )
}

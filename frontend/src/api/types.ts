export const LessonTypeEnum = {
  individual: 'individual',
  group: 'group',
  both: 'both',
} as const
export type LessonType = (typeof LessonTypeEnum)[keyof typeof LessonTypeEnum]

export const ScheduleStatusEnum = {
  draft: 'draft',
  active: 'active',
} as const
export type ScheduleStatus = (typeof ScheduleStatusEnum)[keyof typeof ScheduleStatusEnum]

export const EntityTypeEnum = {
  student: 'student',
  teacher: 'teacher',
  room: 'room',
  lesson_request: 'lesson_request',
} as const
export type EntityType = (typeof EntityTypeEnum)[keyof typeof EntityTypeEnum]

export const ExportFormatEnum = {
  png: 'png',
  pdf: 'pdf',
  xlsx: 'xlsx',
} as const
export type ExportFormat = (typeof ExportFormatEnum)[keyof typeof ExportFormatEnum]

export const ConflictTypeEnum = {
  teacher_busy: 'teacher_busy',
  room_busy: 'room_busy',
  student_busy: 'student_busy',
  teacher_required: 'teacher_required',
  room_capacity: 'room_capacity',
  subject_mismatch: 'subject_mismatch',
} as const
export type ConflictType = (typeof ConflictTypeEnum)[keyof typeof ConflictTypeEnum]

export const DayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] as const
export const DayNamesFull = [
  'Понедельник',
  'Вторник',
  'Среда',
  'Четверг',
  'Пятница',
  'Суббота',
  'Воскресенье',
] as const

export interface Subject {
  id: number
  name: string
  description?: string | null
  default_duration_minutes: number
  is_active: boolean
}

export interface Parent {
  id: number
  first_name: string
  last_name: string
  phone?: string | null
  email?: string | null
  comment?: string | null
}

export interface ParentList extends Parent {
  students: StudentBase[]
}

export interface StudentBase {
  id: number
  first_name: string
  last_name: string
  birth_date?: string | null
  comment?: string | null
  is_active: boolean
  parent_id?: number | null
}

export interface StudentList extends StudentBase {
  parent?: Parent | null
  lesson_requests: LessonRequestBase[]
}

export interface Teacher {
  id: number
  first_name: string
  last_name: string
  comment?: string | null
  is_active: boolean
  max_weekly_hours?: number | null
  subjects: Subject[]
}

export interface Room {
  id: number
  name: string
  capacity: number
  comment?: string | null
  allowed_subjects: Subject[]
}

export interface Availability {
  id?: number | null
  entity_type: EntityType
  entity_id: number
  day_of_week: number
  start_time: string
  end_time: string
}

export interface LessonRequestBase {
  id: number
  student_id: number
  subject_id: number
  lesson_type: LessonType
  lessons_per_week: number
  duration_minutes: number
  preferred_teacher_id?: number | null
  teacher_is_required: boolean
  priority: number
  notes?: string | null
  subject?: Subject | null
  preferred_teacher?: Teacher | null
  excluded_students: StudentBase[]
}

export interface LessonRequestList extends LessonRequestBase {
  student?: StudentBase | null
}

export interface Price {
  id: number
  subject_id: number
  lesson_type: LessonType
  min_participants: number
  max_participants: number
  price_per_student: number
  subject?: Subject | null
}

export interface ScheduleBase {
  id: number
  name: string
  week_start: string
  status: ScheduleStatus
  unscheduled_report?: string | null
}

export interface ScheduledLessonBase {
  id: number
  schedule_id: number
  lesson_type: LessonType
  lesson_request_id?: number | null
  student_id?: number | null
  lesson_request_ids: number[]
  day_of_week: number
  start_time: string
  end_time: string
  teacher_id: number
  room_id: number
}

export interface ScheduledLessonParticipant {
  lesson_request_id: number
  student?: StudentBase | null
  subject?: Subject | null
}

export interface ScheduledLessonDetail extends ScheduledLessonBase {
  schedule?: ScheduleBase | null
  lesson_request?: LessonRequestBase | null
  student?: StudentBase | null
  participants: ScheduledLessonParticipant[]
  teacher?: Teacher | null
  room?: Room | null
}

export interface ScheduleList extends ScheduleBase {
  lessons: ScheduledLessonBase[]
}

export interface OptimizerSettings {
  id: number
  time_limit_seconds: number
  weight_presence: number
  reward_preferred_teacher: number
  penalty_student_same_day: number
  penalty_early_late: number
  early_hour: number
  late_hour: number
  weight_teacher_balance: number
  weight_room_balance: number
  group_min_size: number
  group_max_size: number
}

export interface ScheduleGenerateResponse {
  schedule_id: number
  status: ScheduleStatus
  generated_at: string
  total_lessons: number
  scheduled_count: number
  unscheduled_count: number
  unscheduled_report?: string | null
  unscheduled: UnscheduledItem[]
}

export interface UnscheduledItem {
  identifier: string
  name?: string | null
  reason: string
  suggestions?: string[]
  level?: string
}

export interface ConflictDetail {
  conflict_type: ConflictType
  message: string
  conflicting_lesson_id?: number | null
}

export interface ConflictCheckResponse {
  has_conflicts: boolean
  conflicts: ConflictDetail[]
}

export interface FinanceSummary {
  schedule_id?: number | null
  period_start: string
  period_end: string
  total_revenue: number
  total_lessons: number
  individual_lessons: number
  group_lessons: number
  total_student_hours: number
  average_lesson_price: number
  revenue_by_subject: Record<string, number>
  revenue_by_lesson_type: Record<string, number>
}

export interface ListResponse<T> {
  items: T[]
  total: number
}

export interface DataResponse<T> {
  data: T
}

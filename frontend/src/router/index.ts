import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/teacher',
    component: () => import('../layouts/TeacherLayout.vue'),
    meta: { requiresAuth: true, role: 'teacher' },
    children: [
      {
        path: 'dashboard',
        name: 'TeacherDashboard',
        component: () => import('../views/teacher/DashboardView.vue'),
      },
      {
        path: 'classes',
        name: 'TeacherClasses',
        component: () => import('../views/teacher/ClassesView.vue'),
      },
      {
        path: 'classes/:id',
        name: 'TeacherClassDetail',
        component: () => import('../views/teacher/ClassDetailView.vue'),
      },
      {
        path: 'classes/:id/report',
        name: 'TeacherClassReport',
        component: () => import('../views/teacher/ClassReportView.vue'),
      },
      {
        path: 'assignments',
        name: 'TeacherAssignments',
        component: () => import('../views/teacher/AssignmentsView.vue'),
      },
      {
        path: 'assignments/create',
        name: 'AssignmentCreate',
        component: () => import('../views/teacher/AssignmentCreateView.vue'),
      },
      {
        path: 'grading',
        name: 'GradingReview',
        component: () => import('../views/teacher/GradingReviewView.vue'),
      },
      {
        path: 'submissions/:id',
        name: 'TeacherSubmissionDetail',
        component: () => import('../views/teacher/SubmissionDetailView.vue'),
      },
    ],
  },
  {
    path: '/student',
    component: () => import('../layouts/StudentLayout.vue'),
    meta: { requiresAuth: true, role: 'student' },
    children: [
      {
        path: 'dashboard',
        name: 'StudentDashboard',
        component: () => import('../views/student/AssignmentsView.vue'),
      },
      {
        path: 'submit/:id',
        name: 'StudentSubmit',
        component: () => import('../views/student/SubmitView.vue'),
      },
      {
        path: 'result/:id',
        name: 'StudentResult',
        component: () => import('../views/student/ResultView.vue'),
      },
      {
        path: 'profile',
        name: 'StudentProfile',
        component: () => import('../views/student/ProfileView.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  if (!authStore.isLoggedIn && localStorage.getItem('access_token')) {
    await authStore.init()
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  if (to.meta.role && authStore.user?.role !== to.meta.role) {
    const redirect = authStore.isTeacher ? '/teacher/dashboard' : '/student/dashboard'
    next(redirect)
    return
  }

  if (to.path === '/login' && authStore.isLoggedIn) {
    const redirect = authStore.isTeacher ? '/teacher/dashboard' : '/student/dashboard'
    next(redirect)
    return
  }

  next()
})

export default router

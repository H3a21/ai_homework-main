import { expect, test, type Page } from '@playwright/test'


const runId = process.env.DOCKER_E2E_RUN_ID
if (!runId) throw new Error('DOCKER_E2E_RUN_ID is required')

const password = 'E2e-demo-123'
const teacherUsername = `e2e_teacher_${runId}`
const studentUsername = `e2e_student_${runId}`
const teacherName = `E2E教师-${runId}`
const studentName = `E2E学生-${runId}`
const className = `E2E班级-${runId}`
const studentAssignmentTitle = `E2E学生提交-${runId}`
const teacherAssignmentTitle = `E2E教师发布-${runId}`
const batchAssignmentTitle = `E2E批量批改-${runId}`
const pngBytes = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
)

let createdSubmissionId = 0

async function login(
  page: Page,
  role: 'teacher' | 'student',
  username: string,
) {
  await page.goto('/login')
  await page.getByRole('button', {
    name: role === 'teacher' ? '教师端' : '学生端',
  }).click()
  await page.getByTestId('login-account').fill(username)
  await page.getByTestId('login-password').fill(password)
  await page.getByTestId('login-submit').click()
  await expect(page).toHaveURL(
    role === 'teacher'
      ? /\/teacher\/dashboard$/
      : /\/student\/dashboard$/,
  )
}

test.describe.serial('Docker course workflows', () => {
  test('teacher creates an assignment for the managed class', async ({ page }) => {
    await login(page, 'teacher', teacherUsername)
    await expect(page.getByText(teacherName, { exact: true })).toBeVisible()

    await page.getByRole('link', { name: '作业管理' }).click()
    await page.getByRole('button', { name: '布置作业' }).click()
    await expect(page).toHaveURL(/\/teacher\/assignments\/create$/)

    await page.getByPlaceholder('如：第三章综合练习').fill(teacherAssignmentTitle)
    const selects = page.locator('.form-row select')
    await selects.nth(0).selectOption({ label: className })
    await selects.nth(1).selectOption('1')
    await page.locator('#q-content-1').fill('计算 6 × 7')
    await page.locator('.score-input').fill('10')
    await page.getByRole('button', { name: '发布作业' }).click()

    await expect(page).toHaveURL(/\/teacher\/assignments$/)
    await expect(page.getByText(teacherAssignmentTitle)).toBeVisible()
    await expect(page.getByText(className).first()).toBeVisible()
  })

  test('student uploads an image and receives realtime grading', async ({ page }) => {
    let realtimeSocketSeen = false
    page.on('websocket', websocket => {
      if (websocket.url().includes('/api/ws/submissions/')) {
        realtimeSocketSeen = true
      }
    })

    await login(page, 'student', studentUsername)
    await expect(page.getByText(studentName, { exact: true })).toBeVisible()

    const assignment = page.locator('.asg-card').filter({
      hasText: studentAssignmentTitle,
    })
    await expect(assignment).toBeVisible()
    await assignment.getByRole('button', { name: '提交作业' }).click()
    await page.getByTestId('submission-images').setInputFiles({
      name: 'answer.png',
      mimeType: 'image/png',
      buffer: pngBytes,
    })
    await expect(page.getByAltText('answer.png')).toBeVisible()
    await page.getByTestId('submit-assignment').click()

    await expect(page).toHaveURL(/\/student\/result\/\d+$/)
    createdSubmissionId = Number(page.url().split('/').pop())
    expect(createdSubmissionId).toBeGreaterThan(0)
    await expect(page.getByTestId('grading-summary')).toBeVisible()
    await expect(page.getByTestId('grading-score')).toBeVisible({
      timeout: 90_000,
    })
    await expect(page.getByText('已批改').first()).toBeVisible()
    expect(realtimeSocketSeen).toBe(true)
  })

  test('teacher reviews grading and opens the class report', async ({ page }) => {
    expect(createdSubmissionId).toBeGreaterThan(0)
    await login(page, 'teacher', teacherUsername)

    await page.getByRole('link', { name: '批改审核' }).click()
    const submission = page.locator('.sub-card').filter({
      hasText: studentAssignmentTitle,
    })
    await expect(submission).toContainText(studentName)
    await expect(submission).toContainText('已批改')
    await submission.getByRole('button', { name: '查看批改' }).click()

    await expect(page).toHaveURL(
      new RegExp(`/teacher/submissions/${createdSubmissionId}$`),
    )
    await expect(page.getByRole('heading', { name: '批改详情' })).toBeVisible()
    await expect(page.getByText(studentName).first()).toBeVisible()
    await expect(page.getByText(studentAssignmentTitle).first()).toBeVisible()

    await page.getByRole('link', { name: '班级管理' }).click()
    const classroom = page.locator('.class-card').filter({ hasText: className })
    await classroom.click()
    await page.getByRole('button', { name: '班级学情' }).click()

    await expect(page.getByRole('heading', { name: className })).toBeVisible()
    const studentsWithData = page.locator('.metric').filter({ hasText: '已有数据' })
    await expect(studentsWithData.locator('strong')).toHaveText('1')
    await expect(page.getByText(studentName).first()).toBeVisible()
  })

  test('teacher starts a batch and sees aggregate progress', async ({ page }) => {
    await login(page, 'teacher', teacherUsername)
    await page.getByRole('link', { name: '批改审核' }).click()

    await page.locator('.filter-select').selectOption({ label: batchAssignmentTitle })
    const batchSubmissions = page.locator('.sub-card').filter({
      hasText: batchAssignmentTitle,
    })
    await expect(batchSubmissions).toHaveCount(2)
    await page.getByRole('button', { name: '批量批改 2' }).click()

    const progress = page.locator('.batch-progress')
    await expect(progress).toBeVisible()
    await expect(progress.getByText('批次已完成')).toBeVisible({ timeout: 90_000 })
    await expect(progress.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    await expect(batchSubmissions.filter({ hasText: '已批改' })).toHaveCount(2)
  })
})

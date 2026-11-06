import { expect, test } from '@playwright/test'


test('student can log in, submit homework, and view grading result', async ({ page }) => {
  let gradingCompleted = false
  let resultRequests = 0
  await page.route('**/api/auth/login', async route => {
    await route.fulfill({
      json: { access_token: 'e2e-access', refresh_token: 'e2e-refresh', token_type: 'bearer' },
    })
  })
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({
      json: { id: 8, username: 'e2e_student', display_name: 'E2E Student', role: 'student' },
    })
  })
  await page.route('**/api/assignments/101', async route => {
    await route.fulfill({
      json: {
        id: 101,
        title: 'E2E Assignment',
        class_id: 1,
        class_name: 'E2E Class',
        subject_id: 1,
        subject_name: 'Math',
        teacher_id: 5,
        questions: [
          { id: 201, question_number: 1, content: '2 + 2', max_score: 10 },
        ],
      },
    })
  })
  await page.route('**/api/assignments', async route => {
    await route.fulfill({
      json: [{
        id: 101,
        title: 'E2E Assignment',
        class_id: 1,
        class_name: 'E2E Class',
        subject_id: 1,
        subject_name: 'Math',
        teacher_id: 5,
        question_count: 1,
      }],
    })
  })
  await page.route('**/api/submissions/501', async route => {
    resultRequests += 1
    await route.fulfill({
      json: {
        id: 501,
        assignment_id: 101,
        assignment_title: 'E2E Assignment',
        student_id: 8,
        student_name: 'E2E Student',
        status: gradingCompleted ? 'completed' : 'grading',
        total_score: gradingCompleted ? 9 : null,
        comment: gradingCompleted ? 'Good progress.' : null,
        submitted_at: '2026-07-19T00:00:00',
        graded_at: gradingCompleted ? '2026-07-19T00:00:05' : null,
        images: [],
        questions: [
          {
            id: 201,
            question_number: 1,
            content: '2 + 2',
            max_score: 10,
            score: gradingCompleted ? 9 : null,
            feedback: gradingCompleted ? 'Correct method.' : null,
          },
        ],
      },
    })
  })
  await page.routeWebSocket('**/api/ws/submissions/501', websocket => {
    websocket.onMessage(message => {
      expect(JSON.parse(String(message))).toEqual({ type: 'auth', token: 'e2e-access' })
      gradingCompleted = true
      websocket.send(JSON.stringify({
        type: 'submission.status',
        submission_id: 501,
        status: 'completed',
      }))
    })
  })
  await page.route('**/api/submissions/images', async route => {
    await route.fulfill({
      status: 201,
      json: {
        image_path: `submissions/8/${'a'.repeat(32)}.png`,
        filename: 'homework.png',
        content_type: 'image/png',
        size: 12,
      },
    })
  })
  await page.route('**/api/submissions', async route => {
    if (route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload.image_paths).toEqual([`submissions/8/${'a'.repeat(32)}.png`])
      await route.fulfill({
        status: 202,
        json: { id: 501, assignment_id: 101, status: 'grading', task_id: 'task-e2e' },
      })
      return
    }
    await route.fulfill({ json: [] })
  })

  await page.goto('/login')
  await page.getByTestId('role-student').click()
  await page.getByTestId('login-account').fill('e2e_student')
  await page.getByTestId('login-password').fill('demo123')
  await page.getByTestId('login-submit').click()

  await expect(page).toHaveURL(/\/student\/dashboard$/)
  await expect(page.getByText('E2E Assignment')).toBeVisible()
  await page.getByTestId('assignment-submit-101').click()

  await expect(page).toHaveURL(/\/student\/submit\/101$/)
  await page.getByTestId('submission-images').setInputFiles({
    name: 'homework.png',
    mimeType: 'image/png',
    buffer: Buffer.from('89504e470d0a1a0a74657374', 'hex'),
  })
  await expect(page.getByAltText('homework.png')).toBeVisible()
  await page.getByTestId('submit-assignment').click()

  await expect(page).toHaveURL(/\/student\/result\/501$/)
  await expect(page.getByTestId('grading-summary')).toBeVisible()
  await expect(page.getByTestId('grading-score')).toHaveText('9')
  await expect(page.getByText('Good progress.')).toBeVisible()
  expect(resultRequests).toBe(2)
})

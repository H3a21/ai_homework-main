<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  account: '',
  password: '',
  role: 'teacher' as 'teacher' | 'student',
  remember: false,
})

const loading = ref(false)
const showPassword = ref(false)
const errorMsg = ref('')
const isRegister = ref(false)

async function handleLogin() {
  errorMsg.value = ''

  if (!form.account.trim()) {
    errorMsg.value = '请输入账号'
    return
  }
  if (!form.password.trim()) {
    errorMsg.value = '请输入密码'
    return
  }

  loading.value = true
  try {
    let success: boolean
    if (isRegister.value) {
      success = await authStore.register(
        form.account.trim(),
        form.password,
        form.account.trim(),
        form.role,
      )
    } else {
      success = await authStore.login(form.account.trim(), form.password)
    }
    if (success) {
      router.push(form.role === 'teacher' ? '/teacher/dashboard' : '/student/dashboard')
    }
  } catch (err: any) {
    if (err.response?.data?.detail) {
      errorMsg.value = err.response.data.detail
    } else if (err.response) {
      errorMsg.value = `服务器错误 (${err.response.status})`
    } else if (err.request) {
      errorMsg.value = '无法连接到服务器，请检查后端是否已启动'
    } else {
      errorMsg.value = '操作失败，请重试'
    }
  } finally {
    loading.value = false
  }
}

function switchRole(role: 'teacher' | 'student') {
  form.role = role
  errorMsg.value = ''
}

function toggleMode() {
  isRegister.value = !isRegister.value
  errorMsg.value = ''
}
</script>

<template>
  <div class="login-page">
    <!-- 左侧品牌区 · 自然山水 -->
    <div class="brand-section">
      <!-- 自然风景层 -->
      <div class="nature-scene">
        <div class="nature-sky"></div>
        <div class="nature-mountains">
          <div class="mountain mountain--far"></div>
          <div class="mountain mountain--mid"></div>
          <div class="mountain mountain--near"></div>
        </div>
        <div class="nature-lake"></div>
        <div class="nature-mist mist--1"></div>
        <div class="nature-mist mist--2"></div>
        <div class="nature-mist mist--3"></div>
        <div class="nature-rays"></div>
        <div class="nature-dust">
          <span
            class="dust-particle"
            v-for="n in 10"
            :key="n"
            :style="`--i: ${n}`"
          ></span>
        </div>
      </div>

      <!-- 文字内容 -->
      <div class="brand-content">
        <!-- Logo -->
        <div class="logo-wrapper">
          <div class="logo-mark">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="logoGrad" x1="0" y1="0" x2="32" y2="32">
                  <stop offset="0%" stop-color="rgba(255,255,255,0.95)"/>
                  <stop offset="100%" stop-color="rgba(255,255,255,0.55)"/>
                </linearGradient>
              </defs>
              <path d="M7 22.5V12l9 3v10.5l-9-3z" fill="rgba(255,255,255,0.08)"/>
              <path d="M25 22.5V12l-9 3v10.5l9-3z" fill="rgba(255,255,255,0.05)"/>
              <path d="M9.5 16l5 4.5 8-8.5" stroke="url(#logoGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="25" cy="8.5" r="1.8" fill="#fbbf24" opacity="0.9"/>
              <path d="M25 5v-1M25 12v1M21 8.5h-1M29 8.5h1" stroke="#fbbf24" stroke-width="1" stroke-linecap="round"/>
            </svg>
          </div>
          <span class="logo-text">智学批改</span>
        </div>

        <!-- 标语 -->
        <div class="tagline-wrapper">
          <h1 class="tagline">
            <span class="line-reveal" style="--d:0">让每一份作业</span>
            <span class="line-reveal" style="--d:1">都被认真对待</span>
          </h1>
          <p class="description">
            覆盖多学科的智能批改系统<br class="hide-mobile" />
            为教育工作者提供自动判分、薄弱点分析与个性化评语
          </p>
        </div>

        <!-- 特性列表 -->
        <div class="features">
          <div
            class="feature-item"
            v-for="(item, i) in features"
            :key="i"
            :style="`--i: ${i}`"
          >
            <span class="feature-num">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="feature-divider"></span>
            <div class="feature-text">
              <span class="feature-title">{{ item.title }}</span>
              <span class="feature-desc">{{ item.desc }}</span>
            </div>
          </div>
        </div>

        <!-- 底部 -->
        <div class="brand-footer">
          <span class="footer-mark"></span>
          <span class="footer-text">智学批改 v1.0</span>
        </div>
      </div>
    </div>

    <!-- 右侧登录区 -->
    <div class="login-section">
      <div class="login-container">
        <!-- 头部 -->
        <div class="login-header">
          <h2 class="login-title">欢迎回来</h2>
          <p class="login-subtitle">请登录您的账号以使用智能批改服务</p>
        </div>

        <!-- 角色切换 -->
        <div class="role-switch">
          <button
            :class="['role-btn', { active: form.role === 'teacher' }]"
            @click="switchRole('teacher')"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 19.5z"/>
              <path d="M9 10h6"/>
              <path d="M9 14h6"/>
              <path d="M9 6h6"/>
            </svg>
            教师端
          </button>
          <button
            data-testid="role-student"
            :class="['role-btn', { active: form.role === 'student' }]"
            @click="switchRole('student')"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
              <path d="M6 12v5c3 3 9 3 12 0v-5"/>
            </svg>
            学生端
          </button>
        </div>

        <!-- 表单 -->
        <form class="login-form" @submit.prevent="handleLogin">
          <!-- 错误提示 -->
          <Transition name="shake">
            <div v-if="errorMsg" class="error-banner">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {{ errorMsg }}
            </div>
          </Transition>

          <!-- 账号 -->
          <div class="input-group">
            <label class="input-label">账号</label>
            <div class="input-wrapper">
              <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <input
                data-testid="login-account"
                v-model="form.account"
                type="text"
                placeholder="请输入邮箱或工号"
                class="input-field"
                autocomplete="username"
              />
            </div>
          </div>

          <!-- 密码 -->
          <div class="input-group">
            <label class="input-label">密码</label>
            <div class="input-wrapper">
              <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <input
                data-testid="login-password"
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码"
                class="input-field"
                autocomplete="current-password"
              />
              <button
                type="button"
                class="toggle-pwd"
                @click="showPassword = !showPassword"
                :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              >
                <svg v-if="!showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                  <circle cx="12" cy="12" r="3"/>
                </svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                  <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 选项 -->
          <div class="form-options">
            <label class="checkbox-wrapper">
              <input type="checkbox" v-model="form.remember" />
              <span class="checkmark"></span>
              <span>记住我</span>
            </label>
            <a href="#" class="forgot-link" @click.prevent>忘记密码？</a>
          </div>

          <!-- 登录按钮 -->
          <button data-testid="login-submit" type="submit" class="login-btn" :class="{ loading }" :disabled="loading">
            <span v-if="!loading">{{ isRegister ? '注 册' : '登 录' }}</span>
            <span v-else class="loading-spinner">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <circle cx="12" cy="12" r="10" stroke-dasharray="31.4 31.4" stroke-dashoffset="0">
                  <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
                </circle>
              </svg>
              处理中...
            </span>
          </button>
        </form>

        <!-- 注册引导 -->
        <div class="signup-hint">
          <template v-if="!isRegister">还没有账号？</template>
          <template v-else>已有账号？</template>
          <a href="#" @click.prevent="toggleMode" v-if="!isRegister">立即注册</a>
  <a href="#" @click.prevent="toggleMode" v-else>返回登录</a>
        </div>

        <!-- 底部 -->
        <div class="login-footer">
          <div class="divider">
            <span>其他登录方式</span>
          </div>
          <div class="social-login">
            <button class="social-btn" title="微信登录">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18z"/>
                <path d="M24 14.35c0-3.66-3.494-6.628-7.804-6.628-4.31 0-7.804 2.967-7.804 6.628 0 3.662 3.494 6.628 7.804 6.628a8.9 8.9 0 0 0 2.318-.327.733.733 0 0 1 .595.082l1.577.922a.282.282 0 0 0 .142.045c.147 0 .26-.123.26-.273 0-.062-.023-.126-.04-.186l-.322-1.233a.493.493 0 0 1 .177-.554C22.98 17.462 24 15.996 24 14.35zm-10.496-.984a.977.977 0 0 1-.97-.983c0-.543.435-.983.97-.983.536 0 .97.44.97.983a.977.977 0 0 1-.97.983zm4.86 0a.977.977 0 0 1-.97-.983c0-.543.435-.983.97-.983.536 0 .97.44.97.983a.977.977 0 0 1-.97.983z"/>
              </svg>
            </button>
            <button class="social-btn" title="企业微信登录">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.03 13.326c0 .598-.424 1.082-.947 1.082-.523 0-.946-.484-.946-1.082 0-.598.423-1.082.946-1.082.523 0 .946.484.946 1.082zm-2.437-2.269c-.523 0-.946.484-.946 1.082 0 .598.423 1.082.946 1.082.523 0 .947-.484.947-1.082 0-.598-.424-1.082-.947-1.082z"/>
                <path d="M12 2C6.477 2 2 6.477 2 12s4.477 10 10 10 10-4.477 10-10S17.523 2 12 2zm0 18.5a8.5 8.5 0 1 1 0-17 8.5 8.5 0 0 1 0 17z"/>
                <path d="M16.5 12.5c0 2.485-2.015 4.5-4.5 4.5s-4.5-2.015-4.5-4.5S9.515 8 12 8s4.5 2.015 4.5 4.5z"/>
              </svg>
            </button>
            <button class="social-btn" title="钉钉登录">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.272 1.904c-5.134.347-9.184 4.571-9.368 9.752-.076 2.37.633 4.643 1.956 6.512.222.313.46.616.712.907a10.365 10.365 0 0 0 1.762 1.574c.102.07.206.14.312.206v-3.008c0-.386.07-.615.255-.906.127-.2.29-.373.48-.51l4.155-2.972c.047-.033.089-.075.122-.124.048-.073.07-.16.06-.246a.426.426 0 0 0-.195-.33L8.61 11.14a.518.518 0 0 1-.255-.424c0-.047.013-.093.038-.134.07-.112.196-.166.324-.14l5.055.99c.05.01.101.01.151 0l4.682-1.036a.374.374 0 0 1 .162-.003c.119.029.184.146.161.265a.877.877 0 0 1-.08.218c-.454.93-1.069 1.755-1.83 2.42l-3.29 2.87a.406.406 0 0 0-.16.321c0 .14.08.268.206.327l4.148 1.941c.105.05.193.127.255.22.093.141.139.306.133.474v2.285a9.562 9.562 0 0 0 1.424-1.46c1.978-2.49 2.586-5.668 1.797-8.618-.834-3.074-3.318-5.523-6.404-6.229a9.92 9.92 0 0 0-2.323-.295z"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
const features = [
  {
    title: '多学科覆盖',
    desc: '支持数学、语文、英语等学科作业批改',
  },
  {
    title: '过程判分',
    desc: '识别解题步骤，评估推理过程而非仅核对最终答案',
  },
  {
    title: '薄弱点定位',
    desc: '汇总错误模式，精准定位知识点薄弱环节',
  },
  {
    title: '个性化评语',
    desc: '针对每份作业自动生成有针对性的反馈建议',
  },
]
</script>

<style scoped>
/* ────────── 页面布局 ────────── */
.login-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg);
}

/* ────────── 左侧品牌区 ────────── */
.brand-section {
  flex: 1.1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 56px;
  background: #1a2a3a;
}

/* ══════ 自然风景背景 ══════ */
.nature-scene {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

/* ── 天空 ── */
.nature-sky {
  position: absolute;
  inset: 0;
  background: linear-gradient(172deg,
    #162838 0%,
    #1e3a50 18%,
    #2a5068 35%,
    #3e6878 50%,
    #7a9a9a 65%,
    #b0c0b8 78%,
    #d0d4c8 90%,
    #c4ccc0 100%
  );
}

/* ── 山脉 ── */
.nature-mountains {
  position: absolute;
  inset: 0;
}

.mountain {
  position: absolute;
  bottom: 28%;
  width: 100%;
}

.mountain--far {
  left: -5%;
  bottom: 35%;
  width: 55%;
  height: 30%;
  background: rgba(120,150,160,0.3);
  clip-path: polygon(0% 100%, 8% 38%, 22% 52%, 35% 18%, 48% 42%, 62% 28%, 78% 48%, 100% 100%);
  animation: mountainBreath 14s ease-in-out infinite;
}

.mountain--mid {
  left: 15%;
  bottom: 30%;
  width: 68%;
  height: 35%;
  background: rgba(80,105,118,0.42);
  clip-path: polygon(0% 100%, 12% 45%, 25% 58%, 38% 22%, 52% 42%, 65% 12%, 78% 38%, 100% 100%);
  animation: mountainBreath 16s ease-in-out infinite reverse;
}

.mountain--near {
  left: -10%;
  bottom: 26%;
  width: 82%;
  height: 38%;
  background: rgba(45,60,70,0.58);
  clip-path: polygon(0% 100%, 10% 52%, 25% 65%, 38% 35%, 52% 55%, 66% 28%, 80% 50%, 100% 100%);
  animation: mountainBreath 18s ease-in-out infinite;
}

@keyframes mountainBreath {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-4px); }
}

/* ── 湖面 ── */
.nature-lake {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28%;
  background: linear-gradient(180deg,
    rgba(22,38,48,0.15) 0%,
    rgba(18,32,40,0.45) 35%,
    rgba(14,24,30,0.7) 100%
  );
}

/* ── 雾层 ── */
.nature-mist {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
}

.mist--1 {
  width: 65%;
  height: 40%;
  background: radial-gradient(ellipse, rgba(210,218,222,0.5) 0%, transparent 60%);
  top: 30%;
  left: 28%;
  animation: mistDrift 11s ease-in-out infinite;
}

.mist--2 {
  width: 50%;
  height: 32%;
  background: radial-gradient(ellipse, rgba(225,220,210,0.4) 0%, transparent 60%);
  top: 42%;
  left: 8%;
  animation: mistDrift 14s ease-in-out infinite reverse;
}

.mist--3 {
  width: 42%;
  height: 28%;
  background: radial-gradient(ellipse, rgba(195,205,210,0.38) 0%, transparent 60%);
  top: 12%;
  left: 48%;
  animation: mistDrift 9s ease-in-out infinite;
  animation-delay: -4s;
}

@keyframes mistDrift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33%      { transform: translate(18px, -10px) scale(1.05); }
  66%      { transform: translate(-12px, 6px) scale(0.97); }
}

/* ── 光束 ── */
.nature-rays {
  position: absolute;
  inset: 0;
  background: linear-gradient(138deg,
    rgba(255,248,235,0.1) 0%,
    rgba(255,242,225,0.04) 28%,
    transparent 60%
  );
  animation: raysPulse 9s ease-in-out infinite;
}

@keyframes raysPulse {
  0%, 100% { opacity: 0.5; }
  50%      { opacity: 1; }
}

/* ── 浮尘粒子 ── */
.nature-dust {
  position: absolute;
  inset: 0;
}

.dust-particle {
  position: absolute;
  width: 2px;
  height: 2px;
  border-radius: 50%;
  background: rgba(255,252,240,0.5);
  left: calc(8% + var(--i) * 9%);
  bottom: calc(12% + var(--i) * 6%);
  animation: dustFloat calc(5s + var(--i) * 1.2s) ease-in-out infinite;
  animation-delay: calc(var(--i) * -1.8s);
}

.dust-particle:nth-child(even) {
  width: 3px;
  height: 3px;
  background: rgba(255,248,230,0.35);
  animation-duration: calc(7s + var(--i) * 1s);
}

.dust-particle:nth-child(3n) {
  width: 1.5px;
  height: 1.5px;
  background: rgba(255,250,240,0.6);
}

@keyframes dustFloat {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0;
  }
  15%  { opacity: 0.7; }
  45%  { opacity: 0.25; }
  75%  { opacity: 0.55; }
  100% {
    transform: translateY(-160px) translateX(18px);
    opacity: 0;
  }
}

/* ══════ 文字内容层 ══════ */
.brand-content {
  position: relative;
  z-index: 2;
  max-width: 480px;
  width: 100%;
  color: #fff;
}

/* Logo */
.logo-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 44px;
}

.logo-mark {
  width: 34px;
  height: 34px;
  color: rgba(255,255,255,0.82);
  filter: drop-shadow(0 2px 6px rgba(0,0,0,0.35));
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: rgba(255,255,255,0.88);
  text-shadow: 0 2px 10px rgba(0,0,0,0.35);
}

/* 标语 */
.tagline-wrapper {
  margin-bottom: 32px;
}

.tagline {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.02em;
  margin: 0 0 18px;
  color: #fff;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-shadow: 0 2px 16px rgba(0,0,0,0.4);
}

/* 逐行动画 */
.line-reveal {
  display: block;
  opacity: 0;
  animation: lineReveal 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  animation-delay: calc(var(--d) * 0.18s + 0.15s);
}

@keyframes lineReveal {
  from {
    opacity: 0;
    transform: translateY(24px);
    filter: blur(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

.description {
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255,255,255,0.52);
  margin: 0;
  opacity: 0;
  animation: lineReveal 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  animation-delay: 0.55s;
  text-shadow: 0 1px 6px rgba(0,0,0,0.35);
}

/* 特性列表 */
.features {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 36px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  opacity: 0;
  animation: itemSlideIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  animation-delay: calc(var(--i) * 0.1s + 0.65s);
  transition: border-color 0.5s ease;
}

.feature-item:last-child { border-bottom: none; }

.feature-item:hover { border-color: rgba(255,255,255,0.2); }
.feature-item:hover .feature-num { color: rgba(255,255,255,0.7); }

@keyframes itemSlideIn {
  from { opacity: 0; transform: translateX(-12px); }
  to   { opacity: 1; transform: translateX(0); }
}

.feature-num {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  color: rgba(255,255,255,0.22);
  letter-spacing: 0.08em;
  flex-shrink: 0;
  width: 24px;
  transition: color 0.5s ease;
}

.feature-divider {
  width: 14px;
  height: 1px;
  background: rgba(255,255,255,0.09);
  flex-shrink: 0;
}

.feature-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.feature-title {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.8);
  letter-spacing: 0.01em;
  text-shadow: 0 1px 6px rgba(0,0,0,0.3);
}

.feature-desc {
  font-size: 12px;
  color: rgba(255,255,255,0.38);
  line-height: 1.5;
}

/* 底部 */
.brand-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  opacity: 0;
  animation: lineReveal 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  animation-delay: 1.15s;
}

.footer-mark {
  width: 5px;
  height: 5px;
  background: rgba(255,255,255,0.22);
  transform: rotate(45deg);
}

.footer-text {
  font-size: 11px;
  color: rgba(255,255,255,0.25);
  letter-spacing: 0.04em;
}

/* ────────── 右侧登录区 ────────── */
.login-section {
  flex: 0.9;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: var(--bg-alt);
}

.login-container {
  max-width: 400px;
  width: 100%;
  animation: slideInRight 0.6s ease-out;
}

.login-header {
  margin-bottom: 32px;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-heading);
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.login-subtitle {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0;
}

/* 角色切换 */
.role-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
  padding: 4px;
  background: var(--border-light);
  border-radius: var(--radius-md);
}

.role-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
  transition: all 0.3s ease;
}

.role-btn:hover {
  color: var(--text);
}

.role-btn.active {
  color: var(--primary);
  background: var(--bg);
  box-shadow: var(--shadow-sm);
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
}

/* 错误提示 */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.shake-enter-active {
  animation: shake 0.4s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(6px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}

/* 输入框组 */
.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-heading);
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: var(--text-secondary);
  pointer-events: none;
  transition: color 0.3s;
}

.input-field {
  width: 100%;
  padding: 12px 14px 12px 42px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-heading);
  background: var(--bg);
  transition: all 0.3s ease;
  outline: none;
}

.input-field::placeholder {
  color: var(--text-secondary);
}

.input-field:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-bg);
}

.input-field:focus ~ .input-icon,
.input-wrapper:focus-within .input-icon {
  color: var(--primary);
}

.toggle-pwd {
  position: absolute;
  right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.toggle-pwd:hover {
  color: var(--text);
  background: var(--border-light);
}

/* 选项 */
.form-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.checkbox-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  user-select: none;
}

.checkbox-wrapper input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.checkmark {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.checkbox-wrapper input:checked + .checkmark {
  background: var(--primary);
  border-color: var(--primary);
}

.checkbox-wrapper input:checked + .checkmark::after {
  content: '';
  width: 5px;
  height: 9px;
  border: solid #fff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
  margin-top: -1px;
}

.forgot-link {
  font-size: 13px;
  font-weight: 500;
  color: var(--primary);
  text-decoration: none;
  transition: color 0.2s;
}

.forgot-link:hover {
  color: var(--primary-dark);
}

/* 登录按钮 */
.login-btn {
  position: relative;
  width: 100%;
  padding: 13px 24px;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.login-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--primary-light), var(--primary));
  opacity: 0;
  transition: opacity 0.3s ease;
}

.login-btn:hover:not(:disabled)::before {
  opacity: 1;
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0);
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.login-btn span {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.loading-spinner {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 注册引导 */
.signup-hint {
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 28px;
}

.signup-hint a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
  transition: color 0.2s;
}

.signup-hint a:hover {
  color: var(--primary-dark);
}

/* 社交登录 */
.login-footer {
  text-align: center;
}

.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.divider span {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.social-login {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.social-btn {
  width: 44px;
  height: 44px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.3s ease;
  padding: 10px;
}

.social-btn svg {
  width: 22px;
  height: 22px;
}

.social-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-bg);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* ────────── 响应式 ────────── */
@media (max-width: 900px) {
  .login-page {
    flex-direction: column;
  }

  .brand-section {
    flex: none;
    padding: 28px 24px;
    min-height: 320px;
  }

  .brand-content {
    max-width: 100%;
  }

  .logo-wrapper {
    margin-bottom: 24px;
  }

  .tagline {
    font-size: 28px;
    gap: 2px;
  }

  .tagline-wrapper {
    margin-bottom: 20px;
  }

  .features {
    margin-bottom: 20px;
  }

  .feature-item {
    padding: 11px 0;
  }

  .hide-mobile {
    display: none;
  }

  .login-section {
    flex: none;
    padding: 32px 24px;
  }

  .login-container {
    max-width: 100%;
  }
}

@media (max-width: 480px) {
  .brand-section {
    padding: 20px 16px;
    min-height: 260px;
  }

  .logo-wrapper {
    margin-bottom: 18px;
  }

  .tagline {
    font-size: 24px;
  }

  .features {
    gap: 0;
  }

  .feature-item {
    padding: 10px 0;
  }

  .description {
    font-size: 12px;
  }

  .login-section {
    padding: 24px 16px;
  }
}
</style>

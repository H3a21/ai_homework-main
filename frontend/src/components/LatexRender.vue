<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'

const props = defineProps<{ text: string }>()

const rendered = computed(() => {
  let html = props.text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Block math $$...$$
  html = html.replace(/\$\$(.+?)\$\$/gs, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="tex-error">$$${formula}$$</span>`
    }
  })

  // Inline math $...$
  html = html.replace(/\$(.+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="tex-error">$${formula}$</span>`
    }
  })

  // Images ![alt](url)
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="question-img" />')

  return html
})
</script>

<template>
  <span v-if="!text" class="empty">--</span>
  <span v-else v-html="rendered" class="latex-content" />
</template>

<style>
.latex-content { line-height: 1.8; }
.latex-content .question-img { max-width: 100%; border-radius: 8px; margin: 8px 0; }
.tex-error { color: #ef4444; font-size: 13px; }
.katex { font-size: 1.05em; }
</style>

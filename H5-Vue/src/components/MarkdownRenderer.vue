<template>
  <div v-if="plain" class="markdown-plain">{{ content }}</div>
  <div
    v-else
    ref="mdRef"
    class="markdown-body"
    v-html="renderedHtml"
  />
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/common'
import 'highlight.js/styles/atom-one-dark.css'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  plain: {
    type: Boolean,
    default: false
  },
  streaming: {
    type: Boolean,
    default: false
  }
})

const renderedHtml = ref('')
const mdRef = ref(null)
let timer = null

// 配置 marked
marked.setOptions({
  gfm: true,
  breaks: true,
  headerIds: false,
  mangle: false,
  highlight(code, lang) {
    const validLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language: validLang, ignoreIllegals: true }).value
  }
})

// 配置 DOMPurify 白名单
const purifyConfig = {
  ALLOWED_TAGS: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'div', 'span', 'br', 'hr',
    'pre', 'code', 'blockquote',
    'ul', 'ol', 'li',
    'strong', 'b', 'em', 'i', 'del', 's', 'sup', 'sub',
    'a', 'img', 'button',
    'table', 'thead', 'tbody', 'tr', 'th', 'td'
  ],
  ALLOWED_ATTR: [
    'class', 'href', 'src', 'alt', 'title',
    'target', 'rel', 'type'
  ],
  FORBID_ATTR: ['style']
}

DOMPurify.addHook('afterSanitizeAttributes', node => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer nofollow')
  }
})

// 给代码块加上 header + copy 按钮
function wrapCodeBlocks(html) {
  return html
    .replace(
      /<pre><code(?: class="language-([^"]*)")?>/g,
      (_, lang = 'plaintext') => {
        const label = String(lang).toUpperCase()
        return `<div class="code-block-wrapper">
  <div class="code-header">
    <span class="lang-label">${label}</span>
    <button class="copy-btn" type="button">复制</button>
  </div>
  <pre><code class="language-${lang}">`.trim()
      }
    )
    .replace(/<\/code><\/pre>/g, '</code></pre></div>')
}

function computeHtml() {
  const raw = marked.parse(props.content || '', { async: false })
  const wrapped = wrapCodeBlocks(raw)
  return DOMPurify.sanitize(wrapped, purifyConfig)
}

function updateHtml() {
  renderedHtml.value = computeHtml()
}

watch(() => props.content, () => {
  clearTimeout(timer)
  if (props.streaming) {
    timer = setTimeout(updateHtml, 80)
  } else {
    updateHtml()
  }
}, { immediate: true })

watch(() => props.streaming, (isStreaming) => {
  if (!isStreaming) {
    clearTimeout(timer)
    updateHtml()
  }
})

// 复制功能
function onCopyClick(e) {
  const btn = e.target.closest('.copy-btn')
  if (!btn) return
  const wrapper = btn.closest('.code-block-wrapper')
  const code = wrapper?.querySelector('code')
  if (!code) return

  const text = code.textContent || ''
  const original = btn.innerHTML

  const done = () => {
    btn.innerHTML = '已复制'
    setTimeout(() => {
      btn.innerHTML = original
    }, 2000)
  }

  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(fallback)
  } else {
    fallback()
  }

  function fallback() {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    done()
  }
}

onMounted(() => {
  mdRef.value?.addEventListener('click', onCopyClick)
})

onUnmounted(() => {
  mdRef.value?.removeEventListener('click', onCopyClick)
})
</script>

<style>
.markdown-plain {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
}

.markdown-body {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  white-space: normal;
  word-break: break-word;
}

.markdown-body * {
  box-sizing: border-box;
}

.markdown-body p {
  margin: 0 0 10px 0;
}

.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin: 16px 0 10px 0;
  font-weight: 600;
  line-height: 1.4;
  color: #1f2329;
}

.markdown-body h1 { font-size: 20px; }
.markdown-body h2 { font-size: 18px; }
.markdown-body h3 { font-size: 16px; }
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 { font-size: 14px; }

.markdown-body ul,
.markdown-body ol {
  margin: 10px 0;
  padding-left: 22px;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body blockquote {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 4px solid #409eff;
  background: #f5f7fa;
  color: #606266;
}

.markdown-body code:not(pre code) {
  background: #f2f3f5;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  color: #d73a49;
  font-size: 0.9em;
}

.code-block-wrapper {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #3e4451;
  background: #282c34;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #21252b;
  border-bottom: 1px solid #3e4451;
}

.lang-label {
  font-size: 12px;
  color: #abb2bf;
  text-transform: uppercase;
  font-family: 'SFMono-Regular', Consolas, monospace;
  letter-spacing: 0.5px;
}

.copy-btn {
  background: transparent;
  border: 1px solid #5c6370;
  color: #abb2bf;
  cursor: pointer;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  transition: all 0.2s;
}

.copy-btn:hover {
  background: #3e4451;
  color: #ffffff;
  border-color: #3e4451;
}

.markdown-body pre {
  margin: 0;
  padding: 12px;
  overflow-x: auto;
  background: #282c34;
}

.markdown-body pre code {
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 13px;
  line-height: 1.5;
  background: transparent !important;
  color: #abb2bf;
  padding: 0;
}

.markdown-body .hljs {
  background: transparent !important;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: #f5f7fa;
  font-weight: 600;
}

.markdown-body tr:nth-child(even) {
  background: #fafafa;
}

.markdown-body a {
  color: #409eff;
  text-decoration: none;
}

.markdown-body a:hover {
  text-decoration: underline;
}

.markdown-body img {
  max-width: 100%;
  border-radius: 4px;
}

.markdown-body hr {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 16px 0;
}
</style>

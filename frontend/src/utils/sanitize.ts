import { marked } from "marked"
import DOMPurify from "dompurify"

export function renderMarkdown(text: string): string {
  if (!text) return ""
  try {
    const html = marked.parse(text, { breaks: true }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(text)
  }
}

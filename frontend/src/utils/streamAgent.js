export async function streamAgent(url, body, onToken, onDone) {
  let res
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Cannot reach the API. Check that Docker is running.')
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Server error: ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let fullText = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value, { stream: true })
    fullText += chunk

    // Detect error token from backend
    if (fullText.trimStart().startsWith('[ERROR:')) {
      throw new Error(fullText.replace('[ERROR:', '').replace(']', '').trim())
    }

    if (fullText.includes('__META__')) {
      const [analysisPart, rest] = fullText.split('__META__')
      const [metaStr, sourcesStr] = rest.split('__SOURCES__')
      try {
        const meta = JSON.parse(metaStr.trim())
        const sources = JSON.parse(sourcesStr.trim())
        onDone({ analysis: analysisPart.trim(), sources, ...meta })
      } catch {
        onDone({ analysis: analysisPart.trim(), sources: [] })
      }
      return
    }
    onToken(fullText)
  }
}

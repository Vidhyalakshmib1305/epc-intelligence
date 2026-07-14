export async function streamAgent(url, body, onToken, onDone) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error('Request failed')
  
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let fullText = ''
  
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      fullText += chunk
  
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
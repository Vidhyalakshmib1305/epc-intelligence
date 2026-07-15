import { useState } from 'react'

export default function Upload() {
  const [file, setFile] = useState(null)
  const [docType, setDocType] = useState('specification')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleUpload = async () => {
    if (!file) return

    // Client-side validation
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported.')
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setError('File too large. Maximum size is 50MB.')
      return
    }
    if (file.size === 0) {
      setError('File is empty.')
      return
    }

    setLoading(true); setError(null); setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', docType)
    try {
      const res = await fetch('/api/documents/upload', { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload failed')
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Upload Documents</h2>
      <p className="text-gray-500 mb-6">Upload EPC project documents (PDFs) to the knowledge base.</p>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">PDF File</label>
          <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
          <select value={docType} onChange={e => setDocType(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="specification">Specification</option>
            <option value="schedule">Schedule</option>
            <option value="rfi_log">RFI Log</option>
            <option value="drawing">Drawing</option>
            <option value="other">Other</option>
          </select>
        </div>
        <button onClick={handleUpload} disabled={!file || loading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {loading ? 'Uploading...' : 'Upload Document'}
        </button>
      </div>
      {error && <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>}
      {result && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="font-medium text-green-800 mb-2">✅ Upload successful</p>
          <div className="grid grid-cols-2 gap-2 text-sm text-green-700">
            <span>Document ID:</span><span className="font-mono">{result.doc_id}</span>
            <span>Filename:</span><span>{result.filename}</span>
            <span>Pages:</span><span>{result.page_count}</span>
            <span>Chunks stored:</span><span>{result.chunks_stored}</span>
          </div>
        </div>
      )}
    </div>
  )
}
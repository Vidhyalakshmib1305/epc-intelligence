import { useState, useEffect } from 'react'

const typeColors = {
  specification: 'bg-blue-100 text-blue-700',
  schedule:      'bg-purple-100 text-purple-700',
  rfi_log:       'bg-orange-100 text-orange-700',
  drawing:       'bg-teal-100 text-teal-700',
  other:         'bg-gray-100 text-gray-700',
}

export default function Documents() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/documents')
      .then(r => r.json())
      .then(data => { setDocs(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  return (
    <div className="max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Documents</h2>
      <p className="text-gray-500 mb-6">All documents currently in the knowledge base.</p>
      {loading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-600">Error: {error}</p>}
      {!loading && !error && docs.length === 0 && <p className="text-gray-500">No documents uploaded yet.</p>}
      <div className="space-y-3">
        {docs.map(doc => (
          <div key={doc.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-800">{doc.filename}</p>
              <p className="text-xs text-gray-400 font-mono mt-0.5">{doc.id}</p>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${typeColors[doc.doc_type] || typeColors.other}`}>
                {doc.doc_type}
              </span>
              <span className="text-gray-500">{doc.page_count} pages</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
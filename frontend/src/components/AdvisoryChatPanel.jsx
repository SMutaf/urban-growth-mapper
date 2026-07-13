import { useEffect, useRef, useState } from 'react'
import { continueAdvisory, startAdvisory } from '../api/client.js'
import { CloseIcon } from './icons.jsx'

// Thresholds are arbitrary-but-reasonable (not calibrated against a real
// score distribution) - the label is a relative-potential indicator, never
// presented as a precise/absolute figure, see the badge's caption below.
function scoreBand(score) {
  if (score >= 0.65) return { label: 'Yüksek', color: '#16a34a', background: '#dcfce7' }
  if (score >= 0.35) return { label: 'Orta', color: '#a16207', background: '#fef9c3' }
  return { label: 'Düşük', color: '#dc2626', background: '#fee2e2' }
}

// Stays mounted at all times (App.jsx renders it unconditionally) and is
// only ever hidden/shown via CSS (isOpen), never unmounted - closing the
// panel must not lose the conversation, since the user should be able to
// reopen it "any time" and pick up where they left off. Dropping a NEW pin
// (analysisPoint changes) is the one thing that always starts a fresh
// conversation, replacing whatever was open - see App.jsx's handleMapClick.
// The backend is stateless (see application/services/advisory_service.py):
// the first call builds and returns `context`, which this component holds
// onto and resends verbatim on every follow-up call instead of the server
// keeping any session.
export default function AdvisoryChatPanel({ city, analysisPoint, isOpen, onClose }) {
  const [messages, setMessages] = useState([])
  const [context, setContext] = useState(null)
  const [usedProfile, setUsedProfile] = useState(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    setMessages([])
    setContext(null)
    setUsedProfile(null)
    setInput('')
    setError(null)
  }, [analysisPoint])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || loading || !analysisPoint) return
    setLoading(true)
    setError(null)
    const userMessage = { role: 'user', content: trimmed }
    setInput('')

    try {
      if (!context) {
        const result = await startAdvisory(city, analysisPoint.lat, analysisPoint.lon, trimmed)
        setContext(result.context)
        setUsedProfile(result.used_profile)
        setMessages([userMessage, { role: 'assistant', content: result.advice }])
      } else {
        const nextMessages = [...messages, userMessage]
        setMessages(nextMessages)
        const result = await continueAdvisory(context, nextMessages)
        setMessages([...nextMessages, { role: 'assistant', content: result.advice }])
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  const locationLabel = analysisPoint
    ? context?.mahalle_adi || `${analysisPoint.lat.toFixed(5)}, ${analysisPoint.lon.toFixed(5)}`
    : 'Henüz nokta seçilmedi'
  const band = context ? scoreBand(context.buyume_skoru) : null

  return (
    <div className="advisory-panel" style={{ display: isOpen ? 'flex' : 'none' }}>
      <div className="advisory-panel-header">
        <div>
          <div className="advisory-panel-title">Analiz Danışmanı</div>
          <div className="advisory-panel-subtitle">
            {locationLabel}
            {usedProfile ? ` · ${usedProfile}` : ''}
          </div>
        </div>
        <button className="advisory-panel-close" onClick={onClose} aria-label="Kapat">
          <CloseIcon />
        </button>
      </div>

      {band && (
        <div className="advisory-score-badge" style={{ color: band.color, background: band.background }}>
          <span className="advisory-score-badge-label">Büyüme potansiyeli: {band.label}</span>
          <span className="advisory-score-badge-value">({context.buyume_skoru.toFixed(2)})</span>
          <span className="advisory-score-badge-caption">göreli gösterge, kesin değer değil</span>
        </div>
      )}

      <div className="advisory-panel-messages">
        {!analysisPoint && (
          <div className="advisory-panel-hint">
            Sohbete başlamak için sağ alttaki "Analiz Et" butonuyla haritada bir nokta seçin.
          </div>
        )}
        {analysisPoint && messages.length === 0 && !loading && (
          <div className="advisory-panel-hint">
            Bu nokta hakkında ne öğrenmek istersiniz? Örn. "buraya konut yapmak istiyorum,
            gelecek vaadi hakkında ne düşünüyorsun?" veya "en yakın hastane nerede?"
          </div>
        )}
        {messages.map((message, index) => (
          <div key={index} className={`advisory-message advisory-message-${message.role}`}>
            {message.content}
          </div>
        ))}
        {loading && <div className="advisory-message advisory-message-assistant advisory-message-loading">…</div>}
        {error && <div className="advisory-panel-error">{error}</div>}
        <div ref={messagesEndRef} />
      </div>

      <div className="advisory-panel-input-row">
        <textarea
          className="advisory-panel-input"
          placeholder={analysisPoint ? 'Mesajınızı yazın...' : 'Önce haritada bir nokta seçin...'}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!analysisPoint}
          rows={2}
        />
        <button
          className="advisory-panel-send"
          onClick={handleSend}
          disabled={loading || !input.trim() || !analysisPoint}
        >
          Gönder
        </button>
      </div>
    </div>
  )
}

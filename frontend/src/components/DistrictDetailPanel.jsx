import { useEffect, useState } from 'react'
import { fetchMahalleScores } from '../api/client.js'
import { CloseIcon } from './icons.jsx'

const scoreFormatter = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function DistrictDetailPanel({ city, district, landUseProfile, onClose }) {
  const [ranking, setRanking] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!district) return
    setLoading(true)
    setError(null)
    fetchMahalleScores(city, district.name, landUseProfile)
      .then((data) => setRanking(data.mahalleler))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [city, district, landUseProfile])

  if (!district) return null

  return (
    <div className="district-detail-panel">
      <div className="district-detail-header">
        <span>{district.name} - Mahalle Sıralaması</span>
        <button className="district-detail-close" onClick={onClose} aria-label="Kapat">
          <CloseIcon />
        </button>
      </div>

      <div className="district-detail-note">
        Nüfus verisi yalnızca ilçe düzeyinde ölçülmüştür (TÜİK). Aşağıdaki sıralama, mahallenin
        gerçek nüfusuna göre değil, model büyüme potansiyeline (tahmin) göredir - ikisini
        karıştırmayın.
      </div>

      {loading && <div className="district-detail-status">Yükleniyor... (birkaç saniye sürebilir)</div>}
      {error && <div className="district-detail-status district-detail-error">{error}</div>}

      {!loading && !error && (
        <ul className="district-detail-list">
          {ranking.map((mahalle) => (
            <li key={mahalle.mahalle_adi} className="district-detail-row">
              <span className="district-detail-name">{mahalle.mahalle_adi}</span>
              <span className="district-detail-score">
                {mahalle.ortalama_skor === null ? (
                  <span className="district-detail-no-data">veri yok</span>
                ) : (
                  <>
                    {scoreFormatter.format(mahalle.ortalama_skor)}
                    {mahalle.dusuk_ornek && (
                      <span className="district-detail-low-sample" title={`${mahalle.hucre_sayisi} hücre - düşük örneklem`}>
                        düşük örneklem
                      </span>
                    )}
                  </>
                )}
              </span>
            </li>
          ))}
          {ranking.length === 0 && <li className="district-detail-status">Mahalle verisi bulunamadı.</li>}
        </ul>
      )}
    </div>
  )
}

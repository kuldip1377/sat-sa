// Stylized low-poly India silhouette with entity risk nodes (demo visual).
const POS = {
  'PWR-01': [33, 22], 'PWR-02': [29, 30], 'BNK-01': [22, 52], 'BNK-02': [26, 57],
  'TEL-01': [35, 47], 'TEL-02': [31, 64], 'TRN-01': [40, 30], 'TRN-02': [43, 68],
  'OIL-01': [60, 27], 'OIL-02': [18, 42], 'GOV-01': [35, 26], 'GOV-02': [32, 40],
}
const col = (s) => (s >= 60 ? '#f87171' : s >= 30 ? '#fbbf24' : '#34d399')

export default function IndiaMap({ entities, onPick }) {
  return (
    <svg viewBox="0 0 80 100" className="w-full h-full">
      <path d="M34,4 L40,3 L45,8 L43,13 L48,15 L55,13 L62,17 L68,24 L63,27 L70,30 L73,36
               L66,37 L58,34 L54,40 L56,47 L50,58 L45,70 L40,84 L37,95 L33,84 L29,70
               L24,58 L18,47 L15,38 L21,31 L19,22 L26,12 Z"
        fill="#1e293b" stroke="#334155" strokeWidth="0.6" />
      {entities.map((e) => {
        const [x, y] = POS[e.id] || [40, 50]
        return (
          <g key={e.id} onClick={() => onPick(e.id)} className="cursor-pointer">
            <circle cx={x} cy={y} r={1.6 + Math.min(2.4, e.alerts30 / 600)}
              fill={col(e.score)} fillOpacity="0.28" />
            <circle cx={x} cy={y} r="1.1" fill={col(e.score)} stroke="#0f172a" strokeWidth="0.3">
              <title>{`${e.name} (${e.id}) — risk ${e.score}`}</title>
            </circle>
          </g>
        )
      })}
    </svg>
  )
}

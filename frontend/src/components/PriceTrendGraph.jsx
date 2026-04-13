import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { getPriceHistory } from '../lib/api';

function formatDate(isoString) {
  const d = new Date(isoString);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div style={tooltipStyles.box}>
        <p style={tooltipStyles.label}>{label}</p>
        <p style={tooltipStyles.value}>${Number(payload[0].value).toFixed(2)}</p>
      </div>
    );
  }
  return null;
}

const tooltipStyles = {
  box: {
    background: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '0.5rem 0.75rem',
  },
  label: { color: '#94a3b8', fontSize: '0.75rem', margin: 0, marginBottom: '0.2rem' },
  value: { color: '#38bdf8', fontWeight: '700', fontSize: '0.95rem', margin: 0 },
};

export default function PriceTrendGraph({ route_group }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!route_group) return;
    setLoading(true);
    setError('');
    getPriceHistory(route_group)
      .then((res) => {
        const points = (res.data || []).map((row) => ({
          date: formatDate(row.recorded_at),
          price: Number(row.lowest_price),
        }));
        setData(points);
      })
      .catch((err) => setError(err.message || 'Failed to load price history'))
      .finally(() => setLoading(false));
  }, [route_group]);

  if (loading) {
    return <p style={styles.status}>Loading price trend…</p>;
  }

  if (error) {
    return <p style={{ ...styles.status, color: '#f87171' }}>{error}</p>;
  }

  if (data.length === 0) {
    return <p style={styles.status}>No price history yet for this route.</p>;
  }

  const prices = data.map((d) => d.price);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = Math.max((maxPrice - minPrice) * 0.15, 10);

  return (
    <div style={styles.wrapper}>
      <p style={styles.heading}>Price Trend · {route_group}</p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${route_group}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#818cf8" />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[minPrice - padding, maxPrice + padding]}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${Math.round(v)}`}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#475569', strokeWidth: 1 }} />
          <Line
            type="monotone"
            dataKey="price"
            stroke={`url(#grad-${route_group})`}
            strokeWidth={2.5}
            dot={{ fill: '#38bdf8', r: 3, strokeWidth: 0 }}
            activeDot={{ fill: '#fff', r: 5, stroke: '#38bdf8', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const styles = {
  wrapper: {
    background: '#0f172a',
    borderRadius: '10px',
    padding: '1rem 1rem 0.5rem',
    marginTop: '0.75rem',
  },
  heading: {
    color: '#94a3b8',
    fontSize: '0.78rem',
    fontWeight: '600',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    margin: '0 0 0.5rem 0',
  },
  status: {
    color: '#94a3b8',
    fontSize: '0.825rem',
    marginTop: '0.75rem',
    textAlign: 'center',
  },
};

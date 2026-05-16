import { Sankey, Tooltip, ResponsiveContainer } from 'recharts';
import { formatTL } from '../api.js';
import { GitMerge } from 'lucide-react';

const NODE_COLORS = {
  income: '#22c55e',    // positive-500
  cash: '#3b82f6',      // brand-500
  expense: '#ef4444',   // negative-500
};

function CustomNode({ x, y, width, height, index, payload }) {
  const color = NODE_COLORS[payload.type] || NODE_COLORS.cash;
  const isRightAligned = payload.type === 'expense';
  const textX = isRightAligned ? x - 4 : x + width + 4;
  const textAnchor = isRightAligned ? 'end' : 'start';

  return (
    <g>
      <rect
        x={x} y={y}
        width={width} height={height}
        fill={color} fillOpacity={0.85}
        rx={3} ry={3}
      />
      <text
        x={textX} y={y + height / 2}
        textAnchor={textAnchor}
        dominantBaseline="middle"
        style={{ fontSize: 11, fill: 'currentColor', opacity: 0.8 }}
      >
        {payload.name.length > 14 ? payload.name.slice(0, 13) + '…' : payload.name}
      </text>
    </g>
  );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="card p-2.5 text-xs shadow-lg border border-zinc-200 dark:border-zinc-700">
      <p className="font-semibold text-zinc-700 dark:text-zinc-200">
        {p.source?.name ?? ''} → {p.target?.name ?? ''}
      </p>
      <p className="font-numeric mt-0.5 text-zinc-600 dark:text-zinc-300">
        {formatTL(p.value)} TL
      </p>
    </div>
  );
}

export default function CashflowSankey({ sankey }) {
  if (!sankey.nodes.length || !sankey.links.length) {
    return (
      <div className="card p-6 flex flex-col items-center justify-center text-center gap-2 min-h-[160px]">
        <GitMerge className="w-8 h-8 text-zinc-300 dark:text-zinc-600" />
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Seçili filtrelerde akış verisi yok
        </p>
      </div>
    );
  }

  const data = {
    nodes: sankey.nodes.map(n => ({ name: n.name, type: n.type })),
    links: sankey.links.map(l => ({
      source: l.source,
      target: l.target,
      value: Math.max(l.value, 0.01),  // recharts sıfır değeri desteklemiyor
    })),
  };

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold mb-3 text-zinc-700 dark:text-zinc-300">
        Nakit Akış Diyagramı
      </h3>
      <div className="w-full" style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={data}
            node={<CustomNode />}
            nodePadding={16}
            nodeWidth={14}
            margin={{ top: 8, right: 80, bottom: 8, left: 80 }}
            iterations={0}
            link={{ strokeOpacity: 0.3 }}
          >
            <Tooltip content={<CustomTooltip />} />
          </Sankey>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm" style={{ background: NODE_COLORS.income }} />
          Giriş
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm" style={{ background: NODE_COLORS.cash }} />
          Nakit
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-sm" style={{ background: NODE_COLORS.expense }} />
          Çıkış
        </span>
      </div>
    </div>
  );
}

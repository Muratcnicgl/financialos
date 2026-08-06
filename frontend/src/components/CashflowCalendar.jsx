import { useState } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { todayLocalISO } from '../api.js';
import { formatPara, formatSayi } from '../lib/money.js';

const TR_MONTHS = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran',
                   'Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
const TR_DAYS_SHORT = ['Pzt','Sal','Çar','Per','Cum','Cmt','Paz'];

function buildCalendarGrid(year, month) {
  // month: 0-indexed
  const firstDay = new Date(year, month, 1);
  // Pazartesi=0 başlangıç
  const startOffset = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function isoStr(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export default function CashflowCalendar({ days }) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [selected, setSelected] = useState(null);  // { date, day: ForecastDay }

  // Forecast günlerini map'e çevir: ISO date -> ForecastDay
  const dayMap = {};
  for (const d of days) {
    dayMap[d.date] = d;
  }

  const cells = buildCalendarGrid(viewYear, viewMonth);

  const prevMonth = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  };

  return (
    <div className="card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          Takvim Görünümü
        </h3>
        <div className="flex items-center gap-1">
          <button type="button" onClick={prevMonth} className="btn btn-ghost btn-icon !p-1">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300 min-w-[110px] text-center">
            {TR_MONTHS[viewMonth]} {viewYear}
          </span>
          <button type="button" onClick={nextMonth} className="btn btn-ghost btn-icon !p-1">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Gün isimleri */}
      <div className="grid grid-cols-7 mb-1">
        {TR_DAYS_SHORT.map(d => (
          <div key={d} className="text-center text-[10px] text-zinc-400 dark:text-zinc-500 py-1 font-medium">
            {d}
          </div>
        ))}
      </div>

      {/* Takvim grid */}
      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((day, i) => {
          if (!day) {
            return <div key={i} className="aspect-square" />;
          }
          const iso = isoStr(viewYear, viewMonth, day);
          const forecastDay = dayMap[iso];
          const isToday = iso === todayLocalISO(); // W3-002: UTC değil yerel gün
          const hasForecast = !!forecastDay;
          const isCrunch = forecastDay?.crunch;
          const balance = forecastDay?.closing_balance;
          const isSelected = selected?.date === iso;

          return (
            <button
              key={i}
              onClick={() => {
                if (hasForecast) setSelected(isSelected ? null : { date: iso, day: forecastDay });
              }}
              className={`
                relative aspect-square rounded-lg flex flex-col items-center justify-center p-0.5 text-center
                transition-colors
                ${isToday ? 'ring-1 ring-brand-500' : ''}
                ${isSelected ? 'bg-brand-100 dark:bg-brand-900/30' : ''}
                ${hasForecast && !isSelected ? 'hover:bg-zinc-100 dark:hover:bg-zinc-800/60 cursor-pointer' : ''}
                ${!hasForecast ? 'opacity-35 cursor-default' : ''}
              `}
            >
              <span className={`text-[10px] font-medium leading-none ${isToday ? 'text-brand-600 dark:text-brand-400 font-bold' : 'text-zinc-600 dark:text-zinc-400'}`}>
                {day}
              </span>
              {hasForecast && (
                <span className={`text-[9px] font-numeric leading-none mt-0.5 ${balance >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                  {balance >= 0 ? '' : '−'}{formatSayi(Math.abs(balance), { compact: true })}
                </span>
              )}
              {isCrunch && (
                <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-negative-500" />
              )}
            </button>
          );
        })}
      </div>

      {/* Seçili gün detayı */}
      {selected && (
        <div className="mt-3 p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
              {selected.date} olayları
            </p>
            <button type="button" onClick={() => setSelected(null)} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 min-w-[44px] min-h-[44px] inline-flex items-center justify-center shrink-0 -my-2 -mr-2">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          {selected.day.events.length === 0 ? (
            <p className="text-xs text-zinc-400 dark:text-zinc-500">Bu gün için kayıt yok.</p>
          ) : (
            <div className="space-y-1">
              {selected.day.events.map((ev, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-zinc-600 dark:text-zinc-400 truncate max-w-[70%]">{ev.label}</span>
                  <span className={`font-numeric font-semibold flex-shrink-0 ${ev.amount >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                    {ev.amount > 0 ? '+' : ''}{formatPara(ev.amount)}
                  </span>
                </div>
              ))}
              <div className="border-t border-zinc-200 dark:border-zinc-700 mt-1.5 pt-1.5 flex justify-between text-xs font-semibold">
                <span className="text-zinc-500 dark:text-zinc-400">Kapanış</span>
                <span className={`font-numeric ${selected.day.closing_balance >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                  {formatPara(selected.day.closing_balance)}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
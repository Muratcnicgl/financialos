/**
 * Generic skeleton placeholder — animate-pulse shimmer.
 * className ile boyut ve şekil dışarıdan verilir.
 *
 * Kullanım örnekleri:
 *   <Skeleton className="h-4 w-32" />           text satırı
 *   <Skeleton className="h-7 w-1/2" />           başlık
 *   <Skeleton className="h-24 w-full" />          büyük kart
 *   <Skeleton className="w-10 h-10 rounded-full" /> avatar
 */
export function Skeleton({ className = '' }) {
  return (
    <div
      className={`animate-pulse bg-zinc-200 dark:bg-zinc-800 rounded-md ${className}`}
      aria-hidden="true"
    />
  );
}

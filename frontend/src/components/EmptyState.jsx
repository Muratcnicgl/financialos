/**
 * Generic boş durum bileşeni.
 *
 * Props:
 *   icon        — lucide-react component (opsiyonel)
 *   title       — kısa başlık (zorunlu)
 *   description — açıklama metni (opsiyonel)
 *   ctaLabel    — eylem butonu metni (onCta ile birlikte verilmeli)
 *   onCta       — eylem butonu tıklama handler'ı
 *   children    — ek içerik (öneri chips, vb.)
 *   fullHeight  — true ise h-full flex column (Coach mesaj alanı gibi scroll container içi)
 */
export default function EmptyState({
  icon: Icon,
  title,
  description,
  ctaLabel,
  onCta,
  children,
  fullHeight = false,
}) {
  if (fullHeight) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center px-4">
        {Icon && (
          <div className="w-12 h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-3">
            <Icon className="w-6 h-6 text-zinc-400 dark:text-zinc-500" />
          </div>
        )}
        <h3 className="font-medium text-base mb-1">{title}</h3>
        {description && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mb-4">{description}</p>
        )}
        {ctaLabel && onCta && (
          <button onClick={onCta} className="btn btn-primary !text-xs mb-4">{ctaLabel}</button>
        )}
        {children}
      </div>
    );
  }

  return (
    <div className="card py-12 px-8 text-center">
      {Icon && (
        <div className="w-12 h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mx-auto mb-3">
          <Icon className="w-6 h-6 text-zinc-400 dark:text-zinc-500" />
        </div>
      )}
      <h3 className="font-medium text-base mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-sm mx-auto mb-4">{description}</p>
      )}
      {ctaLabel && onCta && (
        <button onClick={onCta} className="btn btn-primary !text-xs">{ctaLabel}</button>
      )}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

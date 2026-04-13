import { useEffect, useRef } from 'react';

export default function Toast({ message, type = 'error', onClose, duration = 5000 }) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => onCloseRef.current(), duration);
    return () => clearTimeout(timer);
  }, [message, duration]);

  if (!message) return null;

  const base =
    'fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3.5 rounded-xl shadow-lg text-sm font-medium transition-all';

  const variants = {
    error: 'bg-red-600 text-white',
    success: 'bg-green-600 text-white',
    info: 'bg-blue-600 text-white',
  };

  return (
    <div className={`${base} ${variants[type] ?? variants.error}`} role="alert">
      <span>{message}</span>
      <button
        onClick={onClose}
        className="ml-2 text-white/80 hover:text-white text-lg leading-none"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

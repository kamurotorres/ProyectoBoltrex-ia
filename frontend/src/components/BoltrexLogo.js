import React from 'react';

// Logo de Boltrex (P2.27): el mismo rayo del ícono de la pestaña (public/favicon.svg).
const BoltrexLogo = ({ size = 32, className = '', title = 'Boltrex' }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label={title}>
    <rect width="64" height="64" rx="14" fill="#09090b" />
    <rect x="1.5" y="1.5" width="61" height="61" rx="12.5" fill="none" stroke="#27272a" strokeWidth="3" />
    <path d="M36 8 L16 36 H30 L26 56 L48 26 H34 Z" fill="#16a34a" stroke="#22c55e" strokeWidth="2" strokeLinejoin="round" />
  </svg>
);

export default BoltrexLogo;

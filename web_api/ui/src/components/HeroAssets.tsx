import React from 'react';

export const CommanderSVG = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 200 300" className={className} xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="armorGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#2DE2E6" stopOpacity="0.8" />
        <stop offset="100%" stopColor="#0B1224" stopOpacity="0.9" />
      </linearGradient>
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="5" result="coloredBlur" />
        <feMerge>
          <feMergeNode in="coloredBlur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    {/* Stylized Silhouette */}
    <path 
      d="M100,50 L120,60 L115,90 L140,100 L130,150 L160,160 L150,220 L180,280 L20,280 L50,220 L40,160 L70,150 L60,100 L85,90 L80,60 Z" 
      fill="url(#armorGradient)" 
      filter="url(#glow)"
    />
    {/* Visor */}
    <rect x="90" y="70" width="20" height="5" fill="#2DE2E6" filter="url(#glow)" />
    {/* Sword */}
    <path d="M160,160 L180,100 L190,100 L195,80 L185,80 L190,20 L170,20 L175,80 L165,80 L170,100 L130,150" fill="#EAF0FF" opacity="0.8" />
  </svg>
);

export const BossSVG = ({ className }: { className?: string }) => (
  <svg viewBox="0 0 300 300" className={className} xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="bossGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#F43F5E" stopOpacity="0.8" />
        <stop offset="100%" stopColor="#0B1224" stopOpacity="0.9" />
      </linearGradient>
      <filter id="fireGlow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="8" result="coloredBlur" />
        <feMerge>
          <feMergeNode in="coloredBlur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
    {/* Horns / Spikes */}
    <path d="M50,100 Q20,20 80,80" fill="none" stroke="#F43F5E" strokeWidth="5" />
    <path d="M250,100 Q280,20 220,80" fill="none" stroke="#F43F5E" strokeWidth="5" />
    
    {/* Bulk Silhouette */}
    <path 
      d="M80,80 L220,80 L240,120 L280,140 L260,200 L290,280 L10,280 L40,200 L20,140 L60,120 Z" 
      fill="url(#bossGradient)" 
      filter="url(#fireGlow)"
    />
    
    {/* Eyes */}
    <circle cx="120" cy="110" r="5" fill="#FBBF24" />
    <circle cx="180" cy="110" r="5" fill="#FBBF24" />
  </svg>
);

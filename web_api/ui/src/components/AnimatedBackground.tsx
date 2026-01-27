import React, { useMemo } from 'react';

/**
 * AnimatedBackground - Epic Medieval/Fantasy Guild Background
 *
 * ALLE FARBEN werden über CSS-Variablen in index.css gesteuert:
 * - --scene-sky-*      : Himmel-Gradient
 * - --scene-mountain-* : Berg-Ebenen
 * - --scene-silhouette : Krieger-Silhouetten
 * - --scene-torch-*    : Fackel-Lichteffekte
 * - --ember-color-*    : Funken/Glut
 * - --dust-color       : Staubpartikel
 *
 * Änderungen in index.css werden global angewendet.
 */

// Epic background scene SVG - uses CSS variables for all colors
const EpicScene = () => (
  <svg
    className="epic-scene"
    viewBox="0 0 1920 1080"
    preserveAspectRatio="xMidYMax slice"
    xmlns="http://www.w3.org/2000/svg"
  >
    <defs>
      {/* Gradients using CSS variables */}
      <linearGradient id="skyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="var(--scene-sky-top)" />
        <stop offset="40%" stopColor="var(--scene-sky-mid)" />
        <stop offset="70%" stopColor="var(--scene-sky-mid)" />
        <stop offset="100%" stopColor="var(--scene-sky-bottom)" />
      </linearGradient>

      <linearGradient id="moonGlow" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stopColor="var(--scene-moon-color)" stopOpacity="0.3" />
        <stop offset="100%" stopColor="var(--scene-torch-color)" stopOpacity="0" />
      </linearGradient>

      <radialGradient id="torchGlow1" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="var(--scene-torch-color)" stopOpacity="0.4" />
        <stop offset="50%" stopColor="var(--scene-torch-color-alt)" stopOpacity="0.15" />
        <stop offset="100%" stopColor="var(--scene-torch-color-alt)" stopOpacity="0" />
      </radialGradient>

      <radialGradient id="torchGlow2" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="var(--scene-torch-color)" stopOpacity="0.3" />
        <stop offset="100%" stopColor="var(--scene-torch-color-alt)" stopOpacity="0" />
      </radialGradient>

      {/* Fog filter */}
      <filter id="fog" x="-50%" y="-50%" width="200%" height="200%">
        <feTurbulence type="fractalNoise" baseFrequency="0.01" numOctaves="3" result="noise" />
        <feGaussianBlur in="noise" stdDeviation="20" result="blur" />
        <feColorMatrix type="matrix" values="1 0 0 0 0.1  0 1 0 0 0.08  0 0 1 0 0.05  0 0 0 0.3 0" />
      </filter>
    </defs>

    {/* Sky background */}
    <rect width="100%" height="100%" fill="url(#skyGradient)" />

    {/* Moon/Sun glow */}
    <ellipse cx="1600" cy="200" rx="300" ry="300" fill="url(#moonGlow)" />
    <circle cx="1600" cy="200" r="60" fill="var(--scene-moon-color)" opacity="0.15" />

    {/* Far mountains - Layer 3 (darkest, furthest) */}
    <path
      d="M0 600 L200 400 L400 550 L600 350 L800 500 L1000 300 L1200 450 L1400 280 L1600 400 L1800 320 L1920 450 L1920 1080 L0 1080 Z"
      fill="var(--scene-mountain-far)"
      opacity="0.6"
    />

    {/* Mid mountains - Layer 2 */}
    <path
      d="M0 700 L150 550 L350 650 L500 480 L700 600 L900 420 L1100 580 L1300 400 L1500 550 L1700 450 L1920 600 L1920 1080 L0 1080 Z"
      fill="var(--scene-mountain-mid)"
      opacity="0.8"
    />

    {/* Castle silhouette on mountain */}
    <g fill="var(--scene-castle)" opacity="0.9">
      {/* Main castle body */}
      <rect x="1300" y="380" width="200" height="180" />
      {/* Left tower */}
      <rect x="1280" y="320" width="40" height="240" />
      <polygon points="1280,320 1300,280 1320,320" />
      {/* Right tower */}
      <rect x="1480" y="340" width="35" height="220" />
      <polygon points="1480,340 1497,300 1515,340" />
      {/* Center tower (tallest) */}
      <rect x="1370" y="300" width="60" height="260" />
      <polygon points="1370,300 1400,240 1430,300" />
      {/* Battlements */}
      <rect x="1300" y="375" width="15" height="20" />
      <rect x="1330" y="375" width="15" height="20" />
      <rect x="1360" y="375" width="15" height="20" />
      <rect x="1440" y="375" width="15" height="20" />
      <rect x="1470" y="375" width="15" height="20" />
    </g>

    {/* Near mountains/hills - Layer 1 */}
    <path
      d="M0 800 L100 700 L250 780 L400 650 L550 750 L700 620 L850 720 L1000 600 L1150 700 L1300 560 L1450 680 L1600 580 L1750 700 L1920 620 L1920 1080 L0 1080 Z"
      fill="var(--scene-mountain-near)"
    />

    {/* Ground/foreground */}
    <path
      d="M0 900 L200 870 L400 890 L600 860 L800 880 L1000 850 L1200 875 L1400 855 L1600 870 L1800 850 L1920 880 L1920 1080 L0 1080 Z"
      fill="var(--scene-ground)"
    />

    {/* Torch glow left */}
    <ellipse cx="250" cy="950" rx="150" ry="100" fill="url(#torchGlow1)" />

    {/* Torch glow right */}
    <ellipse cx="1700" cy="970" rx="120" ry="80" fill="url(#torchGlow2)" />

    {/* Torch glow center */}
    <ellipse cx="960" cy="1000" rx="200" ry="120" fill="url(#torchGlow1)" opacity="0.7" />

    {/* === WARRIOR SILHOUETTES === */}
    {/* All warriors use --scene-silhouette color */}

    {/* Left Samurai - Standing with katana */}
    <g fill="var(--scene-silhouette)" transform="translate(150, 700)">
      <ellipse cx="50" cy="20" rx="18" ry="20" />
      <path d="M30 40 L30 120 L45 120 L45 180 L55 180 L55 120 L70 120 L70 40 Z" />
      <path d="M20 45 L30 40 L30 70 L20 75 Z" />
      <path d="M80 45 L70 40 L70 70 L80 75 Z" />
      <path d="M35 5 L50 -15 L65 5" stroke="var(--scene-silhouette)" strokeWidth="4" fill="none" />
      <rect x="75" y="30" width="4" height="100" transform="rotate(15, 75, 30)" />
      <rect x="73" y="125" width="8" height="15" transform="rotate(15, 75, 30)" />
    </g>

    {/* Center-left warrior - Knight with sword raised */}
    <g fill="var(--scene-silhouette)" transform="translate(400, 720)">
      <circle cx="50" cy="20" r="22" />
      <rect x="45" y="-5" width="10" height="15" />
      <path d="M25 42 L25 100 L40 100 L40 160 L60 160 L60 100 L75 100 L75 42 Z" />
      <path d="M25 45 L5 140 L25 130 L25 45" opacity="0.8" />
      <rect x="80" y="-30" width="5" height="90" transform="rotate(-20, 80, 30)" />
      <polygon points="80,-35 82,-55 85,-35" transform="rotate(-20, 80, 30)" />
      <ellipse cx="20" cy="70" rx="20" ry="30" />
    </g>

    {/* Center warrior - Large warrior with banner */}
    <g fill="var(--scene-silhouette)" transform="translate(750, 680)">
      <circle cx="60" cy="25" r="28" />
      <path d="M35 15 L25 -20 M85 15 L95 -20" stroke="var(--scene-silhouette)" strokeWidth="6" strokeLinecap="round" />
      <path d="M20 55 L20 130 L45 130 L45 200 L75 200 L75 130 L100 130 L100 55 Z" />
      <ellipse cx="15" cy="70" rx="20" ry="15" />
      <ellipse cx="105" cy="70" rx="20" ry="15" />
      <rect x="110" y="20" width="6" height="150" />
      <path d="M116 30 L140 50 L140 80 L116 100 Z" />
      <rect x="-10" y="-60" width="5" height="200" />
      <path d="M-5 -60 L60 -40 L60 0 L-5 -20 Z" fill="var(--scene-ground)" />
      <path d="M-5 -60 L60 -40 L60 0 L-5 -20 Z" fill="var(--scene-silhouette)" opacity="0.5" />
    </g>

    {/* Center-right Ronin - Crouching with two swords */}
    <g fill="var(--scene-silhouette)" transform="translate(1050, 760)">
      <ellipse cx="50" cy="15" rx="35" ry="12" />
      <circle cx="50" cy="25" r="18" />
      <path d="M25 45 L20 90 L40 95 L50 70 L60 95 L80 90 L75 45 Z" />
      <path d="M30 90 L10 120 L25 125 L45 100" />
      <path d="M70 90 L90 120 L75 125 L55 100" />
      <rect x="30" y="10" width="3" height="80" transform="rotate(-30, 50, 50)" />
      <rect x="70" y="10" width="3" height="80" transform="rotate(30, 50, 50)" />
    </g>

    {/* Right warrior - Archer */}
    <g fill="var(--scene-silhouette)" transform="translate(1350, 730)">
      <circle cx="40" cy="20" r="20" />
      <path d="M20 10 L10 0 L40 -10 L70 0 L60 10" />
      <path d="M20 40 L20 100 L35 100 L35 150 L50 150 L50 100 L65 100 L65 40 Z" />
      <path d="M65 40 L90 130 L65 120 L65 40" opacity="0.7" />
      <path d="M-10 20 Q-30 70 -10 120" stroke="var(--scene-silhouette)" strokeWidth="4" fill="none" />
      <line x1="-10" y1="20" x2="-10" y2="120" stroke="var(--scene-silhouette)" strokeWidth="2" />
      <line x1="0" y1="70" x2="60" y2="50" stroke="var(--scene-silhouette)" strokeWidth="3" />
      <rect x="55" y="30" width="15" height="50" rx="3" />
    </g>

    {/* Far right - Spearman silhouette */}
    <g fill="var(--scene-silhouette)" transform="translate(1600, 750)">
      <circle cx="40" cy="20" r="18" />
      <path d="M25 38 L25 90 L35 90 L35 140 L50 140 L50 90 L60 90 L60 38 Z" />
      <rect x="70" y="-80" width="4" height="200" />
      <polygon points="70,-85 72,-110 74,-85" />
      <path d="M60 40 L75 100 L60 90" opacity="0.7" />
    </g>

    {/* Additional small figures in background for scale */}
    <g fill="var(--scene-silhouette-distant)" opacity="0.5">
      <rect x="50" y="830" width="8" height="25" />
      <circle cx="54" cy="823" r="5" />
      <rect x="80" y="835" width="7" height="22" />
      <circle cx="83" cy="828" r="4" />
      <rect x="1800" y="840" width="8" height="25" />
      <circle cx="1804" cy="833" r="5" />
      <rect x="1840" y="838" width="7" height="23" />
      <circle cx="1843" cy="831" r="4" />
    </g>

    {/* Atmospheric fog overlay */}
    <rect x="0" y="600" width="100%" height="500" fill="url(#fog)" opacity="0.15" style={{ mixBlendMode: 'soft-light' }} />

    {/* Bottom gradient fade to blend with UI */}
    <rect x="0" y="900" width="100%" height="180" fill="url(#skyGradient)" opacity="0.5" />
  </svg>
);

const AnimatedBackground: React.FC = () => {
  // Generate floating embers (like from torches)
  const embers = useMemo(() => {
    const emberList = [];
    for (let i = 0; i < 25; i++) {
      emberList.push({
        id: i,
        x: 5 + Math.random() * 90,
        y: 70 + Math.random() * 30,
        size: 2 + Math.random() * 4,
        delay: Math.random() * 12,
        duration: 6 + Math.random() * 8,
        drift: -40 + Math.random() * 80,
      });
    }
    return emberList;
  }, []);

  // Dust/ash particles
  const dustParticles = useMemo(() => {
    const particles = [];
    for (let i = 0; i < 15; i++) {
      particles.push({
        id: i,
        x: Math.random() * 100,
        y: 20 + Math.random() * 60,
        size: 1 + Math.random() * 2,
        delay: Math.random() * 20,
        duration: 20 + Math.random() * 25,
      });
    }
    return particles;
  }, []);

  return (
    <div className="medieval-bg" aria-hidden="true">
      {/* Epic Scene Illustration */}
      <EpicScene />

      {/* Overlay for depth */}
      <div className="scene-overlay" />

      {/* Floating Embers from torches */}
      <div className="embers-container">
        {embers.map((ember) => (
          <div
            key={ember.id}
            className="ember"
            style={{
              left: `${ember.x}%`,
              bottom: `${100 - ember.y}%`,
              width: `${ember.size}px`,
              height: `${ember.size}px`,
              animationDelay: `${ember.delay}s`,
              animationDuration: `${ember.duration}s`,
              '--drift': `${ember.drift}px`,
            } as React.CSSProperties}
          />
        ))}
      </div>

      {/* Dust/ash particles */}
      <div className="dust-container">
        {dustParticles.map((particle) => (
          <div
            key={particle.id}
            className="dust-particle"
            style={{
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              width: `${particle.size}px`,
              height: `${particle.size}px`,
              animationDelay: `${particle.delay}s`,
              animationDuration: `${particle.duration}s`,
            }}
          />
        ))}
      </div>

      {/* Vignette */}
      <div className="vignette-medieval" />
    </div>
  );
};

export default AnimatedBackground;

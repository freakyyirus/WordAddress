/**
 * AR Navigation Component for Open3Words
 * Uses WebXR Device API for browser-based AR wayfinding.
 * Falls back to a compass-style 2D view on unsupported devices.
 *
 * NOTE: WebXR AR requires HTTPS and a compatible browser (Chrome Android 81+, etc.)
 * This file is a standalone module that can be imported into the React app.
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';

// ── Utility functions ────────────────────────────────────────

function haversineDistance(loc1, loc2) {
  const R = 6371e3; // meters
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(loc2.lat - loc1.lat);
  const dLon = toRad(loc2.lon - loc1.lon);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(loc1.lat)) * Math.cos(toRad(loc2.lat)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function bearing(from, to) {
  const toRad = (d) => (d * Math.PI) / 180;
  const y = Math.sin(toRad(to.lon - from.lon)) * Math.cos(toRad(to.lat));
  const x =
    Math.cos(toRad(from.lat)) * Math.sin(toRad(to.lat)) -
    Math.sin(toRad(from.lat)) * Math.cos(toRad(to.lat)) * Math.cos(toRad(to.lon - from.lon));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function cardinalDirection(deg) {
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(deg / 45) % 8];
}

// ── 2D Compass Fallback Component ────────────────────────────

const CompassView = ({ destination, currentLocation, words }) => {
  const dist = haversineDistance(currentLocation, destination);
  const bear = bearing(currentLocation, destination);
  const cardinal = cardinalDirection(bear);

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.85)', color: '#fff', display: 'flex',
      flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui', zIndex: 9999,
    }}>
      <h2 style={{ margin: 0, fontSize: 24 }}>Navigation</h2>
      <div style={{ margin: '20px 0', fontSize: 18, fontFamily: 'monospace', color: '#4ecdc4' }}>
        ///{words}
      </div>

      {/* Compass arrow */}
      <div style={{
        width: 200, height: 200, borderRadius: '50%', border: '3px solid #4ecdc4',
        display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
        margin: '20px 0',
      }}>
        <div style={{
          width: 0, height: 0,
          borderLeft: '20px solid transparent', borderRight: '20px solid transparent',
          borderBottom: '80px solid #4ecdc4',
          transform: `rotate(${bear}deg)`, transformOrigin: 'center 60%',
        }} />
        <div style={{ position: 'absolute', top: 8, fontSize: 14, fontWeight: 700 }}>N</div>
        <div style={{ position: 'absolute', bottom: 8, fontSize: 14 }}>S</div>
        <div style={{ position: 'absolute', right: 8, fontSize: 14 }}>E</div>
        <div style={{ position: 'absolute', left: 8, fontSize: 14 }}>W</div>
      </div>

      <div style={{ display: 'flex', gap: 40, marginTop: 20 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 12, opacity: 0.7 }}>DISTANCE</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>
            {dist < 1000 ? `${dist.toFixed(0)}m` : `${(dist / 1000).toFixed(1)}km`}
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 12, opacity: 0.7 }}>DIRECTION</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{cardinal}</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 12, opacity: 0.7 }}>BEARING</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{bear.toFixed(0)}°</div>
        </div>
      </div>

      <div style={{ marginTop: 30, fontSize: 13, opacity: 0.6 }}>
        Walk {cardinal} for {dist < 1000 ? `${dist.toFixed(0)} meters` : `${(dist / 1000).toFixed(1)} km`}
      </div>
    </div>
  );
};

// ── Main AR Navigation Component ─────────────────────────────

const ARNavigation = ({ destination, currentLocation, words, onClose }) => {
  const [arSupported, setArSupported] = useState(false);

  useEffect(() => {
    if ('xr' in navigator) {
      navigator.xr.isSessionSupported('immersive-ar').then(setArSupported).catch(() => setArSupported(false));
    }
  }, []);

  if (!destination || !currentLocation) {
    return (
      <div style={{ padding: 20, background: '#333', color: '#fff', textAlign: 'center' }}>
        <p>Set a destination and enable GPS to use navigation.</p>
        <button onClick={onClose} style={{ marginTop: 10, padding: '8px 20px', borderRadius: 4 }}>Close</button>
      </div>
    );
  }

  // For now, use the 2D compass view (WebXR AR requires a Three.js setup which needs bundling)
  return (
    <div>
      <button onClick={onClose} style={{
        position: 'fixed', top: 20, right: 20, zIndex: 10000,
        padding: '10px 20px', background: '#ff4757', color: '#fff',
        border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14,
      }}>✕ Close</button>
      <CompassView destination={destination} currentLocation={currentLocation} words={words} />
      {!arSupported && (
        <div style={{
          position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)',
          zIndex: 10000, padding: '8px 16px', background: 'rgba(255,255,255,0.2)',
          borderRadius: 20, fontSize: 12, color: '#fff',
        }}>
          AR not supported — using compass view
        </div>
      )}
    </div>
  );
};

export default ARNavigation;
export { haversineDistance, bearing, cardinalDirection };

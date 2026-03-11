import React, { useState, useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const API_BASE = '';

function App() {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const markerRef = useRef(null);
  const [words, setWords] = useState('');
  const [coords, setCoords] = useState({ lat: 51.505, lon: -0.09 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('encode'); // encode | decode | voice | assistant
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [assistantQuery, setAssistantQuery] = useState('');
  const [assistantResponse, setAssistantResponse] = useState(null);
  const [correctionInput, setCorrectionInput] = useState('');
  const [corrections, setCorrections] = useState(null);
  const [gridInfo, setGridInfo] = useState(null);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  // ── Initialize map ─────────────────────────────────────────
  useEffect(() => {
    if (map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://demotiles.maplibre.org/style.json',
      center: [coords.lon, coords.lat],
      zoom: 13,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'bottom-right');

    // Geolocation control
    const geolocate = new maplibregl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
    });
    map.current.addControl(geolocate, 'bottom-right');

    map.current.on('click', (e) => {
      const { lat, lng: lon } = e.lngLat;
      fetchEncode(lat, lon);
    });
  }, []);

  // ── Place marker ───────────────────────────────────────────
  const placeMarker = useCallback((lat, lon, label) => {
    if (markerRef.current) {
      markerRef.current.remove();
    }
    const popup = new maplibregl.Popup({ offset: 25 }).setHTML(
      `<div style="padding:5px;font-family:monospace;font-size:14px;color:#667eea">
        ///${label || ''}
        <br/><small style="color:#666">${lat.toFixed(6)}, ${lon.toFixed(6)}</small>
      </div>`
    );
    markerRef.current = new maplibregl.Marker({ color: '#667eea' })
      .setLngLat([lon, lat])
      .setPopup(popup)
      .addTo(map.current);
    markerRef.current.togglePopup();
  }, []);

  // ── Encode: coords → words ─────────────────────────────────
  const fetchEncode = async (lat, lon) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/encode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat, lon }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Encode failed');
      const data = await res.json();
      setWords(data.words);
      setCoords({ lat, lon });
      setGridInfo(data.grid);
      placeMarker(lat, lon, data.words);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  // ── Decode: words → coords ─────────────────────────────────
  const fetchDecode = async () => {
    if (!words.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/decode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ words }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Decode failed');
      const data = await res.json();
      const { lat, lon } = data.coordinates;
      setCoords({ lat, lon });
      setGridInfo(data.grid);
      map.current.flyTo({ center: [lon, lat], zoom: 18, duration: 2000 });
      placeMarker(lat, lon, data.words);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  // ── Voice recording ────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder.current = new MediaRecorder(stream);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (e) => audioChunks.current.push(e.data);
      mediaRecorder.current.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(audioChunks.current, { type: 'audio/wav' });
        await sendVoice(blob);
      };

      mediaRecorder.current.start();
      setIsListening(true);
      setTimeout(() => stopRecording(), 5000);
    } catch (err) {
      setError('Microphone access denied');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current?.state === 'recording') {
      mediaRecorder.current.stop();
      setIsListening(false);
      setLoading(true);
    }
  };

  const sendVoice = async (blob) => {
    const form = new FormData();
    form.append('audio', blob, 'voice.wav');
    try {
      const res = await fetch(`${API_BASE}/voice/decode`, { method: 'POST', body: form });
      const data = await res.json();
      setTranscript(data.text || '');
      if (data.processed_words) setWords(data.processed_words);
      if (data.coordinates) {
        const { lat, lon } = data.coordinates;
        setCoords({ lat, lon });
        map.current.flyTo({ center: [lon, lat], zoom: 18, duration: 2000 });
        placeMarker(lat, lon, data.processed_words);
      }
    } catch (err) {
      setError('Voice processing failed');
    }
    setLoading(false);
  };

  // ── Error correction ───────────────────────────────────────
  const fetchCorrections = async () => {
    if (!correctionInput.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: correctionInput }),
      });
      const data = await res.json();
      setCorrections(data);
    } catch (err) {
      setError('Correction failed');
    }
    setLoading(false);
  };

  // ── Assistant ──────────────────────────────────────────────
  const sendAssistantQuery = async () => {
    if (!assistantQuery.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/assistant/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'web-user',
          query: assistantQuery,
          lat: coords.lat,
          lon: coords.lon,
        }),
      });
      const data = await res.json();
      setAssistantResponse(data);
    } catch (err) {
      setError('Assistant unavailable');
    }
    setLoading(false);
  };

  // ── Render ─────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif' }}>
      {/* Sidebar */}
      <div style={{ width: 360, background: '#fafafa', borderRight: '1px solid #e0e0e0', display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: '#fff' }}>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Open3Words</h1>
          <p style={{ margin: '4px 0 0', fontSize: 12, opacity: 0.85 }}>AI-Powered 3-Word Location System</p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #e0e0e0' }}>
          {['encode', 'decode', 'voice', 'assistant'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '10px 0', border: 'none', cursor: 'pointer', fontSize: 12, fontWeight: 600,
              background: tab === t ? '#fff' : '#f0f0f0', color: tab === t ? '#667eea' : '#888',
              borderBottom: tab === t ? '2px solid #667eea' : '2px solid transparent',
            }}>{t.toUpperCase()}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: 20, flex: 1 }}>
          {/* ENCODE tab */}
          {tab === 'encode' && (
            <div>
              <p style={{ fontSize: 14, color: '#555', marginBottom: 12 }}>Click anywhere on the map to get a 3-word address.</p>
              {words && (
                <div style={{ padding: 14, background: '#fff', borderRadius: 8, border: '1px solid #e0e0e0', marginBottom: 12 }}>
                  <div style={{ fontSize: 10, color: '#999', textTransform: 'uppercase', letterSpacing: 1 }}>Address</div>
                  <div style={{ fontSize: 20, fontFamily: 'monospace', color: '#667eea', marginTop: 4, wordBreak: 'break-all' }}>
                    ///{words}
                  </div>
                  <button onClick={() => { navigator.clipboard.writeText(`///${words}`); }} style={{
                    marginTop: 8, padding: '6px 12px', fontSize: 12, border: '1px solid #667eea', background: 'transparent',
                    color: '#667eea', borderRadius: 4, cursor: 'pointer',
                  }}>Copy</button>
                </div>
              )}
              <div style={{ fontSize: 12, color: '#888' }}>
                <div>{coords.lat.toFixed(6)}, {coords.lon.toFixed(6)}</div>
                {gridInfo && (
                  <div style={{ marginTop: 4 }}>
                    Grid: {gridInfo.size_meters?.lat?.toFixed(1)}m × {gridInfo.size_meters?.lon?.toFixed(1)}m
                  </div>
                )}
              </div>
            </div>
          )}

          {/* DECODE tab */}
          {tab === 'decode' && (
            <div>
              <p style={{ fontSize: 14, color: '#555', marginBottom: 12 }}>Enter a 3-word address to find the location.</p>
              <input
                value={words} onChange={e => setWords(e.target.value)}
                placeholder="table.chair.lamp"
                onKeyDown={e => e.key === 'Enter' && fetchDecode()}
                style={{ width: '100%', padding: 10, fontSize: 14, border: '1px solid #ccc', borderRadius: 6, marginBottom: 8, fontFamily: 'monospace' }}
              />
              <button onClick={fetchDecode} disabled={loading} style={{
                width: '100%', padding: 10, fontSize: 14, fontWeight: 600, border: 'none', borderRadius: 6,
                background: '#667eea', color: '#fff', cursor: loading ? 'wait' : 'pointer',
              }}>{loading ? 'Finding...' : 'Find Location'}</button>

              {/* Error correction section */}
              <div style={{ marginTop: 20, borderTop: '1px solid #eee', paddingTop: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Typo Correction</div>
                <input
                  value={correctionInput} onChange={e => setCorrectionInput(e.target.value)}
                  placeholder="tabel.chiar.lmap"
                  onKeyDown={e => e.key === 'Enter' && fetchCorrections()}
                  style={{ width: '100%', padding: 8, fontSize: 13, border: '1px solid #ccc', borderRadius: 4, marginBottom: 6, fontFamily: 'monospace' }}
                />
                <button onClick={fetchCorrections} style={{
                  width: '100%', padding: 8, fontSize: 12, border: 'none', borderRadius: 4,
                  background: '#eee', cursor: 'pointer',
                }}>Correct</button>
                {corrections?.suggestions?.map((s, i) => (
                  <div key={i} onClick={() => { setWords(s.words); setTab('decode'); }} style={{
                    padding: 8, marginTop: 4, background: i === 0 ? '#e8f5e9' : '#fff', borderRadius: 4,
                    border: '1px solid #e0e0e0', cursor: 'pointer', fontSize: 12,
                  }}>
                    <span style={{ fontFamily: 'monospace', color: '#667eea' }}>{s.words}</span>
                    <span style={{ float: 'right', color: '#888' }}>{s.score}%</span>
                    {s.corrections?.length > 0 && (
                      <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>
                        Fixed: {s.corrections.map(c => `${c.original}→${c.corrected}`).join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VOICE tab */}
          {tab === 'voice' && (
            <div>
              <p style={{ fontSize: 14, color: '#555', marginBottom: 16 }}>Speak a 3-word address to find the location.</p>
              <button
                onClick={isListening ? stopRecording : startRecording}
                style={{
                  width: '100%', padding: 20, fontSize: 16, fontWeight: 600, border: 'none', borderRadius: 30,
                  background: isListening ? '#ff4757' : '#2ed573', color: '#fff', cursor: 'pointer',
                  transition: 'all 0.3s', boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
                }}
              >
                {isListening ? '🔴 Listening... (tap to stop)' : '🎙️ Tap to Speak'}
              </button>
              {loading && <p style={{ textAlign: 'center', marginTop: 12, color: '#888' }}>Processing...</p>}
              {transcript && (
                <div style={{ marginTop: 16, padding: 12, background: '#fff', borderRadius: 8, border: '1px solid #e0e0e0' }}>
                  <div style={{ fontSize: 10, color: '#999', textTransform: 'uppercase' }}>Heard</div>
                  <div style={{ fontSize: 14, fontStyle: 'italic', marginTop: 4 }}>"{transcript}"</div>
                </div>
              )}
              {words && tab === 'voice' && (
                <div style={{ marginTop: 12, padding: 12, background: '#e8f5e9', borderRadius: 8, fontSize: 16, fontFamily: 'monospace', color: '#667eea', textAlign: 'center' }}>
                  ///{words}
                </div>
              )}
              <p style={{ marginTop: 20, fontSize: 12, color: '#aaa' }}>
                Try saying: "table dot chair dot lamp" or "navigate to hello world sunrise"
              </p>
            </div>
          )}

          {/* ASSISTANT tab */}
          {tab === 'assistant' && (
            <div>
              <p style={{ fontSize: 14, color: '#555', marginBottom: 12 }}>Ask me about locations, navigation, or saving favorites.</p>
              <input
                value={assistantQuery} onChange={e => setAssistantQuery(e.target.value)}
                placeholder="Navigate to the nearest park"
                onKeyDown={e => e.key === 'Enter' && sendAssistantQuery()}
                style={{ width: '100%', padding: 10, fontSize: 14, border: '1px solid #ccc', borderRadius: 6, marginBottom: 8 }}
              />
              <button onClick={sendAssistantQuery} disabled={loading} style={{
                width: '100%', padding: 10, fontSize: 14, fontWeight: 600, border: 'none', borderRadius: 6,
                background: '#764ba2', color: '#fff', cursor: loading ? 'wait' : 'pointer',
              }}>{loading ? 'Thinking...' : 'Ask Assistant'}</button>
              {assistantResponse && (
                <div style={{ marginTop: 12, padding: 12, background: '#fff', borderRadius: 8, border: '1px solid #e0e0e0' }}>
                  <div style={{ fontSize: 10, color: '#999', textTransform: 'uppercase', marginBottom: 4 }}>
                    Intent: {assistantResponse.intent}
                  </div>
                  <div style={{ fontSize: 14, color: '#333' }}>{assistantResponse.response}</div>
                  {assistantResponse.saved && (
                    <div style={{ marginTop: 8, fontSize: 12, color: '#4caf50' }}>
                      ✓ Saved as "{assistantResponse.saved.label}"
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div style={{ padding: '10px 20px', background: '#ffebee', color: '#c62828', fontSize: 13 }}>
            {error}
            <button onClick={() => setError('')} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', color: '#c62828' }}>✕</button>
          </div>
        )}

        {/* Footer */}
        <div style={{ padding: '10px 20px', borderTop: '1px solid #e0e0e0', fontSize: 11, color: '#aaa', textAlign: 'center' }}>
          Open3Words v1.0 — Open Source Location System
        </div>
      </div>

      {/* Map */}
      <div ref={mapContainer} style={{ flex: 1 }} />
    </div>
  );
}

export default App;

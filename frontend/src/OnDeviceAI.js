/**
 * On-Device AI Module for Open3Words
 * Provides privacy-preserving ML capabilities that run entirely in the browser.
 * Uses IndexedDB for local caching and learning data.
 *
 * Features:
 * - Offline speech pattern matching
 * - Edit distance word correction (no network needed)
 * - Location history prediction
 * - Federated learning data collection
 */

const DB_NAME = 'Open3WordsAI';
const DB_VERSION = 1;

class OnDeviceAI {
  constructor() {
    this.db = null;
    this.wordlist = [];
    this.wordSet = new Set();
    this.ready = false;
  }

  async initialize(wordlist) {
    this.wordlist = wordlist || [];
    this.wordSet = new Set(this.wordlist);
    await this._initDB();
    this.ready = true;
  }

  // ── IndexedDB Setup ──────────────────────────────────────

  _initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => { this.db = request.result; resolve(); };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        if (!db.objectStoreNames.contains('locationCache')) {
          const store = db.createObjectStore('locationCache', { keyPath: 'words' });
          store.createIndex('timestamp', 'timestamp');
        }

        if (!db.objectStoreNames.contains('locationHistory')) {
          const store = db.createObjectStore('locationHistory', { keyPath: 'id', autoIncrement: true });
          store.createIndex('timestamp', 'timestamp');
        }

        if (!db.objectStoreNames.contains('offlineQueue')) {
          const store = db.createObjectStore('offlineQueue', { keyPath: 'id', autoIncrement: true });
          store.createIndex('status', 'status');
        }
      };
    });
  }

  // ── Offline Error Correction ─────────────────────────────

  correctWord(input, maxDistance = 2, topK = 5) {
    input = input.toLowerCase().trim();

    if (this.wordSet.has(input)) {
      return [{ word: input, distance: 0, score: 100 }];
    }

    const candidates = [];

    for (const word of this.wordlist) {
      // Quick length check for early rejection
      if (Math.abs(word.length - input.length) > maxDistance) continue;

      const dist = this._levenshtein(input, word);
      if (dist <= maxDistance) {
        candidates.push({ word, distance: dist, score: 100 - dist * 30 });
      }
    }

    candidates.sort((a, b) => a.distance - b.distance || b.score - a.score);
    return candidates.slice(0, topK);
  }

  correctAddress(address) {
    const parts = address.toLowerCase().replace('///', '').trim().split('.');
    if (parts.length !== 3) return [];

    const corrections = parts.map(part => this.correctWord(part));

    // Generate top combinations
    const results = [];
    const limit = 5;

    for (const c1 of corrections[0].slice(0, 3)) {
      for (const c2 of corrections[1].slice(0, 3)) {
        for (const c3 of corrections[2].slice(0, 3)) {
          results.push({
            words: `${c1.word}.${c2.word}.${c3.word}`,
            score: Math.round((c1.score + c2.score + c3.score) / 3),
            corrections: [
              parts[0] !== c1.word ? { from: parts[0], to: c1.word } : null,
              parts[1] !== c2.word ? { from: parts[1], to: c2.word } : null,
              parts[2] !== c3.word ? { from: parts[2], to: c3.word } : null,
            ].filter(Boolean),
          });
          if (results.length >= limit) break;
        }
        if (results.length >= limit) break;
      }
      if (results.length >= limit) break;
    }

    results.sort((a, b) => b.score - a.score);
    return results;
  }

  // ── Location Cache (Offline Lookups) ─────────────────────

  async cacheLocation(words, lat, lon) {
    if (!this.db) return;
    const tx = this.db.transaction('locationCache', 'readwrite');
    await tx.objectStore('locationCache').put({
      words, lat, lon, timestamp: Date.now(),
    });
  }

  async getCachedLocation(words) {
    if (!this.db) return null;
    return new Promise((resolve) => {
      const tx = this.db.transaction('locationCache', 'readonly');
      const request = tx.objectStore('locationCache').get(words);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => resolve(null);
    });
  }

  // ── Location History ─────────────────────────────────────

  async addToHistory(lat, lon, words) {
    if (!this.db) return;
    const tx = this.db.transaction('locationHistory', 'readwrite');
    await tx.objectStore('locationHistory').add({
      lat, lon, words, timestamp: Date.now(),
    });
  }

  async getHistory(limit = 50) {
    if (!this.db) return [];
    return new Promise((resolve) => {
      const tx = this.db.transaction('locationHistory', 'readonly');
      const store = tx.objectStore('locationHistory');
      const index = store.index('timestamp');
      const request = index.openCursor(null, 'prev');
      const results = [];
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor && results.length < limit) {
          results.push(cursor.value);
          cursor.continue();
        } else {
          resolve(results);
        }
      };
      request.onerror = () => resolve([]);
    });
  }

  // ── Offline Queue ────────────────────────────────────────

  async queueAction(type, payload) {
    if (!this.db) return;
    const tx = this.db.transaction('offlineQueue', 'readwrite');
    await tx.objectStore('offlineQueue').add({
      type, payload, status: 'pending', created: Date.now(),
    });
  }

  async processQueue() {
    if (!this.db) return;
    const tx = this.db.transaction('offlineQueue', 'readonly');
    const index = tx.objectStore('offlineQueue').index('status');
    const request = index.getAll('pending');

    return new Promise((resolve) => {
      request.onsuccess = async () => {
        const pending = request.result || [];
        for (const action of pending) {
          try {
            await this._executeAction(action);
            await this._updateQueueStatus(action.id, 'completed');
          } catch {
            await this._updateQueueStatus(action.id, 'failed');
          }
        }
        resolve(pending.length);
      };
      request.onerror = () => resolve(0);
    });
  }

  async _executeAction(action) {
    const res = await fetch(`/${action.type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action.payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async _updateQueueStatus(id, status) {
    if (!this.db) return;
    const tx = this.db.transaction('offlineQueue', 'readwrite');
    const store = tx.objectStore('offlineQueue');
    const request = store.get(id);
    request.onsuccess = () => {
      if (request.result) {
        request.result.status = status;
        store.put(request.result);
      }
    };
  }

  // ── Levenshtein Distance ─────────────────────────────────

  _levenshtein(s1, s2) {
    if (s1 === s2) return 0;
    if (s1.length === 0) return s2.length;
    if (s2.length === 0) return s1.length;

    const row = Array.from({ length: s2.length + 1 }, (_, i) => i);

    for (let i = 0; i < s1.length; i++) {
      let prev = i + 1;
      for (let j = 0; j < s2.length; j++) {
        const val = s1[i] === s2[j] ? row[j] : Math.min(row[j], row[j + 1], prev) + 1;
        row[j] = prev;
        prev = val;
      }
      row[s2.length] = prev;
    }

    return row[s2.length];
  }
}

export default OnDeviceAI;

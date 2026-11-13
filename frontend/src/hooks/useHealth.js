import { useState, useEffect, useCallback } from 'react';
import { getHealth, getStats } from '../api/health';

export function useHealth(intervalMs = 10000) {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [online, setOnline] = useState(null);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchHealth = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([getHealth(), getStats()]);
      setHealth(h);
      setStats(s);
      setOnline(true);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setOnline(false);
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const id = setInterval(fetchHealth, intervalMs);
    return () => clearInterval(id);
  }, [fetchHealth, intervalMs]);

  return { health, stats, online, error, lastUpdated, refetch: fetchHealth };
}

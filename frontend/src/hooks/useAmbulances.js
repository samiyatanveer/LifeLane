import { useState, useEffect, useCallback } from 'react';
import { getAmbulances } from '../api/dispatch';

export function useAmbulances(intervalMs = null) {
  const [ambulances, setAmbulances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getAmbulances();
      setAmbulances(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch();
    if (intervalMs) {
      const id = setInterval(fetch, intervalMs);
      return () => clearInterval(id);
    }
  }, [fetch, intervalMs]);

  return { ambulances, loading, error, refetch: fetch };
}


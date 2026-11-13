import { useState, useEffect, useCallback } from 'react';
import { getDetections } from '../api/detection';

export function useDetections(limit = 20, intervalMs = null) {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetch = useCallback(async () => {
    try {
      const data = await getDetections(limit);
      setDetections(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetch();
    if (intervalMs) {
      const id = setInterval(fetch, intervalMs);
      return () => clearInterval(id);
    }
  }, [fetch, intervalMs]);

  return { detections, loading, error, refetch: fetch };
}

import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import { getErrorMessage } from '@/lib/utils';

// Búsqueda en el servidor mientras se escribe (mantenimiento fase 5; antes copiada en cada pantalla).
//   const { results, searching } = useServerSearch('/clients', texto, { errorMessage: 'Error al buscar clientes' });
// - Desde `minLength` caracteres (2) y `delay` ms (300) después de la última tecla.
// - Solo se usa la respuesta de la ÚLTIMA búsqueda (si llegan desordenadas, las viejas se descartan).
// - `onResults(items)` se llama con cada respuesta válida (p. ej. para guardar los productos vistos).
export function useServerSearch(path, text, { minLength = 2, delay = 300, pageSize = 20, params = {}, errorMessage, onResults } = {}) {
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const requestId = useRef(0);
  const onResultsRef = useRef(onResults);
  onResultsRef.current = onResults;
  const paramsKey = JSON.stringify(params);

  useEffect(() => {
    const q = (text || '').trim();
    if (q.length < minLength) {
      setResults([]);
      return undefined;
    }
    const id = ++requestId.current;
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.get(path, { params: { ...JSON.parse(paramsKey), search: q, page_size: pageSize } });
        if (id !== requestId.current) return;
        const found = res.data.items || [];
        setResults(found);
        if (onResultsRef.current) onResultsRef.current(found);
      } catch (error) {
        if (id === requestId.current) toast.error(getErrorMessage(error, errorMessage || 'Error al buscar'));
      } finally {
        if (id === requestId.current) setSearching(false);
      }
    }, delay);
    return () => clearTimeout(t);
  }, [path, text, minLength, delay, pageSize, paramsKey, errorMessage]);

  // Mientras el texto sea corto no se muestran resultados viejos.
  return { results: (text || '').trim().length >= minLength ? results : [], searching };
}

export default useServerSearch;

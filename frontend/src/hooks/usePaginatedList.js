import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/utils';

// Listado paginado en el servidor (backlog P1.18).
//
//   const list = usePaginatedList(`${API}/products`, { params: { stock: 'low' } });
//   list.items, list.total, list.page, list.pages, list.search, list.setSearch, list.reload()
//   <Pagination {...list.paginationProps} />
//
// - La búsqueda va al servidor (con espera de 300 ms mientras se escribe) y vuelve a la página 1.
// - Cambiar `params` (filtros) también vuelve a la página 1.
// - El servidor responde { items, total, page, page_size, pages, ...extra } (extra = p. ej. summary).

export const PAGE_SIZES = [25, 50, 100];
const SEARCH_DELAY_MS = 300;

export function usePaginatedList(url, { params = {}, pageSize: initialPageSize = 50, enabled = true, errorMessage } = {}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [search, setSearchState] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1 });
  const [loading, setLoading] = useState(true);
  const paramsKey = JSON.stringify(params);
  const requestId = useRef(0);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(t);
  }, [search]);

  // Filtros o búsqueda nuevos → primera página.
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, paramsKey]);

  const load = useCallback(async () => {
    if (!enabled) return;
    const id = ++requestId.current;
    setLoading(true);
    try {
      const query = { ...JSON.parse(paramsKey), page, page_size: pageSize };
      if (debouncedSearch) query.search = debouncedSearch;
      const res = await axios.get(url, { params: query });
      // Solo la respuesta más reciente se pinta (si el usuario escribe rápido llegan desordenadas).
      if (id === requestId.current) setData(res.data);
    } catch (error) {
      if (id === requestId.current) toast.error(getErrorMessage(error, errorMessage || 'Error al cargar los datos'));
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [url, paramsKey, page, pageSize, debouncedSearch, enabled, errorMessage]);

  useEffect(() => {
    load();
  }, [load]);

  const setSearch = (value) => setSearchState(value);
  const setPageSize = (size) => {
    setPageSizeState(size);
    setPage(1);
  };

  return {
    ...data,
    items: data.items || [],
    loading,
    page,
    pageSize,
    search,
    setSearch,
    setPage,
    setPageSize,
    reload: load,
    paginationProps: {
      page,
      pages: data.pages || 1,
      total: data.total || 0,
      pageSize,
      loading,
      onPageChange: setPage,
      onPageSizeChange: setPageSize,
    },
  };
}

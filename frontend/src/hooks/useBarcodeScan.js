import { useCallback } from 'react';
import { toast } from 'sonner';
import { api } from '@/api/client';
import { getErrorMessage } from '@/lib/utils';

// Lector de código de barras (rama compras-estilo-pos, decisión 3.A): el lector escribe el código y manda
// Enter. Se busca el producto con ese código EXACTO (primero en lo ya encontrado, si no en el servidor con
// GET /products?barcode=…): un código parcial nunca agrega otro producto.
//   const scan = useBarcodeScan();  const product = await scan(código, resultadosActuales);
export function useBarcodeScan() {
  return useCallback(async (code, known = []) => {
    const wanted = String(code || '').trim();
    if (!wanted) return null;
    const local = known.find((p) => p.barcode === wanted);
    if (local) return local;
    try {
      const res = await api.get('/products', { params: { barcode: wanted, page_size: 1 } });
      const found = (res.data.items || [])[0];
      if (found) return found;
      toast.error(`No hay un producto con el código «${wanted}».`);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al buscar el código'));
    }
    return null;
  }, []);
}

export default useBarcodeScan;

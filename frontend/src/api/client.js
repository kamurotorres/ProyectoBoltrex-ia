// Cliente único del backend (mantenimiento fase 4).
//   import { api } from '@/api/client';
//   const { data } = await api.get('/clients', { params: { search } });
// - `api.get/post/put/patch/delete(ruta, …)` = axios con el prefijo `/api` (mismas opciones que axios).
// - El token y los interceptores de sesión (401/403) los configura src/auth/AuthProvider.js sobre axios,
//   así aplican también a usePaginatedList y a las descargas.
// - `API` (la URL base) se sigue exportando para los listados paginados y las exportaciones.
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
export const API = `${BACKEND_URL}/api`;

const url = (path) => `${API}${path}`;

export const api = {
  get: (path, config) => axios.get(url(path), config),
  post: (path, data, config) => axios.post(url(path), data, config),
  put: (path, data, config) => axios.put(url(path), data, config),
  patch: (path, data, config) => axios.patch(url(path), data, config),
  delete: (path, config) => axios.delete(url(path), config),
};

export const setAuthToken = (token) => {
  axios.defaults.headers.common.Authorization = `Bearer ${token}`;
};

export const clearAuthToken = () => {
  delete axios.defaults.headers.common.Authorization;
};

export { axios };

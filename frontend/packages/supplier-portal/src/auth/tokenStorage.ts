const ACCESS_TOKEN_KEY = "accessToken";
const REFRESH_TOKEN_KEY = "refreshToken";
const SUPPLIER_ID_KEY = "supplierId";

const getStorage = (rememberMe: boolean): Storage => {
  return rememberMe ? localStorage : sessionStorage;
};

export const saveTokens = (
  accessToken: string,
  refreshToken: string,
  rememberMe: boolean
): void => {
  clearTokens();

  const storage = getStorage(rememberMe);

  storage.setItem(ACCESS_TOKEN_KEY, accessToken);
  storage.setItem(REFRESH_TOKEN_KEY, refreshToken);
};

export const getAccessToken = (): string | null => {
  return (
    localStorage.getItem(ACCESS_TOKEN_KEY) ??
    sessionStorage.getItem(ACCESS_TOKEN_KEY)
  );
};

export const getRefreshToken = (): string | null => {
  return (
    localStorage.getItem(REFRESH_TOKEN_KEY) ??
    sessionStorage.getItem(REFRESH_TOKEN_KEY)
  );
};

export const saveSupplierId = (
  supplierId: string,
  rememberMe: boolean
): void => {
  const storage = getStorage(rememberMe);

  localStorage.removeItem(SUPPLIER_ID_KEY);
  sessionStorage.removeItem(SUPPLIER_ID_KEY);

  storage.setItem(SUPPLIER_ID_KEY, supplierId);
};

export const getSupplierId = (): string | null => {
  return (
    localStorage.getItem(SUPPLIER_ID_KEY) ??
    sessionStorage.getItem(SUPPLIER_ID_KEY)
  );
};

export const clearTokens = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(SUPPLIER_ID_KEY);

  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(SUPPLIER_ID_KEY);
};

export const isAuthenticated = (): boolean => {
  return Boolean(getAccessToken());
};

export const updateAccessToken = (accessToken: string): void => {
  if (localStorage.getItem(ACCESS_TOKEN_KEY)) {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  } else if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  }
};
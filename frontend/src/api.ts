const API_URL = 'http://localhost:8000';

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(error?.detail || 'Erreur avec le serveur');
  }

  return response.json();
}

export function authHeader(token: string) {
  return {
    Authorization: `Bearer ${token}`,
  };
}

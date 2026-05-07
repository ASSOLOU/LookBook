import { FormEvent, useState } from 'react';
import type { ReactNode } from 'react';
import { api, authHeader } from './api';
import type { Item, LoginResponse, Trip, User } from './types';

function App() {
  const [username, setUsername] = useState('demo');
  const [email, setEmail] = useState('demo@lookbook.test');
  const [password, setPassword] = useState('demo123');
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('Backend attendu sur http://localhost:8000');
  const [items, setItems] = useState<Item[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [weather, setWeather] = useState<Record<string, unknown> | null>(null);

  async function register() {
    setMessage('Création du compte...');

    try {
      await api<User>('/register', {
        method: 'POST',
        body: JSON.stringify({ username, email, password }),
      });
      setMessage('Compte créé. Tu peux te connecter.');
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function login(event: FormEvent) {
    event.preventDefault();
    setMessage('Connexion...');

    try {
      const data = await api<LoginResponse>('/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setToken(data.token);
      setMessage('Connecté. Tu peux charger les données.');
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function loadItems() {
    if (!token) {
      setMessage('Connecte-toi avant.');
      return;
    }

    try {
      const data = await api<Item[]>('/items', {
        headers: authHeader(token),
      });
      setItems(data);
      setMessage(`${data.length} vêtement(s) chargé(s).`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function loadTrips() {
    if (!token) {
      setMessage('Connecte-toi avant.');
      return;
    }

    try {
      const data = await api<Trip[]>('/trips', {
        headers: authHeader(token),
      });
      setTrips(data);
      setMessage(`${data.length} voyage(s) chargé(s).`);
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function loadWeather() {
    try {
      const data = await api<Record<string, unknown>>('/weather?location=Paris');
      setWeather(data);
      setMessage('Météo chargée.');
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-wide text-blue-600"></p>
        <h1 className="text-4xl font-bold text-gray-900"></h1>
        <p className="mt-2 text-gray-600">
          
        </p>
      </header>

      <section className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <div className="rounded-2xl bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-xl font-semibold">Compte</h2>

          <form className="space-y-4" onSubmit={login}>
            <Input label="Nom" value={username} onChange={setUsername} />
            <Input label="Email" value={email} onChange={setEmail} type="email" />
            <Input label="Mot de passe" value={password} onChange={setPassword} type="password" />

            <div className="grid grid-cols-2 gap-3">
              <button
                className="rounded-xl bg-gray-900 px-4 py-3 font-semibold text-white"
                type="submit"
              >
                Connexion
              </button>
              <button
                className="rounded-xl border border-gray-300 px-4 py-3 font-semibold text-gray-800"
                onClick={register}
                type="button"
              >
                Inscription
              </button>
            </div>
          </form>

          {token && (
            <div className="mt-4 rounded-xl bg-gray-100 p-3 text-xs text-gray-700">
              Token : {token.slice(0, 18)}...
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="rounded-2xl bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-xl font-semibold">Actions</h2>
            <div className="flex flex-wrap gap-3">
              <ActionButton onClick={loadItems}>Voir mes vêtements</ActionButton>
              <ActionButton onClick={loadTrips}>Voir mes voyages</ActionButton>
              <ActionButton onClick={loadWeather}>Météo Paris</ActionButton>
            </div>
            <p className="mt-4 rounded-xl bg-blue-50 p-3 text-sm text-blue-900">{message}</p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <List title="Vêtements" emptyText="Aucun vêtement chargé">
              {items.map((item) => (
                <ItemCard key={item.id} item={item} />
              ))}
            </List>

            <List title="Voyages" emptyText="Aucun voyage chargé">
              {trips.map((trip) => (
                <div key={trip.id} className="rounded-xl border border-gray-200 p-4">
                  <p className="font-semibold">{trip.destination}</p>
                  <p className="text-sm text-gray-600">
                    {trip.start_date} → {trip.end_date}
                  </p>
                </div>
              ))}
            </List>
          </div>

          {weather && (
            <pre className="max-h-80 overflow-auto rounded-2xl bg-gray-900 p-4 text-sm text-white">
              {JSON.stringify(weather, null, 2)}
            </pre>
          )}
        </div>
      </section>
    </main>
  );
}

type InputProps = {
  label: string;
  value: string;
  type?: string;
  onChange: (value: string) => void;
};

function Input({ label, value, type = 'text', onChange }: InputProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-gray-700">{label}</span>
      <input
        className="w-full rounded-xl border border-gray-300 px-3 py-2 outline-none focus:border-blue-500"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ActionButton({ children, onClick }: { children: string; onClick: () => void }) {
  return (
    <button
      className="rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white hover:bg-blue-700"
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function List({ title, emptyText, children }: { title: string; emptyText: string; children: ReactNode }) {
  const content = Array.isArray(children) && children.length === 0 ? null : children;

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-xl font-semibold">{title}</h2>
      <div className="space-y-3">
        {content || <p className="text-sm text-gray-500">{emptyText}</p>}
      </div>
    </section>
  );
}

function ItemCard({ item }: { item: Item }) {
  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{item.name}</p>
          <p className="text-sm text-gray-600">
            {item.category} · chaleur {item.warmth}
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium">
          {item.color || 'couleur ?'}
        </span>
      </div>
      {item.waterproof && <p className="mt-2 text-sm text-blue-700">Imperméable</p>}
    </div>
  );
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return 'Erreur inconnue';
}

export default App;

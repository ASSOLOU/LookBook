export type User = {
  id: number;
  username: string;
  email: string;
};

export type Item = {
  id: number;
  name: string;
  category: string;
  color?: string;
  warmth: number;
  waterproof: boolean;
  style?: string;
};

export type Trip = {
  id: number;
  destination: string;
  start_date: string;
  end_date: string;
};

export type LoginResponse = {
  token: string;
};

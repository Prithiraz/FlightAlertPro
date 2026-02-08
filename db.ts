import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
  throw new Error('VITE_SUPABASE_URL is not configured. Please set it in your .env file.');
}

if (!supabaseAnonKey) {
  throw new Error('VITE_SUPABASE_ANON_KEY is not configured. Please set it in your .env file.');
}

let supabaseHost = 'unknown';
try {
  supabaseHost = new URL(supabaseUrl).host;
} catch (error) {
  throw new Error(`Invalid VITE_SUPABASE_URL: ${supabaseUrl}`);
}

console.log('===== SUPABASE INITIALIZATION =====');
console.log('Supabase host:', supabaseHost);
console.log('===================================');

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export function getSupabaseHost(): string {
  return supabaseHost;
}

export interface PriceAlert {
  id?: string;
  user_email: string;
  from_iata: string;
  to_iata: string;
  max_price: number;
  departure_date?: string;
  is_active: boolean;
  notification_channels: ('email' | 'whatsapp')[];
  created_at?: string;
}

export interface SavedSearch {
  id?: string;
  user_email: string;
  from_iata: string;
  to_iata: string;
  departure_date: string;
  return_date?: string;
  passengers: number;
  cabin_class: string;
  search_name?: string;
  created_at?: string;
}

export interface UserProfile {
  id?: string;
  email: string;
  preferred_currency: string;
  theme: 'light' | 'dark';
  frequent_flyer_programs: Record<string, string>;
  preferred_airlines: string[];
  loyalty_tier?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AnalyticsEvent {
  id?: string;
  event_type: 'search' | 'click' | 'booking' | 'filter';
  route?: string;
  device_type?: string;
  timestamp?: string;
  metadata?: Record<string, any>;
}

export const alertsDb = {
  async create(alert: PriceAlert) {
    const { data, error } = await supabase
      .from('price_alerts')
      .insert([alert])
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async getByEmail(email: string) {
    const { data, error } = await supabase
      .from('price_alerts')
      .select('*')
      .eq('user_email', email)
      .eq('is_active', true);

    if (error) throw error;
    return data;
  },

  async update(id: string, updates: Partial<PriceAlert>) {
    const { data, error } = await supabase
      .from('price_alerts')
      .update(updates)
      .eq('id', id)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async delete(id: string) {
    const { error } = await supabase
      .from('price_alerts')
      .delete()
      .eq('id', id);

    if (error) throw error;
    return true;
  }
};

export const savedSearchesDb = {
  async create(search: SavedSearch) {
    const { data, error } = await supabase
      .from('saved_searches')
      .insert([search])
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async getByEmail(email: string) {
    const { data, error } = await supabase
      .from('saved_searches')
      .select('*')
      .eq('user_email', email)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data;
  },

  async delete(id: string) {
    const { error } = await supabase
      .from('saved_searches')
      .delete()
      .eq('id', id);

    if (error) throw error;
    return true;
  }
};

export const userProfilesDb = {
  async create(profile: UserProfile) {
    const { data, error } = await supabase
      .from('user_profiles')
      .insert([profile])
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async getByEmail(email: string) {
    const { data, error } = await supabase
      .from('user_profiles')
      .select('*')
      .eq('email', email)
      .single();

    if (error) throw error;
    return data;
  },

  async update(email: string, updates: Partial<UserProfile>) {
    const { data, error } = await supabase
      .from('user_profiles')
      .update(updates)
      .eq('email', email)
      .select()
      .single();

    if (error) throw error;
    return data;
  }
};

export const analyticsDb = {
  async logEvent(event: AnalyticsEvent) {
    const { error } = await supabase
      .from('analytics_events')
      .insert([{
        ...event,
        timestamp: new Date().toISOString()
      }]);

    if (error) console.error('Analytics error:', error);
  },

  async getPopularRoutes(limit: number = 10) {
    const { data, error } = await supabase
      .from('analytics_events')
      .select('route')
      .eq('event_type', 'search')
      .not('route', 'is', null);

    if (error) throw error;

    const routeCounts: Record<string, number> = {};
    data?.forEach(item => {
      if (item.route) {
        routeCounts[item.route] = (routeCounts[item.route] || 0) + 1;
      }
    });

    return Object.entries(routeCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, limit)
      .map(([route, count]) => ({ route, count }));
  }
};

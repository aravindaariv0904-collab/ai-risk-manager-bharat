import { createClient, SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl =
  import.meta.env.VITE_SUPABASE_URL || 'https://digktcqwnvkdfyhgkroc.supabase.co'
const supabaseAnonKey =
  import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_eYHuWoKr7l48sKEqVtOOeQ_sHfIE-fI'

export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseAnonKey)
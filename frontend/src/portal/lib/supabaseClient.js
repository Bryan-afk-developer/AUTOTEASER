import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://wyumnamymbpejtvxlpku.supabase.co'
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_-mZzCDLCF6GNXvplQgZKwg_f626SYtm'

export const supabase = createClient(supabaseUrl, supabaseKey)

-- Add separate address fields to clients table
-- Run this in your Supabase SQL Editor

ALTER TABLE clients 
ADD COLUMN IF NOT EXISTS street1 TEXT,
ADD COLUMN IF NOT EXISTS street2 TEXT,
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS state TEXT,
ADD COLUMN IF NOT EXISTS zip_code TEXT;

-- If you want to enable the Places API to work, you also need to
-- enable it in Google Cloud Console:
-- 1. Go to https://console.cloud.google.com
-- 2. Select your project
-- 3. Go to APIs & Services > Library
-- 4. Search for "Places API" (the original one, not "Places API (New)")
-- 5. Enable it
-- 6. Make sure your API key has access to it
